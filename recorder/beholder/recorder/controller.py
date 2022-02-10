import configparser

import datetime
import os
import pathlib
import signal
import sqlite3
import subprocess
import time

from concurrent.futures import ThreadPoolExecutor as Pool
from concurrent.futures import Future
from typing import Optional, Union

import psutil # type: ignore
import pyudev # type: ignore
import requests # type: ignore

from .configuration import Configuration
from .interval import IntervalCollection, RecordTime
from .computer_vision import computer_vision
from .process_recordings import process_all
from .record import record
from .spaces import Spaces
from .upload_recordings import upload_all
from .utils import _log

class Credentials:
    def __init__(self, conn: Optional[sqlite3.Connection], spaces_client: Optional[Spaces]):
        self.conn = conn
        self.spaces_client = spaces_client

    @staticmethod
    def from_file(cfgpath: Union[str, pathlib.Path]) -> "Credentials":
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
        _log().debug("read credentials %s", _cfgpath)

        if "beholder" not in parser:
            raise AttributeError

        sqlite_path = parser.get("beholder", "sqlite", fallback=None)
        if sqlite_path is not None:
            connection: Optional[sqlite3.Connection] = sqlite3.connect(
                sqlite_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        else:
            connection = None

        try:
            spaces: Optional[Spaces] = Spaces.from_file(cfgpath)
        except Exception:
            spaces = None

        return Credentials(connection, spaces)


S_STARTUP = "startup"
S_HAS_WIFI = "has_wifi"
S_HAS_SPACE = "has_space"
S_RECORD = "record"
S_ERROR = "error"
S_RESTART = "restart"
class ControllerState:
    def __init__(self, initstate=S_STARTUP):
        self.state = initstate


class Controller:
    def __init__(self, config_path: pathlib.Path, credentials_path: pathlib.Path, verbose=None):
        self.verbose = verbose
        self.record_pool = Pool(max_workers=1)
        self.process_pool = Pool(max_workers=1)
        self.computer_vision_pool = Pool(max_workers=1)
        self.upload_pool = Pool(max_workers=1)
        self.config_path = config_path
        self.config = Configuration.from_file(self.config_path)
        if self.config.verbose is None:
            self.config.set_verbose(self.verbose)
        self.credentials: Credentials = Credentials.from_file(credentials_path)
        self.interval_collection: Optional[IntervalCollection] = self.refresh_interval_collection()
        self.record_times: Optional[RecordTime] = self.refresh_record_times()

        self.record_process: Optional[subprocess.Popen] = None
        self.process_future: Optional[Future] = None
        self.computer_vision_future: Optional[Future] = None
        self.upload_future: Optional[Future] = None
        self.config_signals()
        self.context = pyudev.Context()
        self.handling_usb = False
        self.config_usb_listener()

        self.controller_state = ControllerState()
        self.last_restart = datetime.datetime.now()

    # --------------------------------------------------------------------------
    # State Machine Stuff
    # --------------------------------------------------------------------------
    def run(self) -> bool:
        if self.controller_state.state == S_ERROR:
            exit()
        elif self.controller_state.state == S_STARTUP:

            hdd = psutil.disk_usage("/")
            total = int(hdd.total / (2**30))
            used = int(hdd.used / (2**30))
            _log().info("%d GB of %d GB used", used, total)

            # if self.check_wifi():
            self.controller_state.state = S_HAS_WIFI
            self.run()
            # else:
            #     self.controller_state.state = S_ERROR
        elif self.controller_state.state == S_HAS_WIFI:
            if self.check_space():
                self.controller_state.state = S_HAS_SPACE
                self.run()
            else:
                self.controller_state.state = S_ERROR
        elif self.controller_state.state == S_HAS_SPACE:
            if self.check_devices():
                self.controller_state.state = S_RECORD
                self.run()
            else:
                self.controller_state.state = S_ERROR
        elif self.controller_state.state == S_RECORD:
            self.record()
            self.start_process()
            self.start_upload()
            self.start_computer_vision()
            while True:
                time.sleep(10)
                self.interval_collection = self.refresh_interval_collection()
                self.record_times = self.refresh_record_times()
                now = datetime.datetime.now()
                if self.is_blackout_datetime(now) or not self.is_record_time(now):
                    self.stop_record()
                else:
                    time_running = datetime.datetime.now() - self.last_restart
                    if time_running.total_seconds() > self.config.restart_seconds:
                        self.stop_record()
                    if self.record_process is None or self.record_process.poll() is not None:
                        self.config.refresh_devices()
                        self.record()
                    if self.process_future is None or self.process_future.done:
                        self.start_process()
                    if self.upload_future is None or self.upload_future.done:
                        self.start_upload()
                    if self.computer_vision_future is None or self.computer_vision_future.done:
                        self.start_computer_vision()
        return True

    def check_wifi(self) -> bool:
        try:
            requests.get("http://digitalocean.com", timeout=10)
            return True
        except (requests.ConnectionError, requests.Timeout):
            _log().error("not connected to internet")
            return False

    def check_space(self) -> bool:
        return True

    def check_devices(self) -> bool:
        has_devices = len(self.config.devices) > 0
        if not has_devices:
            _log().error("no devices plugged in")
        return has_devices

    # --------------------------------------------------------------------------
    # Handle OS Events: how to shutdown gracefully & recover from unplugged usb
    # --------------------------------------------------------------------------

    def config_signals(self):
        signal.signal(signal.SIGINT, self.handle_sigint)

    def handle_sigint(self, signum, frame):
        self.shutdown()
        exit()

    def stop_record(self):
        _log().info("Program has decided to stop recording")
        if self.record_process is not None:
            self.record_process.send_signal(signal.SIGINT)

    def shutdown(self):
        _log().info("trying to shut down gstreamer")
        self.stop_record()
        self.process_pool.shutdown(wait=False)
        self.upload_pool.shutdown(wait=False)
        self.computer_vision_pool.shutdown(wait=False)
        self.computer_vision_pool.shutdown(wait=False)
        _log().info("shut down sucessfully")
        time.sleep(1)
        pid = os.getpid()
        os.kill(pid, signal.SIGKILL)

    def config_usb_listener(self):
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by(subsystem='video4linux')
        observer = pyudev.MonitorObserver(monitor, callback=self.handle_usb, name='usb-observer')
        observer.start()

    def handle_usb(self, device):
        _log().warn("USB: %s -> %s", device.action, device.device_path)
        if not self.handling_usb and self.record_process is not None and\
           (device.action == "remove" or device.action == "add"):
            try:
                subprocess.call(["reboot"])
            except Exception:
                pass
            self.handling_usb = True
            self.record_process.kill()
            self.sleep(5)
            self.config.refresh_devices()
            self.record_process = None
            self.handling_usb = False

    # --------------------------------------------------------------------------
    # User Preferences
    # --------------------------------------------------------------------------

    def refresh_interval_collection(self):
        icol = None
        if self.credentials.conn is not None:
            icol = IntervalCollection.from_sql(self.credentials.conn.cursor())
        return icol

    def refresh_record_times(self):
        icol = None
        if self.credentials.conn is not None:
            icol = RecordTime.from_sql(self.credentials.conn.cursor())
        return icol

    def is_blackout_datetime(self, dt: datetime.datetime):
        if self.interval_collection is not None:
            return self.interval_collection.point_overlaps(dt)

    def is_record_time(self, dt: datetime.datetime):
        if self.record_times is not None:
            if len(self.record_times.intervals) == 0:
                return True
            return self.record_times.point_overlaps(dt.time())

    # --------------------------------------------------------------------------
    # Main Controller Code: record, process, upload
    # --------------------------------------------------------------------------
    def record(self):
        self.last_restart = datetime.datetime.now()
        self.record_process = record(self.config)

    def start_computer_vision(self):
        if self.config.loopback_enabled:
            self.computer_vision_future = self.computer_vision_pool.submit(self.computer_vision)
            self.computer_vision_future.add_done_callback(self.computer_vision_done)

    def computer_vision(self):
        return computer_vision(self.config, self.upload_detection_logs)

    def computer_vision_done(self, future):
        if future.exception() is not None:
            _log().error("uncaught computer_vision exception %s", future.exception(), exc_info=True)
        else:
            _log().info("computer vision result %s", future.result())

    def start_process(self):
        self.process_future = self.process_pool.submit(self.process)
        self.process_future.add_done_callback(self.process_done)

    def process(self):
        return process_all(self.config, self.interval_collection)

    def process_done(self, future):
        if future.exception() is not None:
            _log().error("uncaught processing exception %s", future.exception(), exc_info=True)
        else:
            _log().info("processed %d videos", future.result())

    def start_upload(self):
        self.upload_future = self.upload_pool.submit(self.upload)
        self.upload_future.add_done_callback(self.upload_done)

    def upload(self):
        return upload_all(self.config, self.credentials.spaces_client, self.interval_collection)

    def upload_done(self, future):
        if future.exception() is not None:
            _log().error("uncaught processing exception %s", future.exception(), exc_info=True)
        else:
            _log().info("uploaded %s videos", future.result())

    # --------------------------------------------------------------------------
    # Logging Stuff
    # --------------------------------------------------------------------------
    def upload_logs(self):
        if self.credentials.spaces_client is None: return
        log_path = pathlib.Path("logs")
        for log in log_path.glob("log.*"):
            key = (
                f"{self.config.spaces_root_key}/"
                f"{self.config.user_config['participant_id']}/"
                f"logs/{log.name}")
            self.credentials.spaces_client.upload(log, key)
            log.unlink()

    def upload_detection_logs(self):
        pass
