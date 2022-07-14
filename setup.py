from setuptools import setup

setup(
    name="ibkr_web_api",
    version="1.1.1",
    url="https://github.com/stopdesign/ibkr_web_api.git",
    author="Gregory",
    description="IBKR Web API",
    packages=["ibkr_web_api"],
    package_dir={"": "src"},
    install_requires=[
        "redis~=4.3",
        "requests~=2.28",
        "termcolor~=1.1",
        "pycryptodome~=3.14",
        "cryptography~=37.0",
    ],
)
