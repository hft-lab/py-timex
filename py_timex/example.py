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
        log.info(f"bid price: {bid.price}\tvolume: {bid.volume}")
        break
    for ask in update.asks:
        log.info(f"ask price: {ask.price}\tvolume: {ask.volume}")
        break
    # also possible to access any current orderbook
    log.info(client.order_books[timex.ETHAUDT].bids[:3])
    # access to balances
    log.info(client.balances[timex.AUDT])


def handle_balance(balance: timex.Balance):
    log.info(balance)


def handle_order(order: timex.Order):
    # TODO: separate subscribe to cancelled/expired orders maybe
    log.info(order)


client = timex.WsClientTimex(cp["TIMEX"]["api_key"], cp["TIMEX"]["api_secret"])
client.subscribe(timex.ETHAUDT, handle_update)
client.subscribe(timex.BTCUSD, handle_update)
client.subscribe_balances(handle_balance)
client.subscribe_orders(handle_order)

try:
    client.run_updater()
except KeyboardInterrupt:
    client.wait_closed()
