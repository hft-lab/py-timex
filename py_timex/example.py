import time
import logging

from py_timex.client import WsClientTimex, OrderBook

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s (%(funcName)s)'
logging.basicConfig(format=FORMAT)
log = logging.getLogger("sample bot")
log.setLevel(logging.DEBUG)

api_key = ""
api_secret = ""

updates_received = 0


def handle_update(update: OrderBook):
    global updates_received
    updates_received += 1
    print(f"update {update.market} bids: {len(update.bids)} asks: {len(update.asks)}")
    for bid in update.bids:
        print(f"\tbid:\tprice: {bid.price}\tvolume: {bid.volume}")
    for ask in update.asks:
        print(f"\task:\tprice: {ask.price}\tvolume: {ask.volume}")
    print()


client = WsClientTimex(api_key, api_secret)
client.subscribe("ETHUSD")
client.subscribe("BTCUSD")
client.start_background_updater(handle_update)

try:
    while True:
        time.sleep(10)
        log.info("updates received: %s", updates_received)
except KeyboardInterrupt:
    log.info("exit")
    client.stop_background_updater()
