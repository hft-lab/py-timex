import collections
import logging
import configparser
import sys
import uuid

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

    def __init__(self, client: timex.WsClientTimex):
        self._client = client
        client.on_first_connect = self.on_first_connect
        client.subscribe(timex.ETHAUDT, self.handle_update)
        client.subscribe(timex.BTCUSD, self.handle_update)
        client.subscribe_balances(self.handle_balance)
        client.subscribe_orders(self.handle_order)

    def on_first_connect(self):
        self._client.create_orders([
            timex.NewOrder(
                price=1.1,
                quantity=36.6,
                side=timex.ORDER_SIDE_BUY,
                type=timex.ORDER_TYPE_LIMIT,
                symbol=timex.ETHAUDT,
                expire_in_seconds=3,
                client_order_id=str(uuid.uuid4()),
            )], self.handle_create_orders)

    def handle_create_orders(self, obj):
        log.info(obj)

    def handle_update(self, update: timex.OrderBook):
        self._updates_received += 1

    def handle_balance(self, balance: timex.Balance):
        log.info(balance)

    def handle_order(self, order: timex.Order):
        log.info(order)
        self._client.delete_orders([order.id], self.handle_delete_orders)

    def handle_delete_orders(self, obj):
        log.info(obj)

    def run(self):
        try:
            return self._client.run_updater()
        except KeyboardInterrupt:
            self._client.wait_closed()


timex_client = timex.WsClientTimex(cp["TIMEX"]["api_key"], cp["TIMEX"]["api_secret"])
bot = TriangleBot(timex_client)
bot.run()
