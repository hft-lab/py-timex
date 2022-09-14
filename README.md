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
import time

from py_timex.client import WsClientTimex

FORMAT = '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s (%(funcName)s)'
logging.basicConfig(format=FORMAT)

api_key = "foo"
api_secret = "bar"

client = WsClientTimex(api_key, api_secret)
client.subscribe("ETHUSD")
client.subscribe("ETHAUD")
client.start_background_updater()
while True:
    time.sleep(1)
    print(client.order_books)
```
