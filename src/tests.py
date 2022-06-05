import sys
import unittest

import click
import redis
from termcolor import cprint

from ibkr_web_api import IbApi
from ibkr_web_api.session_storage import RedisStorage


class TestIbApi(unittest.TestCase):
    # надо поставить через cli
    username = None
    password = None
    paper = None
    secret = None
    redis_host = None
    redis_port = None
    redis_db = None
    redis_password = None

    def setUp(self) -> None:
        redis_client = redis.Redis(
            self.redis_host,
            self.redis_port,
            self.redis_db,
            self.redis_password
        )

        self.storage = RedisStorage(
            session_name=self.username,
            redis_client=redis_client,
            secret=self.secret
        )

        self.ib = IbApi(self.username, self.password, session_storage=self.storage, paper=self.paper, debug=False)

    def test_1_login(self):
        cprint("\n\nREQUEST_LOGIN\n", "red")
        self.ib.request_login()
        self.assertIsNotNone(self.ib.jsessionid)

        cprint("\n\nREQUEST_INIT\n", "red")
        self.ib.request_init()

        cprint("\n\nREQUEST_COMPLETEAUTH\n", "red")
        self.ib.request_completeauth()

        cprint("\n\nREQUEST_DISPATHER\n", "red")
        self.ib.request_dispatcher()

        cprint("\n\nVALIDATE SSO\n", "red")
        res = self.ib.sso_validate()
        self.assertIsNotNone(res.get('USER_ID'))
        self.assertIsNotNone(res.get('RESULT'))

        cprint("\n\nINIT_PORTAL_SESSION\n", "red")
        self.ib.init_portal_session()

        cprint("\n\nINIT_ISERVER_SESSION\n", "red")
        self.ib.init_iserver_session()

        cprint("\n\nACCOUNTS\n", "red")
        self.ib.accounts()

        cprint("\n\nHISTORY\n", "red")
        self.ib.history()

        self.ib.print_cookies()

        res = self.ib.sso_validate()
        self.assertIsNotNone(res.get('USER_ID'))
        self.assertIsNotNone(res.get('RESULT'))
        self.ib.save_session()

    def test_2_session_load(self):
        self.ib = IbApi(self.username, self.password, session_storage=self.storage, paper=True, debug=False)
        self.ib.load_session()
        res = self.ib.sso_validate()
        self.assertIsNotNone(res.get('USER_ID'))
        self.assertIsNotNone(res.get('RESULT'))


@click.command()
@click.option('--username', required=True)
@click.option('--password', required=True)
@click.option('--paper', default=False, is_flag=True)
@click.option('--secret', default='fl94ey6PO1kTdMQFRbp-cyiZoxqGvW70h_7N4XwCPFs=')
@click.option('--redis_host', default='127.0.0.1')
@click.option('--redis_port', default=6379)
@click.option('--redis_db', default=0)
@click.option('--redis_password', default='')
def runner(username, password, paper, secret, redis_host, redis_port, redis_db, redis_password):
    TestIbApi.username = username
    TestIbApi.password = password
    TestIbApi.paper = True if paper else False
    TestIbApi.secret = secret
    TestIbApi.redis_host = redis_host
    TestIbApi.redis_port = redis_port
    TestIbApi.redis_db = redis_db
    TestIbApi.redis_password = redis_password

    unittest.main(argv=[sys.argv[0]])


if __name__ == '__main__':
    runner()
