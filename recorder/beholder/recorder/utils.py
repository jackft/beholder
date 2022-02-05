import configparser
import logging
import logging.handlers
import pathlib

from typing import Callable, Optional, Union

import psycopg2 # type: ignore

from beholder.recorder import _log  # type: ignore


class BackcallerTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename, when='h', interval=1, backupCount=0,
                 encoding=None, delay=False, utc=False, atTime=None, callback=Callable[[], None]):
        super(BackcallerTimedRotatingFileHandler, self).__init__(
            filename, when, interval, backupCount,
            encoding, delay, utc, atTime
        )
        self.callback = callback

    def doRollover(self):
        # invoke the superclass' actual rotation implementation
        super(BackcallerTimedRotatingFileHandler, self).doRollover()
        self.callback()


def setup_logging(log_level, log_path, log_backup) -> BackcallerTimedRotatingFileHandler:
    root = _log()
    formatter = logging.Formatter(
        "[%(asctime)s %(process)d] [%(name)s] [%(levelname)s] %(message)s"
    )
    handler = BackcallerTimedRotatingFileHandler(
        log_path, when="h", interval=1, backupCount=log_backup
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.propagate = True
    root.setLevel(log_level)

    return handler


def pathify(str_or_path: Union[str, pathlib.Path]) -> pathlib.Path:
    return pathlib.Path(str_or_path) if isinstance(str_or_path, str) else str_or_path


def pg_connect(
    filename: Union[pathlib.Path, str], section="postgresql"
) -> Optional[psycopg2.extensions.connection]:
    parser = configparser.ConfigParser()
    parser.read(pathify(filename))
    if parser.has_section(section):
        db = {k: v for k, v in parser.items(section)}
        conn = psycopg2.connect(**db)
        _log().info(f"connected to db {db['database']} @ {db['host']}")
        return conn
    else:
        raise Exception(f"Section {section} not found in {str(filename)}")
