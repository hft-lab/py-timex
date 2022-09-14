from py_timex.client import WsClientTimex, ETHUSD
import logging

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s (%(funcName)s)'
logging.basicConfig(format=FORMAT)


api_key = "foo"
api_secret = "bar"

client = WsClientTimex(api_key, api_secret)
client.subscribe(ETHUSD)
client.run_orderbook_updater()
