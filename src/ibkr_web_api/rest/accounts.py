class Accounts:
    def __init__(self, session) -> None:
        self._session = session
    
    def accounts(self):
        return self._session.json_request("/iserver/accounts", "GET")

    def orders(self):
        data = {"filters": []}
        return self._session.json_request("/iserver/account/orders?force=false", "GET")
