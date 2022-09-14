import aiohttp
import asyncio
import logging
import threading
import json

log = logging.getLogger("py-timex")
log.setLevel(logging.DEBUG)

_URI_WS = 'wss://plasma-relay-backend.timex.io/socket/relay'

ETHUSD = "ETHUSD"


class WsClientTimex:

    def __init__(self, api_key=None, api_secret=None, loop=None):
        if loop is None:
            self._loop = asyncio.new_event_loop()
        else:
            self._loop = loop
        self._api_key = api_key
        self._api_secret = api_secret
        self._connected = threading.Event()
        self._ws = None
        self._subscriptions = []

    def subscribe(self, pair):
        msg = {
            "type": "SUBSCRIBE",
            "requestId": "uniqueID",
            "pattern": "/orderbook.raw/%s" % pair,
        }
        self._subscriptions.append(json.dumps(msg))
        if self._connected.is_set():
            self._loop.run_until_complete(self._ws.send_str(msg))

    async def _run_orderbook_updater(self):
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(_URI_WS) as ws:
                log.info("connected")
                self._ws = ws
                self._connected.set()
                try:
                    for msg in self._subscriptions:
                        await ws.send_str(msg)
                    async for msg in ws:
                        self._process_msg(msg)
                finally:
                    self._connected.clear()
        log.info("disconnected")

    def _process_msg(self, msg: aiohttp.WSMessage):
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
                msg_type = data.get("type")
                if msg_type is None:
                    log.info("unknown data type: %s", msg.data)
                log.info(msg_type)
            except json.JSONDecodeError:
                log.exception("failed to decode json")
        elif msg.type == aiohttp.WSMsgType.PONG:
            log.info("PONG received")
        else:
            log.info("unknown message type: %s", msg.type)

    def run_orderbook_updater(self, *args, **kwargs):
        while True:
            try:
                self._loop.run_until_complete(self._run_orderbook_updater(*args, **kwargs))
            except Exception as e:
                log.exception("timex orderbook updater")
            log.info("reconnecting")

    def start_background_updater(self):
        pass
        #  ping_thread = threading.Thread()
