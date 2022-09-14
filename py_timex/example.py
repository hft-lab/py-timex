import logging
import time

from py_timex.client import WsClientTimex, ETHUSD

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s (%(funcName)s)'
logging.basicConfig(format=FORMAT)

api_key = "foo"
api_secret = "bar"

client = WsClientTimex(api_key, api_secret)
client.subscribe(ETHUSD)
client.start_background_updater()
while True:
    time.sleep(1)
    print(client.order_books)
