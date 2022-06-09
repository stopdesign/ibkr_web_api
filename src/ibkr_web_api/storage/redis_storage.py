import json

from cryptography.fernet import Fernet
from termcolor import cprint

from .abc import AbstractSessionStorage


class RedisStorage(AbstractSessionStorage):
    def __init__(self, session_name, redis_client, secret):
        """
        session_name - имя пользователя IBKR или другой понятный идентификатор сессии
        redis_client - коннект к редис(из пула или напрямую)
        secret - чтобы безопасно хранить сессию и не проебать
        """
        self.session_name = session_name
        self.redis = redis_client
        self.secret = secret

    def save(self, data: dict):
        # Сдампить cookies в строку и зашифровать
        cookies = data["cookies"]
        cookies_str = json.dumps(cookies, default=str).encode()
        data = {"cookies": self.encrypt(cookies_str, self.secret)}
        stream_name = f"session_{self.session_name}"
        self.redis.xadd(stream_name, data, maxlen=5, approximate=False)

        cprint(
            "SAVE SESSION: "
            f"uid={cookies.get('USERID')}, "
            f"cp={cookies.get('cp')}, "
            f"token={cookies.get('XYZAB')}",
            "green",
        )

    def load(self) -> dict:
        stream_name = f"session_{self.session_name}"
        res = self.redis.xread({stream_name: b"0-0"}, None, 1000)
        try:
            enc_value = res[0][1][-1][1][b"cookies"]
            cookies = json.loads(self.decrypt(enc_value, self.secret).decode())
            data = {
                "cookies": cookies,
            }
            # print(json.dumps(cookies, indent=2))
            cprint(
                "LOAD SESSION: "
                f"uid={cookies.get('USERID')}, "
                f"cp={cookies.get('cp')}, "
                f"token={cookies.get('XYZAB')}",
                "blue",
            )
            return data
        except (IndexError, ValueError):
            return {}

    def encrypt(self, message: bytes, key: bytes) -> bytes:
        assert key, "No secret key provided"
        return Fernet(key).encrypt(message)

    def decrypt(self, token: bytes, key: bytes) -> bytes:
        assert key, "No secret key provided"
        return Fernet(key).decrypt(token)
