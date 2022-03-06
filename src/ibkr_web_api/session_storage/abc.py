from abc import ABC, abstractmethod


class AbstractSessionStorage(ABC):
    @abstractmethod
    def save(self, cookies: dict):
        pass

    @abstractmethod
    def load(self) -> dict:
        pass
