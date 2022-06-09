from setuptools import setup

setup(
    name="ibkr_web_api",
    version="1.1.0",
    url="https://github.com/stopdesign/ibkr_web_api.git",
    author="Gregory",
    description="IBKR Web API",
    packages=["ibkr_web_api"],
    package_dir={"": "src"},
    install_requires=[
        "requests==2.28.0",
        "termcolor==1.1.0",
        "pycryptodome==3.14.1",
        "cryptography==37.0.2",
    ],
)
