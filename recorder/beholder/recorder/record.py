import shutil
import subprocess

from typing import Optional

from .configuration import Configuration
from .utils import _log

def record(config: Configuration) -> Optional[subprocess.Popen]:
    if len(config.devices) == 0: return None

    for write_path in config.write_paths:
        write_path.mkdir(exist_ok=True, parents=True)

    # always clear the livestream files
    if config.hls_path.exists():
        shutil.rmtree(config.hls_path)
        config.hls_path.mkdir(exist_ok=True, parents=True)

    gstreamer_flags = config.gstreamer_flags()

    _log().info("gstreamer %s", gstreamer_flags)
    print(subprocess.list2cmdline(gstreamer_flags))
    p = subprocess.Popen(gstreamer_flags)
    print(p.args)
    return p


if __name__ == "__main__":
    config = Configuration.from_file("beholder.ini")
    record(config)
