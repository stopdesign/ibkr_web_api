import logging

log = logging.getLogger("ib.accounts")


MAX_CONF = 5


class Accounts:
    def __init__(self, session) -> None:
        self._session = session

    def accounts(self):
        return self._session.json_request("/iserver/accounts", "GET")

    def trades(self):
        url = f"/iserver/account/trades"
        return self._session.json_request(url, "GET")

    def orders(self):
        url = f"/iserver/account/orders?force=false"
        # url += "&filters=filled"
        return self._session.json_request(url, "GET")

    def order_status(self, order_id: int):
        url = f"/iserver/account/order/status/{order_id}"
        return self._session.json_request(url, "GET")

    def cancel_order(self, account_id: str, order_id: int):
        url = f"/iserver/account/{account_id}/order/{order_id}"
        return self._session.json_request(url, "DELETE")

    def preview_order(self, account_id: str, order: dict, confirm=False):
        # confirm - для совместимости с place_order
        url = f"/iserver/account/{account_id}/orders/whatif"
        data = {"orders": [order]}
        return self._session.json_request(url, "POST", data=data)

    def place_order(self, account_id: str, order: dict, confirm=False):
        """
        Размещение ордера.
        При confirm=True ордер подтверждается автоматически.
        """
        results = []
        url = f"/iserver/account/{account_id}/orders"
        data = {"orders": [order]}
        res = self._session.json_request(url, "POST", data=data)
        results.append(res)

        # Ошибка или нет автоподтверждения
        if not confirm or not res.json or res.error:
            return results

        # Ордер создан
        if type(res.json) is list and "order_id" in res.json[0]:
            return results

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
                results.append(res)
            else:
                log.error("No reply id in confirmation request")

        return results

    def place_order_reply(self, reply_id: str):
        url = f"/iserver/reply/{reply_id}"
        data = {"confirmed": True}
        return self._session.json_request(url, "POST", data=data)
