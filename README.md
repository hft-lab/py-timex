INSTALL
=======

```shell
git clone git@github.com:hft-lab/py-timex.git
# also may be cloned via https
# git clone https://github.com/hft-lab/py-timex.git
pip install py-timex
```

```python
from py_timex.client import WsClientTimex, ETHUSD

api_key = "foo"
api_secret = "bar"

client = WsClientTimex(api_key, api_secret)
client.subscribe(ETHUSD)
client.run_orderbook_updater()
```
