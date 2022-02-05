import cv2  # type: ignore
import datetime
import time
import pathlib
import logging
import sys

from typing import List, Tuple

import numpy as np  # type: ignore

from utils import _log, BackcallerTimedRotatingFileHandler, setup_logging

class MotionDetector():
    def __init__(self, height: int, width: int, learning_rate: float = 0.2):
        self.bgs = cv2.createBackgroundSubtractorMOG2()
        self.fgmask = np.zeros((height, width), np.uint8)
        self.learning_rate = learning_rate

        self.height = height
        self.widht = width
        self.percent_area = (height * width) / 5000
        print(self.percent_area)

    def motion_bboxes(self, frame) -> List[Tuple[int, int, int, int]]:
        frame = cv2.resize(frame,(640,480),fx=0,fy=0, interpolation = cv2.INTER_CUBIC)
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
        bboxes = self.biggest_bounding_box(areas, contours)
        for bbox in bboxes:
            print(bbox)
            cv2.rectangle(frame,(bbox[0],bbox[1]),(bbox[0]+bbox[2],bbox[1]+bbox[3]),(0,255,0),2)
        cv2.imshow("Show",frame)
        if cv2.waitKey(25) & 0xFF == ord('q'):
            exit()
        return bboxes



    def biggest_bounding_box(self, areas, contours) -> List[Tuple[int, int, int, int]]:
        if len(areas) == 0: return []
        l = min(len(areas), 3)
        indices = np.argpartition(areas, -l)[-l:]
        return [
            cv2.boundingRect(contours[idx])
            for idx in indices
            if areas[idx] > self.percent_area
        ]

def computer_vision(video, height, width):
    # --------------------------------------------------------------------------
    # Setup Capture
    # --------------------------------------------------------------------------
    motion_detector = MotionDetector(height, width)
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    # --------------------------------------------------------------------------
    # Setup Outputter
    # --------------------------------------------------------------------------
    motion_detection_directory = pathlib.Path("log")
    motion_detection_directory.mkdir(exist_ok=True, parents=True)

    _cv_logger = logging.getLogger("cv_motion_rolling_csv_outputter")
    formatter = logging.Formatter(
        "%(message)s"
    )
    handler = BackcallerTimedRotatingFileHandler(
        motion_detection_directory / "log",
        when="M", interval=15, backupCount=0
    )
    handler.setFormatter(formatter)
    _cv_logger.addHandler(handler)
    _cv_logger.propagate = False
    _cv_logger.setLevel(logging.INFO)
    i = 0
    while True:
        i += 1
        ret, frame = cap.read()
        if i % (30//5) != 0: continue
        if not ret:
            break
        now = datetime.datetime.now().timestamp()
        bboxes = motion_detector.motion_bboxes(frame)
        for bbox in bboxes:
            _cv_logger.info(
                "%s,%s,%s,%s,%s",
                now, bbox[0], bbox[1], bbox[2], bbox[3])

if __name__ == "__main__":
    setup_logging(logging.INFO, "log/log", 3)
    height=1440
    width=2560
    video=sys.argv[1]
    computer_vision(video, height, width)
