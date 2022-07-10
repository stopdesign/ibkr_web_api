
class Trsrv:
    def __init__(self, session) -> None:
        self._session = session

    def secdef(self, conid: str):
        data = {
            "conids": [conid]
        }
        return self._session.json_request(f"/trsrv/secdef", "POST", data)

    def stocks(self, symbols: str):
        url = f"/trsrv/stocks?symbols={symbols}"
        return self._session.json_request(url, "GET")

    def futures(self, symbols: str):
        url = f"/trsrv/futures?symbols={symbols}"
        return self._session.json_request(url, "GET")

    # def schedule(self, asset_class, symbols, exchange, exchange_filter):
    #     data = {
    #         "assetClass": asset_class,
    #         "symbols": symbols,
    #         "exchange": exchange,
    #         "exchangeFilter": exchange_filter,
    #     }
    #     url = "/trsrv/secdef/schedule"
    #     return self._session.json_request(url, "GET", data)
