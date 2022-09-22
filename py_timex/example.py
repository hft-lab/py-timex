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


class TriangleBot:
    _updates_received = 0
    _test_order_sent = False

    def __init__(self, client: timex.WsClientTimex):
        self._client = client
        client.subscribe(timex.ETHAUDT, self.handle_update)
        client.subscribe(timex.BTCUSD, self.handle_update)
        client.subscribe_balances(self.handle_balance)
        client.subscribe_orders(self.handle_order)

    def handle_update(self, update: timex.OrderBook):
        self._updates_received += 1
        #log.info(f"update {update.market} bids: {len(update.bids)} asks: {len(update.asks)}")
        #for bid in update.bids:
        #    log.info(f"bid price: {bid.price}\tvolume: {bid.volume}")
        #    break
        #for ask in update.asks:
        #    log.info(f"ask price: {ask.price}\tvolume: {ask.volume}")
        #    break
        # also possible to access any current orderbook
        #log.info(self._client.order_books[timex.ETHAUDT].bids[:3])
        # access to balances
        #log.info(self._client.balances[timex.AUDT])
        if not self._test_order_sent:
            self._test_order_sent = True
            self._client.create_orders([
                timex.NewOrder(
                    price=1.1,
                    quantity=36.6,
                    side=timex.ORDER_SIDE_BUY,
                    type=timex.ORDER_TYPE_LIMIT,
                    symbol=timex.ETHAUDT,
                    expireInSeconds=3,
                )])

    def handle_balance(self, balance: timex.Balance):
        log.info(balance)

    def handle_order(self, order: timex.Order):
        log.info(order)

    def run(self):
        try:
            return self._client.run_updater()
        except KeyboardInterrupt:
            self._client.wait_closed()


timex_client = timex.WsClientTimex(cp["TIMEX"]["api_key"], cp["TIMEX"]["api_secret"])
bot = TriangleBot(timex_client)
bot.run()
