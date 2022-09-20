import collections

import aiohttp
import asyncio
import logging
import threading
import json
import time

log = logging.getLogger("py-timex")
log.setLevel(logging.DEBUG)

_URI_WS = 'wss://plasma-relay-backend.timex.io/socket/relay'

ETHUSD = "ETHUSD"
ETHAUD = "ETHAUD"


OrderBook = collections.namedtuple("OrderBook", ["exchange", "market", "bids", "asks"])
Entry = collections.namedtuple("Entry", ["price", "volume"])


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
        self.order_books = {}
        self._closed = False
        self._connected = threading.Event()
        self._callbacks = {}

    def subscribe(self, market: str, callback: callable):
        self.order_books[market] = OrderBook(exchange="TIMEX", market=market, bids=[], asks=[])
        self._callbacks[market] = callback

    def _request_order_book(self, market: str):
        return self._rest_message("get_orderbook", {"market": market})

    def _rest_message(self, request_id: str, payload: dict):
        msg = {
            "type": "REST",
            "requestId": request_id,
            "stream": "/get/public/orderbook/raw",
            "auth": {
                "id": self._api_key,
                "secret": self._api_secret
            },
            "payload": payload,
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

    async def _subscribe_all_markets(self):
        for market in self.order_books.keys():
            await self._request_order_book(market)
            await self._subscribe(market)

    async def _run_orderbook_updater(self):
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(_URI_WS) as ws:
                self._connected.set()
                try:
                    log.info("connected")
                    self._ws = ws
                    asyncio.create_task(self._subscribe_all_markets())
                    async for msg in ws:
                        self._process_msg(msg)
                finally:
                    self._connected.clear()
        log.info("disconnected")

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

    def _process_msg(self, msg: aiohttp.WSMessage):
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                obj = json.loads(msg.data)
                msg_type = obj.get("type")
                if msg_type == "MESSAGE":
                    data = obj["message"]["event"]["data"]
                    return self._handle_ob_update(
                        data["market"],
                        data["rawOrderBook"]["bid"],
                        data["rawOrderBook"]["ask"],
                        )
                request_id = obj.get("requestId")
                if request_id is not None:
                    log.info("first raw orderbook received")
                    r_body = obj.get("responseBody")
                    if r_body is None:
                        print(obj)
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

            except json.JSONDecodeError:
                log.exception("failed to decode json")
            except KeyError:
                log.exception("invalid data")
        elif msg.type == aiohttp.WSMsgType.PONG:
            log.info("PONG received")
        else:
            log.info("unknown message type: %s", msg.type)

    def run_updater(self):
        while True:
            try:
                self._loop.run_until_complete(self._run_orderbook_updater())
            except Exception as e:
                log.exception("timex orderbook updater")
            if self._closed:
                return
            time.sleep(1)
            log.info("reconnecting")

    def start_background_updater(self, callback):
        self._background_updater_thread = threading.Thread(
            target=self.run_updater,
            args=(callback,))
        self._background_updater_thread.start()

    def stop_background_updater(self):
        log.info("stopping background updater")
        self._closed = True
        self._loop.create_task(self._ws.close())

    def wait_closed(self):
        self._loop.run_until_complete(self._ws.close())
