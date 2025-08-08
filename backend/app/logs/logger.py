from os.path import join, abspath, dirname
import logging
import logging.config


LOGGER_NAME: str = "docflow"
LOG_FORMAT: str = (
    "%(asctime)s [%(levelname)s] | %(name)s | %(filename)s | %(funcName)s | %(lineno)d | %(message)s"
)
LOG_LEVEL: int = logging.DEBUG

BASE_DIR = abspath(dirname(__file__))
LOG_FILE: str = join(BASE_DIR, "docflow.log")  # now uses BASE_DIR

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "standard",
            "level": "DEBUG",
            "filename": LOG_FILE,          # use the full path
            "mode": "a",
            "encoding": "utf-8",
            "maxBytes": 500_000,
            "backupCount": 4,
        },
    },
    "loggers": {
        # root logger
        "": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        # your application logger
        LOGGER_NAME: {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # SQLAlchemy warnings/errors still go to file
        "sqlalchemy": {
            "handlers": ["file"],
            "level": "WARNING",
        },
        # uvicorn logs
        "uvicorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "uvicorn.asgi": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

logging.config.dictConfig(LOGGING)

# 
docflow_logger = logging.getLogger(LOGGER_NAME)
sqlalchemy_logger = logging.getLogger("sqlalchemy")
# (we removed the separate "s3" logger—no more AWS here)
