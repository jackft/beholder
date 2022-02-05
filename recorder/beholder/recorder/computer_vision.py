import cv2  # type: ignore
import datetime
import time
import logging

from typing import List, Tuple

import numpy as np  # type: ignore

from .configuration import Configuration
from .utils import _log, BackcallerTimedRotatingFileHandler


class MotionDetector():
    def __init__(self, height: int, width: int, learning_rate: float = 0.2):
        self.bgs = cv2.createBackgroundSubtractorMOG2()
        self.fgmask = np.zeros((height, width), np.uint8)
        self.learning_rate = learning_rate

        self.height = height
        self.widht = width
        self.percent_area = height * width / 5000

    def motion_bboxes(self, frame) -> List[Tuple[int, int, int, int]]:
        self.fgmask = self.bgs.apply(frame, self.fgmask, 0.5)
        _, absolute_difference = cv2.threshold(
            self.fgmask,
            100, 255,
            cv2.THRESH_BINARY)
        contours, hierarchy = cv2.findContours(
            absolute_difference,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE)[-2:]
        areas = [cv2.contourArea(c) for c in contours]
        return self.biggest_bounding_box(areas, contours)

    def biggest_bounding_box(self, areas, contours) -> List[Tuple[int, int, int, int]]:
        if len(areas) == 0: return []
        num_boxes = min(len(areas), 3)
        indices = np.argpartition(areas, -num_boxes)[-num_boxes:]
        return [
            cv2.boundingRect(contours[idx])
            for idx in indices
            if areas[idx] > self.percent_area
        ]


def computer_vision(config: Configuration, upload_detection_logs):
    time.sleep(2)
    if config.loopbackdevice is None:
        _log().info("No loopback device. Not running computer vision")
        return False

    # --------------------------------------------------------------------------
    # Setup Capture
    # --------------------------------------------------------------------------
    motion_detector = MotionDetector(config.loopback_height, config.loopback_width)
    cap = cv2.VideoCapture(config.loopback_number)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.loopback_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.loopback_height)
    _log().info("successfully opened computer loopback camera")
    # --------------------------------------------------------------------------
    # Setup Outputter
    # --------------------------------------------------------------------------
    motion_detection_directory = (
        config.output_directory / config.observation_id / "detections" / "motion_capture")
    motion_detection_directory.mkdir(exist_ok=True, parents=True)

    _cv_logger = logging.getLogger("cv_motion_rolling_csv_outputter")
    formatter = logging.Formatter(
        "%(message)s"
    )
    handler = BackcallerTimedRotatingFileHandler(
        motion_detection_directory / "log",
        when="M", interval=config.segment_time_seconds / 60, backupCount=0
    )
    handler.setFormatter(formatter)
    _cv_logger.addHandler(handler)
    _cv_logger.propagate = False
    _cv_logger.setLevel(logging.INFO)
    handler.callback = upload_detection_logs

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        now = datetime.datetime.now().timestamp()
        bboxes = motion_detector.motion_bboxes(frame)
        for bbox in bboxes:
            _cv_logger.info(
                "%s,%s,%s,%s,%s",
                now, bbox[0], bbox[1], bbox[2], bbox[3])
        time.sleep(1 / 5)
