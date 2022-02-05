import configparser
import logging
import pathlib
import sys

from typing import Optional

from mailjet_rest import Client  # type: ignore


def mj_connect(filename: pathlib.Path, section='mailjet') -> Optional[Client]:
    parser = configparser.ConfigParser()
    parser.read(filename)
    if parser.has_section(section):
        items = dict(parser.items(section))
        return Client(auth=(items["public"], items["private"]), version="v3.1")
    else:
        raise Exception(f"Section {section} not found in {filename}")


def _log():
    return logging.getLogger()


def setup_logging():
    root = logging.getLogger()
    formatter =\
        logging.Formatter("[%(asctime)s %(process)d] [%(name)s] [%(levelname)s] %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.propagate = True
    root.setLevel(logging.INFO)
