import datetime
import pathlib
import shutil
import time

from typing import Dict, Optional

from .configuration import Configuration
from .crypto import generate_random_key, encrypt_file
from .interval import IntervalCollection
from .spaces import Spaces
from .utils import _log

def get_raw_video_path_parts(raw_video_path: pathlib.Path) -> Dict[str, str]:
    parts = raw_video_path.parts
    return {
        "datetime": parts[-1],
        "processing_stage": parts[-2],
        "device": parts[-3],
        "observation_id": parts[-4]
    }


def upload_all(config: Configuration, spaces_client: Spaces,
               interval_collection: Optional[IntervalCollection] = None):
    _log().info("starting upload")
    uploads = {
        "videos": 0,
        "keys": 0,
        "detections": 0,
        "logs": 0,
    }
    for key_path in config.observation_directory.glob("**/processed/**/*.key"):
        uploads["keys"] += upload_key(config, key_path, spaces_client, interval_collection)
    for video_path in config.observation_directory.glob("**/processed/**/*.mp4"):
        uploads["videos"] += upload_video(config, video_path, spaces_client)
    for det_path in config.observation_directory.glob("**/detections/**/log.*"):
        uploads["detections"] += upload_detections(config, det_path, spaces_client)
    for logs in pathlib.Path(".").glob("logs/log.*"):
        uploads["logs"] += upload_logs(config, logs, spaces_client)
    for processed in config.observation_directory.glob("**/processed/*"):
        clean_directories(processed)
    return uploads

def upload_video(config: Configuration, video_path: pathlib.Path, spaces_client: Spaces) -> int:
    # generate key
    key_name = f"{video_path.name}.key"
    key_path = video_path.parent / key_name
    if (generate_random_key(key_path) != 0): return 0
    # encrypt file
    output_video_path = video_path.parent / f"{video_path.name}.enc"
    if (encrypt_file(video_path, key_path, output_video_path) == 0):
        # upload if was able to encrypt...otherwise, just delete
        key_suffix = (
            f"{output_video_path.parent.parent.parent.name}/"        # observation_id
            f"{output_video_path.parent.parent.name}/"               # processed
            f"{output_video_path.parent.name}/"                      # time
            f"{output_video_path.name}")                             # file
        try:
            upload(config, spaces_client, output_video_path, key_suffix)
            output_video_path.unlink(missing_ok=True)
            video_path.unlink(missing_ok=True)
        except Exception:
            pass
    # delete
    else:
        output_video_path.unlink(missing_ok=True)
        video_path.unlink(missing_ok=True)
    return 1


def upload_key(config: Configuration, key_path: pathlib.Path, spaces_client: Spaces,
               interval_collection: Optional[IntervalCollection]) -> int:
    key_suffix = (
        f"{key_path.parent.parent.parent.name}/"        # observation_id
        f"{key_path.parent.parent.name}/"               # processed
        f"{key_path.parent.name}/"                      # time
        f"{key_path.name}")                             # file
    file_create_time = datetime.datetime.strptime(key_path.parent.name, "%Y_%m_%d_%H_%M_%S_%f")

    overlaps = interval_collection is not None and\
        interval_collection.point_overlaps(file_create_time)

    now = datetime.datetime.now()
    diff = (now - file_create_time).total_seconds() / 60 / 60
    if overlaps:
        if 2 * config.purgatory_hours < diff:
            shutil.rmtree(key_path)
    else:
        if config.purgatory_hours < diff:
            try:
                upload(config, spaces_client, key_path, key_suffix)
                key_path.unlink()
                return 1
            except Exception:
                _log.error("Fatal error in main loop", exc_info=True)
    return 0


def upload_detections(config: Configuration, det_path: pathlib.Path, spaces_client: Spaces) -> int:
    key_suffix = (
        f"{det_path.parent.parent.parent.name}/"        # observation_id
        f"{det_path.parent.parent.name}/"               # detections
        f"{det_path.parent.name}/"                      # detection type
        f"{det_path.name}")                             # name
    upload(config, spaces_client, det_path, key_suffix)
    det_path.unlink(missing_ok=True)
    return 1


def upload_logs(config: Configuration, log_path: pathlib.Path, spaces_client: Spaces) -> int:
    key_suffix = (
        f"{config.observation_directory.name}/"  # observation_id
        "logs/"                                  # logs
        f"{log_path.name}")                      # name
    upload(config, spaces_client, log_path, key_suffix)
    log_path.unlink(missing_ok=True)
    return 1


def upload(config: Configuration,
           spaces_client: Spaces,
           upload_path: pathlib.Path,
           key_suffix: str):
    key = f"{config.spaces_root_key}/{key_suffix}"
    try:
        start = time.time()
        spaces_client.upload(upload_path, key)
        end = time.time()
        seconds = end - start
        _log().info("uploaded %s->%s in %d seconds", upload_path, key_suffix, seconds)
    except Exception:
        _log().error("failed to uploaded %s->%s", upload_path, key_suffix, exc_info=True)


def clean_directories(path):
    _log().info("%s", list(path.glob("./*")))
    if len(list(path.glob("./*"))) == 0:
        shutil.rmtree(path)
