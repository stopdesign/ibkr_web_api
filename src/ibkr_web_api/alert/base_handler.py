class BaseAlertHandler:
    def __init__(self) -> None:
        pass

    def send(self, text: str) -> None:
        print(f"ALERT: {text}")
