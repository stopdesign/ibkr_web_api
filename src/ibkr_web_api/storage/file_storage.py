import json
import logging
import os

from .abc import AbstractSessionStorage

log = logging.getLogger("session_file_storage")


class FileStorage(AbstractSessionStorage):
    def __init__(self, username, path=""):
        """
        session_name - имя пользователя или другой идентификатор сессии.
        """
        self.data_file_path = f"session_{username}.json"

    def save(self, data):
        with open(self.data_file_path, "w") as f:
            f.write(json.dumps(data, indent=2, default=str))

    def load(self):
        if os.path.isfile(self.data_file_path):
            try:
                return json.load(open(self.data_file_path))
            except Exception as e:
                log.error("Bad session file format")
                log.error(e)
        else:
            log.warning("Session file not found")
        return {}
