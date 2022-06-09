from termcolor import cprint


class MarketData:
    def __init__(self, session) -> None:
        self._session = session

    def history(self):
        url = "/iserver/marketdata/history"
        url += "?conid=508109460&period=30min&bar=10min&outsideRth=true"
        res = self._session.json_request(url, "GET")
        if res.json and res.json.get("startTime") and res.json.get("data"):
            cprint(f"History OK", "green")
        else:
            cprint(f"History ERROR", "red")
        return res.json
