import configparser
import pathlib

from typing import Union

import boto3  # type: ignore
import botocore # type: ignore

from .utils import _log, pathify

class Spaces():
    def __init__(self, client: botocore.client, bucket: str):
        self.client = client
        self.bucket = bucket

    def upload(self, path: pathlib.Path, key: str) -> bool:
        if path.exists():
            _log().debug("uploading %s to bucket=%s key=%s", path, self.bucket, key)
            self.client.upload_file(str(path), self.bucket, key)
            return True
        return False

    @staticmethod
    def from_file(filename: Union[pathlib.Path, str], section="spaces") -> "Spaces":
        client = spaces_connect(filename, section)
        bucket = get_spaces_bucket(filename, section)
        return Spaces(client, bucket)

def spaces_connect(filename: Union[pathlib.Path, str], section="spaces"):
    _keys = {"region_name", "api_version", "use_ssl", "verify",
             "endpoint_url", "aws_access_key_id", "aws_secret_access_key",
             "aws_session_token", "config"}
    parser = configparser.ConfigParser()
    parser.read(pathify(filename))

    session = boto3.session.Session()
    if parser.has_section(section):
        cfg = {k: v for k, v in parser.items(section) if k in _keys}
        _log().info("connected to spaces")
        return session.client("s3", **cfg)
    else:
        raise Exception(f"Section {section} not found in {str(filename)}")


def get_spaces_bucket(filename: Union[pathlib.Path, str], section="spaces") -> str:
    parser = configparser.ConfigParser()
    parser.read(pathify(filename))

    if parser.has_section(section):
        return dict(parser.items(section))["bucket"]
    else:
        raise Exception(f"Section {section} not found in {str(filename)}")
