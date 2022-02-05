import datetime
import pathlib

from typing import Dict, Optional

from ffprobe import FFProbe  # type: ignore
from dateutil import parser  # type: ignore

from .configuration import Configuration
from .interval import IntervalCollection

def get_raw_video_path_parts(raw_video_path: pathlib.Path) -> Dict[str, str]:
    parts = raw_video_path.parts
    return {
        "filename": parts[-1],
        "processing_stage": parts[-2],
        "observation_id": parts[-3]
    }


def process_all(config: Configuration, interval_collection: Optional[IntervalCollection] = None):
    cnt = 0
    for video_path in config.observation_directory.glob("**/recording/*.mp4"):
        cnt += process_video(config, interval_collection, video_path)
    return cnt


def process_video(config: Configuration,
                  interval_collection: Optional[IntervalCollection],
                  raw_video_path: pathlib.Path) -> int:
    create_time = get_create_time(raw_video_path)

    now = datetime.datetime.now()
    create_elapsed = now - create_time.replace(tzinfo=None)
    if (create_elapsed < datetime.timedelta(seconds=2 * config.segment_time_seconds)):
        return 0

    # move file to processed path
    create_time_str = create_time.strftime("%Y_%m_%d_%H_%M_%S_%f")
    processed_path = config.observation_directory / "processed" / create_time_str
    processed_path.mkdir(exist_ok=True, parents=True)
    processed_video = processed_path / "video.mp4"
    raw_video_path.replace(processed_video)
    return 1


def get_create_time(videopath: pathlib.Path) -> datetime.datetime:
    probe = FFProbe(str(videopath))
    iso_str = probe.metadata.get("creation_time", None)
    stat_ctime = datetime.datetime.fromtimestamp(videopath.stat().st_ctime)
    if iso_str is not None:
        return parser.isoparse(iso_str)  # type: ignore
    return stat_ctime


if __name__ == "__main__":
    config = Configuration.from_file("beholder.ini")
    process_all(config)
