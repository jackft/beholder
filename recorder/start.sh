#!/bin/bash
sleep 3
v4l2-ctl --list-devices > tmp.txt
.venv/bin/python -m beholder.recorder beholder.ini /srv/beholder_configuration/credentials.ini -l INFO --verbose
