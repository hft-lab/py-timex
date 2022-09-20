import logging
import configparser
import sys

import py_timex.client as timex

cp = configparser.ConfigParser()

if len(sys.argv) != 2:
    print("Usage %s <config.ini>" % sys.argv[0])
    sys.exit(1)
cp.read(sys.argv[1], "utf-8")

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s (%(funcName)s)'
logging.basicConfig(format=FORMAT)
log = logging.getLogger("sample bot")
log.setLevel(logging.DEBUG)

updates_received = 0


def handle_update(update: timex.OrderBook):
    global updates_received
    updates_received += 1
    log.info(f"update {update.market} bids: {len(update.bids)} asks: {len(update.asks)}")
    for bid in update.bids:
        log.info(f"\tbid:\tprice: {bid.price}\tvolume: {bid.volume}")
    for ask in update.asks:
        log.info(f"\task:\tprice: {ask.price}\tvolume: {ask.volume}")
    # also possible to access any current orderbook
    symbol = timex.ETHUSD
    log.info("%s: %s", symbol, client.order_books[symbol].bids)
    # access to balances
    for currency, balance in client.balances.items():
        log.info(f"{currency}\t{balance.total_balance}")


client = timex.WsClientTimex(cp["TIMEX"]["api_key"], cp["TIMEX"]["api_secret"])
client.subscribe(timex.ETHUSD, handle_update)
client.subscribe(timex.BTCUSD, handle_update)

try:
    client.run_updater()
except KeyboardInterrupt:
    client.wait_closed()
