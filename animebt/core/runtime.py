"""User data paths and redacted, rotating application logs."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading

logger = logging.getLogger("animebt")
_secrets = set()


def register_secret(value):
    if isinstance(value, str) and value:
        _secrets.add(value)


class RedactedFormatter(logging.Formatter):
    def format(self, record):
        output = super().format(record)
        for secret in sorted(_secrets, key=len, reverse=True):
            output = output.replace(secret, "[REDACTED]")
        return output


def default_data_dir():
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "AnimeBT"
    return Path(".animebt")


def initialize_runtime(directory):
    directory = Path(directory).resolve()
    for folder in (directory, directory / "cache", directory / "logs"):
        folder.mkdir(parents=True, exist_ok=True)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(directory / "logs" / "animebt.log", maxBytes=2 * 1024 * 1024,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(RedactedFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    sys.excepthook = lambda kind, error, tb: logger.critical("未捕获异常", exc_info=(kind, error, tb))
    threading.excepthook = lambda args: logger.critical("线程未捕获异常", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    return directory


def record_error(context, error):
    logger.error(context, exc_info=(type(error), error, error.__traceback__))
