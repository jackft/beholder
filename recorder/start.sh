#!/bin/bash
sleep 3
v4l2-ctl --list-devices > tmp.txt
.venv/bin/python -m beholder.recorder beholder.ini credentials.ini -l INFO --verbose
