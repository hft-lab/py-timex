INSTALL
=======

```shell
git clone git@github.com:hft-lab/py-timex.git
# also may be cloned via https
# git clone https://github.com/hft-lab/py-timex.git
pip install py-timex
```

```python
import logging
import multiprocessing

from py_timex.client import WsClientTimex

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s (%(funcName)s)'
logging.basicConfig(format=FORMAT)
log = logging.getLogger("sample bot")
log.setLevel(logging.DEBUG)

api_key = "foo"
api_secret = "bar"

queue = multiprocessing.Queue(1024)


def handle_update(update: dict):
    queue.put(update)


client = WsClientTimex(api_key, api_secret)
client.subscribe("ETHUSD")
client.subscribe("BTCUSD")
client.start_background_updater(handle_update)
while True:
    upd = queue.get()
    log.info("order book updated. exchange: %s\tmarket: %s", upd["exchange"], upd["market"])
```
