import logging

log = logging.getLogger("ib.accounts")


MAX_CONF = 5


class Accounts:
    def __init__(self, session) -> None:
        self._session = session
    
    def accounts(self):
        return self._session.json_request("/iserver/accounts", "GET")

    def orders(self):
        url = "/iserver/account/orders?force=false"
        # data = {"filters": []}
        return self._session.json_request(url, "GET")

    def place_order(self, account_id: str, order: dict, confirm=False):
        """
        Размещение ордера.
        При confirm=True ордер подтверждается автоматически.
        """
        url = f"/iserver/account/{account_id}/orders"
        data = {"orders": [order]}
        res = self._session.json_request(url, "POST", data=data)
        
        # Ошибка или нет автоподтверждения
        if not confirm or not res.json or res.error:
            return res
        
        # Ордер создан
        if type(res.json) is list and "order_id" in res.json[0]:
            return res

        # Просят что-то подтвердить
        cnt = 0
        while type(res.json) is list and "id" in res.json[0] and cnt < MAX_CONF:
            cnt += 1
            if messages := res.json[0].get("message"):
                if type(messages) is list:
                    for message in messages:
                        message = message.replace("\n", " ")
                        log.warning(f"Order confirmation: {message}")
                else:
                    messages = messages.replace("\n", " ")
                    log.warning(f"Order confirmation: {messages}")
            if reply_id := res.json[0].get("id"):
                res = self.place_order_reply(reply_id)
            else:
                log.error("No reply id in confirmation request")

        return res

    def place_order_reply(self, reply_id: str):
        url = f"/iserver/reply/{reply_id}"
        data = {"confirmed": True}
        return self._session.json_request(url, "POST", data=data)
