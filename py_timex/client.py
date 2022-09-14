import aiohttp
import asyncio
import logging
import threading
import json

log = logging.getLogger("py-timex")
log.setLevel(logging.DEBUG)

_URI_WS = 'wss://plasma-relay-backend.timex.io/socket/relay'

ETHUSD = "ETHUSD"
ETHAUD = "ETHAUD"


class WsClientTimex:

    def __init__(self, api_key=None, api_secret=None, loop=None):
        if loop is None:
            self._loop = asyncio.new_event_loop()
        else:
            self._loop = loop
        self._api_key = api_key
        self._api_secret = api_secret
        self._ws = None
        self._markets = []
        self._background_updater_thread = None
        self.order_books = {}
        self._closed = False
        self._connected = threading.Event()
        self._all_markets = {}
        if self._markets is None:
            raise ValueError("missing required argument")

    def subscribe(self, market):
        self._markets.append(market)
        self.order_books[market] = {"bid": [], "ask": []}

    def _request_order_book(self, market):
        return self._rest_message("stub", {"market": market})

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

    def _subscribe(self, market):
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
        for market in self._markets:
            await self._subscribe(market)
            await self._request_order_book(market)

    async def _run_orderbook_updater(self, callback):
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(_URI_WS) as ws:
                self._connected.set()
                try:
                    log.info("connected")
                    self._ws = ws
                    asyncio.create_task(self._subscribe_all_markets())
                    async for msg in ws:
                        self._process_msg(msg, callback)
                finally:
                    self._connected.clear()
        log.info("disconnected")

    def _handle_ob_update(self, data: dict, callback: callable):
        message_type = data.get("type", "")
        if message_type != "MESSAGE":
            return
        try:
            message = data["message"]
            if message["event"]["type"] != "RAW_ORDER_BOOK_UPDATED":
                return
            data = message["event"]["data"]
            market = data["market"]
            ob = self.order_books.get(market)
            if ob is None:
                log.error("unknown market %s", market)
                return
            raw_ob = data["rawOrderBook"]
            ob["bid"] = raw_ob["bid"]
            ob["ask"] = raw_ob["ask"]
            ob["exchange"] = "TIMEX"
            ob["market"] = market
            callback(ob)
        except KeyError:
            log.exception("invalid data")

    def _process_msg(self, msg: aiohttp.WSMessage, callback: callable):
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
                msg_type = data.get("type")
                if msg_type is None:
                    log.info("unknown data type: %s", msg.data)
                self._handle_ob_update(data, callback)
            except json.JSONDecodeError:
                log.exception("failed to decode json")
        elif msg.type == aiohttp.WSMsgType.PONG:
            log.info("PONG received")
        else:
            log.info("unknown message type: %s", msg.type)

    def run_orderbook_updater(self, callback):
        while True:
            try:
                self._loop.run_until_complete(self._run_orderbook_updater(callback))
            except Exception as e:
                log.exception("timex orderbook updater")
            if self._closed:
                return
            log.info("reconnecting")

    def start_background_updater(self, callback):
        self._background_updater_thread = threading.Thread(
            target=self.run_orderbook_updater,
            args=(callback,))
        self._background_updater_thread.start()

    def stop_background_updater(self):
        # TBD
        pass
