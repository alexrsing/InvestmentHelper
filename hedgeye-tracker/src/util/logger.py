from typing import Any


class Logger:
    def __init__(self, name: str):
        self.name = name

    def log(self, message: Any):
        print(f"[{self.name}] {message}")

    def get_logger(self, name: str) -> "Logger":
        return Logger(name)

    def debug(self, message: Any):
        self.log(f"DEBUG: {message}")

    def info(self, message: Any):
        self.log(f"INFO: {message}")

    def warning(self, message: Any):
        self.log(f"WARNING: {message}")

    def error(self, message: Any):
        self.log(f"ERROR: {message}")
