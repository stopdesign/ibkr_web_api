from termcolor import cprint


class MarketData:
    def __init__(self, session) -> None:
        self._session = session

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
