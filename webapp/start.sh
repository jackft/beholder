#!/bin/bash
# start.sh

export FLASK_APP=wsgi.py
export FLASK_DEBUG=1
export APP_CONFIG_FILE=config.py


email=`jq -r '.["email"]' /srv/beholder_configuration/config.json`
.venv/bin/flask init-db
.venv/bin/flask users create $email --password `openssl rand -base64 32` --active || echo "bingo"

.venv/bin/uwsgi --ini uwsgi.ini 2>&1
