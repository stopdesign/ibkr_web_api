# ibkr_web_api
IBKR web API client

### example
```python
username = "username"
password = "password"
# Fernet.generate_key()
secret = 'fl94ey6PO1kTdMQFRbp-cyiZoxqGvW70h_7N4XwCPFs='

redis_host = '127.0.0.1'
redis_port = 6379
redis_db = 0
redis_password = ''
redis_client = redis.Redis(redis_host, redis_port, redis_db, redis_password)

storage = RedisStorage(
    session_name=username,
    redis_client=redis_client,
    secret=secret
)

ib = IbApi(username, password, session_storage=storage, paper=True, debug=False)

```

### tests
```shell
python src/tests.py --username=<username> --password=<password> --paper
```
