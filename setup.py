from setuptools import setup, find_packages

setup(
    name="ibkr_web_api",
    version="1.1.6",
    url="https://github.com/stopdesign/ibkr_web_api.git",
    author="Gregory",
    description="IBKR Web API",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "redis~=4.3",
        "requests~=2.28",
        "termcolor~=1.1",
        "pycryptodome~=3.18",
        "cryptography~=41.0",
    ],
)
