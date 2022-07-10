from termcolor import cprint


class MarketData:
    def __init__(self, session) -> None:
        self._session = session

    def search(self, symbol: str):
        url = "/iserver/secdef/search"
        data = {
            "symbol": symbol,
            "name": False,
        }
        return self._session.json_request(url, "POST", data)

    def contract_info(self, conid):
        url = f"/iserver/contract/{conid}/info"
        return self._session.json_request(url, "GET")

    def snapshot(self, conids, since):
        url = "/iserver/marketdata/snapshot"
        # &fields=31&fields=84&fields=85&fields=86&fields=88
        url += f"?conids={conids}&since={since}"
        return self._session.json_request(url, "GET")

    def history(self, conid, period, bar="1min", rth=True):
        url = "/iserver/marketdata/history"
        outsideRth = "false" if rth else "true"
        url += f"?conid={conid}&period={period}&bar={bar}&outsideRth={outsideRth}"
        return self._session.json_request(url, "GET")

    def history_test(self):
        res = self.history(508109460, period="30min", bar="10min")
        if res.json and res.json.get("startTime") and res.json.get("data"):
            cprint(f"History OK", "green")
            return True
        else:
            cprint(f"History ERROR", "red")
            return False
