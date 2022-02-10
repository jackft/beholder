import configparser
import json
import pathlib
import re

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import v4l2ctl # type: ignore
import sounddevice # type: ignore

from .utils import _log

@dataclass
class CameraDevice:
    name: str
    device: str
    format: str

@dataclass
class MicrophoneDevice:
    name: str
    device: str
    channels: int

@dataclass
class DeviceComplex:
    camera: CameraDevice
    microphone: Optional[MicrophoneDevice]
    primary: bool
    loopback: bool
    number: int

    @property
    def path_friendly_name(self):
        return self.camera.name.replace(" ", "_").replace(":", "") + f"_device_{self.number}"

class Configuration():
    def __init__(self,
                 user_config: Dict[str, str],
                 primary_device_name: str,
                 devices: List[DeviceComplex],
                 output_directory: pathlib.Path,
                 observation_id: str,
                 record_fps: int = 15,
                 output_fps: int = 15,
                 primary_resolution: str = "1920x1080",
                 secondary_resolution: str = "1280x720",
                 loopback_width: int = 640,
                 loopback_height: int = 480,
                 segment_time_seconds: int = 60,
                 hls_enabled: bool = False,
                 hls_list_size: int = 2,
                 hls_target_duration: int = 1,
                 loopback_enabled: bool = False,
                 purgatory_hours: float = 0,
                 restart_seconds: int = 3600,
                 spaces_root_key: str = "beholder"):
        self.primary_device_name = primary_device_name
        self.devices: List[DeviceComplex] = devices
        self.output_directory = output_directory
        self.observation_id = observation_id
        self.record_fps = record_fps
        self.output_fps = output_fps

        self.primary_resolution = primary_resolution
        self.secondary_resolution = secondary_resolution
        self.loopback_width = loopback_width
        self.loopback_height = loopback_height
        self.segment_time_seconds = segment_time_seconds

        self.hls_enabled = hls_enabled
        self.hls_list_size = hls_list_size
        self.hls_target_duration = hls_target_duration

        self.loopback_enabled = loopback_enabled

        self.restart_seconds = restart_seconds
        self.purgatory_hours = purgatory_hours

        self.spaces_root_key = spaces_root_key

        self.verbose: Optional[bool] = None

        if self.primary_device is not None:
            self.primary_device.primary = True

    @property
    def primary_device(self) -> Optional[DeviceComplex]:
        for device in self.devices:
            if self.primary_device_name in device.camera.name:
                return device
        return None

    @property
    def loopbackdevice(self) -> Optional[DeviceComplex]:
        for device in self.devices:
            if device.loopback:
                return device
        return None

    @property
    def loopback_number(self) -> Optional[int]:
        for device in self.devices:
            if device.loopback:
                return int(str(device.camera.device)[-1])
        return None

    @property
    def write_paths(self) -> List[pathlib.Path]:
        paths: List[pathlib.Path] = []
        paths.append(self.out_path)
        paths.append(self.hls_path)
        return paths

    @property
    def out_location(self) -> pathlib.Path:
        return (
            self.observation_directory /
            'recording' /
            'output%07d.mp4'
        )

    @property
    def hls_location(self) -> pathlib.Path:
        return (
            pathlib.Path("/tmp") /
            'livestream' /
            'segment%05d.ts'
        )

    @property
    def hls_playlist_location(self) -> pathlib.Path:
        return (
            pathlib.Path("/tmp") /
            'livestream' /
            'playlist.m3u8'
        )

    @property
    def out_path(self) -> pathlib.Path:
        return self.out_location.parent

    @property
    def hls_path(self) -> pathlib.Path:
        return self.hls_location.parent

    def set_verbose(self, flag: bool):
        if self.verbose is None:
            self.verbose = flag

    def gstreamer_flags(self) -> List[str]:
        stream = []

        stream.append("gst-launch-1.0 -e ")
        out_time_ns = seconds2ns(self.segment_time_seconds)
        compositor = (
            "nvcompositor name=comp"
            " sink_0::xpos=0    sink_0::ypos=0   sink_0::width=1280 sink_0::height=720"
            " sink_1::xpos=1280 sink_1::ypos=0   sink_1::width=1280 sink_1::height=720"
            " sink_2::xpos=0    sink_2::ypos=720 sink_2::width=1280 sink_2::height=720"
            " ! nvvidconv"
            f" ! video/x-raw(memory:NVMM),width=2560,height=1440,"
            f"framerate={self.output_fps}/1,format=NV12"
            " ! tee name=u ! queue max-size-buffers=0 max-size-time=0"
            " ! nvv4l2h264enc preset-level=1 insert-vui=1 iframeinterval=30"
            " ! h264parse ! tee name=t"
            f" t. ! splitmuxsink max-size-time={out_time_ns}"
            f" location={str(self.out_location)} mux=qtmux name=mux sync=false")
        if self.hls_enabled:
            compositor += (
                f" t. ! h264parse ! video/x-h264 "
                f" ! hlssink2 max-files={self.hls_list_size}"
                f" location={str(self.hls_location)} target-duration={self.hls_target_duration}"
                f" playlist_location={str(self.hls_playlist_location)}") # noqa: E122
        if self.loopback_enabled and self.loopbackdevice is not None:
            compositor += (
                " u. ! queue max-size-buffers=0 max-size-time=0" # noqa: E122
                " ! nvvidconv" # noqa: E122
                f" ! video/x-raw,width={self.loopback_width},height={self.loopback_height},framerate={self.record_fps}/1,format=UYVY" # noqa: E122, E501
                " ! identity drop-allocation=true !"                      # noqa: E122
                f" v4l2sink device={self.loopbackdevice.camera.device}")  # noqa: E122

        inputs = []
        sink_idx = 1 # starts at 1 because the primary device is always 0
        for device in self.devices:
            if device.loopback: continue
            if device.primary:
                inputs.append(
                    (f"v4l2src device={device.camera.device}"
                     " ! image/jpeg,width=1280,height=720,framerate=30/1,pixel-aspect-ratio=1/1"
                     " ! jpegdec ! nvvidconv"
                     f" ! video/x-raw(memory:NVMM),width=1280,height=720,"
                     f"framerate={self.record_fps}/1,format=RGBA"
                     " ! queue max-size-buffers=0 max-size-time=0 max-size-bytes=0"
                     " ! comp.sink_0 ")
                )
                if device.microphone is not None:
                    inputs.append(
                        (f"alsasrc device={device.microphone.device} latency-time=10000"
                         " ! audioconvert ! audioresample ! audio/x-raw"
                         " ! voaacenc ! queue max-size-buffers=0 max-size-time=0 max-size-bytes=0"
                         " ! mux.audio_0 ")
                    )
            else:
                inputs.append(
                    (f"v4l2src device={device.camera.device}"
                     " ! image/jpeg,width=1280,height=720,framerate=30/1,"
                     "pixel-aspect-ratio=1/1"
                     " ! jpegdec ! nvvidconv"
                     f" ! video/x-raw(memory:NVMM),width=1280,height=720,"
                     f"framerate={self.record_fps}/1,format=RGBA"
                     " ! queue max-size-buffers=0 max-size-time=0 max-size-bytes=0"
                     f" ! comp.sink_{sink_idx} ")
                )
                if device.microphone is not None:
                    inputs.append(
                        (f"alsasrc device={device.microphone.device} latency-time=10000"
                         " ! audioconvert ! audioresample ! audio/x-raw"
                         " ! voaacenc ! queue max-size-buffers=0 max-size-time=0 max-size-bytes=0"
                         f" ! mux.audio_{sink_idx} ")
                    )
                sink_idx += 1
        stream.append(compositor)
        stream.append("".join(inputs))

        s = " ".join(stream)
        flags = [_s for _s in s.split(" ") if _s != ""]
        return flags

    def refresh_devices(self):
        self.devices = get_joined_devices()

    @property
    def observation_directory(self) -> pathlib.Path:
        return self.output_directory / self.observation_id

    @classmethod
    def from_file(cls, cfgpath: Union[str, pathlib.Path]):
        # ----------------------------------------------------------------------
        # Read config
        # ----------------------------------------------------------------------
        if isinstance(cfgpath, str):
            _cfgpath = pathlib.Path(cfgpath)
        else:
            _cfgpath = cfgpath

        if not _cfgpath.exists():
            raise FileNotFoundError

        parser = configparser.ConfigParser()
        with _cfgpath.open("r") as f:
            parser.read_file(f)
        _log().debug("read config %s", _cfgpath)

        if "beholder" not in parser:
            raise AttributeError

        # ----------------------------------------------------------------------
        #  Parse config and map devices
        # ----------------------------------------------------------------------

        devices = get_joined_devices()
        user_config_pth = pathlib.Path(parser.get("beholder", "user_config"))
        output_directory = user_config_pth / "beholder-data"
        user_config = parse_user_config(user_config_pth / "config.json")
        return Configuration(
            user_config=user_config,
            primary_device_name=parser.get("beholder", "primary_device_name"),
            devices=devices,
            output_directory=output_directory,
            observation_id=user_config["participant_id"],
            primary_resolution=parser.get("beholder", "primary_resolution", fallback="1280x720"),
            secondary_resolution=parser.get(
                "beholder", "secondary_resolution", fallback="1280x720"),
            loopback_width=parser.getint("beholder", "loopback_width", fallback=640),
            loopback_height=parser.getint("beholder", "loopback_height", fallback=480),
            record_fps=parser.getint("beholder", "record_fps", fallback=15),
            output_fps=parser.getint("beholder", "output_fps", fallback=15),
            segment_time_seconds=parser.getint("beholder", "segment_time_seconds", fallback=60),
            hls_enabled=parser.getboolean("beholder", "hls_enabled", fallback=False),
            hls_list_size=parser.getint("beholder", "hls_list_size", fallback=5),
            hls_target_duration=parser.getint("beholder", "hls_target_duration", fallback=1),
            loopback_enabled=parser.getboolean("beholder", "loopback_enabled", fallback=False),
            restart_seconds=parser.getint("beholder", "restart_seconds", fallback=0),
            purgatory_hours=parser.getfloat("beholder", "purgatory_hours", fallback=0),
            spaces_root_key=parser.get("beholder", "spaces_root_key", fallback="beholder")
        )

    @property
    def device_paths(self) -> List[pathlib.Path]:
        return [(
            self.output_directory /
            self.observation_id /
            device.path_friendly_name
        ) for device in self.devices]

    @property
    def raw_device_paths(self):
        return [(device_path / "raw") for device_path in self.device_paths]

    @property
    def processed_device_paths(self):
        return [(device_path / "raw") for device_path in self.device_paths]

    def display(self):
        devices = "\n".join("    - " + device.camera.name for device in self.devices)
        print((
            "Beholder Config\n"
            "  devices\n"
            + devices + "\n"
            "  parameters\n"
            f"    - primary_device_name = {self.primary_device_name}\n"
            f"    - record_fps = {self.record_fps}\n"
            f"    - segment_time = {self.segment_time} seconds\n"
            f"    - thread_queue_size = {self.thread_queue_size}"
        ))


def get_cameras() -> Tuple[List[v4l2ctl.V4l2Device], List[v4l2ctl.V4l2Device]]:
    video_devices_name = pathlib.Path("/dev").glob("./video*")
    cameras = []
    loopbacks = []
    for video_device_name in video_devices_name:
        video_device = v4l2ctl.V4l2Device(video_device_name)
        if video_device.buffer_type == v4l2ctl.V4l2BufferType.VIDEO_CAPTURE:
            cameras.append(video_device)
        elif video_device.name == "LoopbackDevice":
            loopbacks.append(video_device)
    return cameras, loopbacks


def preferred_format(camera: v4l2ctl.V4l2Device) -> str:
    preferences = {
        "H264": "h264",
        "MJPEG": "mjpeg"
    }

    pref_format = None
    for format in camera.formats:
        if format.format.name in preferences:
            pref_format = preferences[format.format.name]
    assert pref_format is not None
    return pref_format


def get_microphones() -> List[Dict[str, Union[str, int]]]:
    sound_devices = sounddevice.query_devices()
    microphones = []
    for sound_device in sound_devices:
        if sound_device["max_input_channels"] > 0 and\
           sound_device["hostapi"] == 0 and\
           re.match(r".* \(hw:\d+,\d+\)", sound_device["name"]):
            microphones.append(sound_device)
    return microphones


def get_joined_devices():
    microphones = get_microphones()
    cameras, loopbacks = get_cameras()

    _joined_devices = []
    for camera in cameras:
        for (i, microphone) in enumerate(microphones):
            if camera.name.split(":")[0] in microphone["name"].split(":")[0]:
                cam = camera
                mic = microphones.pop(i)
                _joined_devices.append((cam, mic))
                break

    joined_devices = []
    for idx, (camera, microphone) in enumerate(_joined_devices):
        cam = CameraDevice(camera.name, camera.device, "")
        mic_devices = re.findall(r"hw:\d+", microphone["name"])
        assert len(mic_devices) == 1
        mic_device = mic_devices[0]
        mic = MicrophoneDevice(microphone["name"], mic_device, microphone["max_input_channels"])
        joined_devices.append(DeviceComplex(cam, mic, False, False, idx))

    for idx2, camera in enumerate(loopbacks):
        cam = CameraDevice("loopback", camera.device, "")
        joined_devices.append(DeviceComplex(cam, None, False, True, idx2))

    return joined_devices


NS_PER_SECOND = int(1e9)
def seconds2ns(seconds: int) -> int:
    return seconds * NS_PER_SECOND


def parse_user_config(config_path: pathlib.Path) -> Dict[str, str]:
    with config_path.open("r") as f:
        data: Dict[str, str] = json.load(f)
        return data


if __name__ == "__main__":
    config = Configuration.from_file("beholder.ini")
    config.display()
    inputs, outputs = config.gstreamer_string()
    for inp in inputs:
        print(inp)
    for out in outputs:
        print(out)
