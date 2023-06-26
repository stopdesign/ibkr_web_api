class Portfolio:
    def __init__(self, session) -> None:
        self._session = session

    def summary(self, account):
        return self._session.json_request(f"/portfolio/{account}/summary", "GET")

    def accounts(self):
        url = f"/portfolio/accounts"
        return self._session.json_request(url, "GET")

    def positions_simple(self, account):
        url = f"/portfolio/{account}/positions?simple=true"
        return self._session.json_request(url, "GET")

    def positions_2(self, account):
        url = f"/portfolio2/{account}/positions"
        return self._session.json_request(url, "GET")

    def invalidate_cache(self, account):
        url = f"/portfolio/{account}/positions/invalidate"
        return self._session.json_request(url, "POST")
