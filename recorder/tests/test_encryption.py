import pytest

import subprocess
import pathlib
import tempfile

from beholder.recorder.crypto import decrypt_file, encrypt_file, generate_random_key

def test_encryption(vpath: pathlib.Path):
    with tempfile.TemporaryDirectory() as tmpdirname:
        dir = pathlib.Path(tmpdirname)
        key = tmpdirname / pathlib.Path("key")
        enc = tmpdirname / pathlib.Path("test_enc")
        dec = tmpdirname / pathlib.Path("test_dec")
        assert 0 == generate_random_key(key)
        assert 0 == encrypt_file(vpath, key, enc)
        assert 0 == decrypt_file(enc, key, dec)
        assert subprocess.run(["cmp", "--silent", str(dec), str(vpath)])
