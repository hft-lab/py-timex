import aiohttp
import asyncio

import collections
import base64
import logging
import threading
import json
import time
import uuid
import http.client

log = logging.getLogger("py-timex")
log.setLevel(logging.DEBUG)

_URI_WS = 'wss://plasma-relay-backend.timex.io/socket/relay'
_HOSTNAME_REST = 'plasma-relay-backend.timex.io'

EXCHANGE = "TIMEX"
ETHUSD = "ETHUSD"
BTCUSD = "BTCUSD"
ETHAUDT = "ETHAUDT"

_eventTypeRawOrderBookUpdated = "RAW_ORDER_BOOK_UPDATED"
_eventTypeAccountSubscription = "ACCOUNT_SUBSCRIPTION"

OrderBook = collections.namedtuple("OrderBook", ["exchange", "market", "bids", "asks"])
Entry = collections.namedtuple("Entry", ["price", "volume"])
Balance = collections.namedtuple("Balance", ['currency', 'total_balance', 'locked_balance'])
# TODO: add all fields
Order = collections.namedtuple("Order",
                               ['id', 'symbol', 'side', 'type', 'quantity', 'price'])


class WsClientTimex:

    def __init__(self, api_key=None, api_secret=None, loop=None):
        if loop is None:
            self._loop = asyncio.new_event_loop()
        else:
            self._loop = loop
        self._api_key = api_key
        self._api_secret = api_secret
        self._ws = None
        self._background_updater_thread = None
        self.order_books = dict[str, OrderBook]()
        self.balances = dict[str, Balance]()
        self._closed = False
        self._connected = threading.Event()
        self._callbacks = {}
        self._rest_queries = {}
        basic_auth = f"{self._api_key}:{self._api_secret}"
        basic_auth = base64.b64encode(basic_auth.encode("ascii"))
        self._http_rest_auth = "Basic " + basic_auth.decode("ascii")
        me = self._http_rest("GET", "/custody/credentials/me")
        self.address = me["address"]
        self._balances_callback = None
        self._orders_callback = None

    def subscribe_balances(self, callback: callable):
        self._balances_callback = callback

    def subscribe_orders(self, callback: callable):
        self._orders_callback = callback

    def _http_rest(self, method: str, path: str):
        conn = http.client.HTTPSConnection(_HOSTNAME_REST)
        conn.request(method, path, headers={"Authorization": self._http_rest_auth})
        r = conn.getresponse()
        ct = r.headers.get("Content-Type")
        if ct != "application/json":
            log.error("Non json rest response")
            return
        return json.loads(r.read())

    def subscribe(self, market: str, callback: callable):
        self.order_books[market] = OrderBook(exchange=EXCHANGE, market=market, bids=[], asks=[])
        self._callbacks[market] = callback

    async def _ws_rest(self, stream: str, payload: dict, callback: callable):
        request_id = str(uuid.uuid4())
        msg = {"type": "REST",
               "requestId": request_id,
               "stream": stream,
               "auth": {
                   "id": self._api_key,
                   "secret": self._api_secret
               }, "payload": payload}
        self._connected.wait()
        await self._ws.send_json(msg)
        self._rest_queries[request_id] = callback

    def _account_subscribe(self):
        msg = {
            "type": "ACCOUNT_SUBSCRIBE",
            "requestId": "acs",
            "account": self.address,
            "auth": {
                "id": self._api_key,
                "secret": self._api_secret,
            },
            "snapshot": True,
        }
        return self._ws.send_json(msg)

    def _subscribe(self, market: str):
        msg = {
            "type": "SUBSCRIBE",
            "requestId": "uniqueID",
            "pattern": "/orderbook.raw/%s" % market,
            "auth": {
                "id": self._api_key,
                "secret": self._api_secret
            },
        }
        return self._ws.send_json(msg)

    async def _subscribe_all(self):
        await self._ws_rest("/get/trading/balances",
                            {},
                            self._handle_rest_balances)
        await self._account_subscribe()
        for market in self.order_books.keys():
            await self._ws_rest("/get/public/orderbook/raw",
                                {"market": market},
                                self._handle_rest_orderbook)
            await self._subscribe(market)

    def _handle_ob_update(self, market: str, bids: list, asks: list):
        ob = self.order_books.get(market)
        if ob is None:
            log.error("unknown market %s", market)
            return
        ob.bids.clear()
        for bid in bids:
            ob.bids.append(Entry(price=float(bid["price"]), volume=float(bid["quantity"])))
        ob.asks.clear()
        for ask in asks:
            ob.asks.append(Entry(price=float(ask["price"]), volume=float(ask["quantity"])))
        self._callbacks[market](ob)

    def _handle_rest_balances(self, obj: dict):
        for b in obj.get("responseBody", []):
            balance = Balance(currency=b["currency"],
                              total_balance=b["totalBalance"],
                              locked_balance=b["lockedBalance"])
            self.balances[balance.currency] = balance
        if self._balances_callback is not None:
            for balance in self.balances.values():
                self._balances_callback(balance)

    def _handle_rest_orderbook(self, obj: dict):
        status = obj.get("status")
        if status != "SUCCESS":
            log.error("rest orderbook request error: %s (%s)", status, obj.get("message"))
            log.error(obj)
            return
        r_body = obj.get("responseBody")
        if r_body is None:
            return
        asks = r_body["ask"]
        bids = r_body["bid"]
        if len(asks) != 0:
            market = asks[0]["market"]
        elif len(bids) != 0:
            market = bids[0]["market"]
        else:
            log.warning("empty update")
            return
        self._handle_ob_update(market, bids, asks)

    def _handle_ws_account_subscription(self, obj: dict):
        payload = obj.get("payload")
        balance = payload.get("balance")
        if balance is not None:
            if self._balances_callback is not None:
                self._balances_callback(
                    Balance(currency=balance["currency"],
                            total_balance=float(balance["totalBalance"]),
                            locked_balance=float(balance["lockedBalance"])))
            return
        order = payload.get("order")
        if order is not None:
            if self._orders_callback is not None:
                self._orders_callback(
                    Order(
                        id=order["id"],
                        symbol=order["symbol"],
                        side=order["side"],
                        type=order["type"],
                        quantity=float(order["quantity"]),
                        price=float(order["price"]),
                    ))
            return
        log.info("unknown")
        log.info(obj)

    def _process_msg(self, msg: aiohttp.WSMessage):
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                obj = json.loads(msg.data)
                msg_type = obj.get("type")
                if msg_type == _eventTypeAccountSubscription:
                    return self._handle_ws_account_subscription(obj)
                if msg_type == "MESSAGE":
                    event = obj["message"]["event"]
                    if event["type"] == _eventTypeRawOrderBookUpdated:
                        data = event["data"]
                        return self._handle_ob_update(
                            data["market"],
                            data["rawOrderBook"]["bid"],
                            data["rawOrderBook"]["ask"],
                        )
                    else:
                        log.warning("Unknown event type: %s. Ignoring." % event["type"])
                        log.info(obj)
                        return
                if msg_type == "SUBSCRIBED":
                    return
                request_id = obj.get("requestId")
                if request_id is not None:
                    cb = self._rest_queries.get(request_id)
                    if cb is None:
                        log.error("Unknown rest request id: %s", request_id)
                        log.error(msg.data)
                        return
                    cb(obj)
            except json.JSONDecodeError:
                log.exception("failed to decode json")
            except KeyError:
                log.exception("invalid data")
        elif msg.type == aiohttp.WSMsgType.PONG:
            log.info("PONG received")
        else:
            log.info("unknown message type: %s", msg.type)

    async def _run_ws_loop(self):
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(_URI_WS) as ws:
                self._connected.set()
                try:
                    log.info("connected")
                    self._ws = ws
                    asyncio.create_task(self._subscribe_all())
                    async for msg in ws:
                        self._process_msg(msg)
                finally:
                    self._connected.clear()
        log.info("disconnected")

    def run_updater(self):
        while True:
            try:
                self._loop.run_until_complete(self._run_ws_loop())
            except Exception as e:
                log.exception("timex orderbook updater")
            if self._closed:
                return
            time.sleep(1)
            log.info("reconnecting")

    def wait_closed(self):
        self._loop.run_until_complete(self._ws.close())
