from setuptools import setup

setup(
    name="ibkr_web_api",
    version="1.0.3",
    url="https://github.com/stopdesign/ibkr_web_api.git",
    author="Gregory Zhizhilkin",
    description="IBKR Web API",
    packages=["ibkr_web_api", "ibkr_web_api.session_storage"],
    package_dir={"": "src"},
    install_requires=[
        "requests==2.25.1",
        "termcolor==1.1.0",
        "pycryptodome==3.13.0",
    ],
)
