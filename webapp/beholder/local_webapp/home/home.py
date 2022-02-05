"""General page routes."""
import psutil
from dateutil.parser import parse
import datetime
from flask.helpers import make_response, send_file
import pathlib
import pytz

from flask import Blueprint, render_template, jsonify, request
from flask import current_app as app
from flask_security import login_required
from flask_login import current_user

from beholder.local_webapp.models import BlackoutInterval, RecordTime
from beholder.local_webapp.db import db

# Blueprint Configuration
home_bp = Blueprint(
    'home_bp', __name__,
    template_folder='templates',
    static_folder='static'
)

def get_events():
    events = [
        {
            "id": e.id,
            "start": pytz.utc.localize(e.start).isoformat(),
            "end": pytz.utc.localize(e.end).isoformat(),
            "title": e.title
        } for e in BlackoutInterval.query.all()]
    app.logger.info("events %s", events)
    return events

@home_bp.route('/events/<id>', methods=['GET', 'PUT', 'DELETE'])
def event(id):
    bi = BlackoutInterval.query.get(id)
    if request.method == 'GET':
        return jsonify({"id": bi.id, "start": bi.start, "end": bi.end, "title": bi.title})
    elif request.method == 'PUT':
        row = request.json
        app.logger.info("put %s", row)
        bi.start = parse(row["start"])
        bi.end = parse(row["end"])
        bi.title = row["title"]
        db.session.commit()
        return jsonify(sucsess=True)
    elif request.method == 'DELETE':
        db.session.delete(bi)
        db.session.commit()
        return jsonify(sucsess=True)

@home_bp.route('/events', methods=['GET', 'POST'])
def events():
    if request.method == 'POST':
        row = request.json
        app.logger.info("recieved new blackout %s", row)
        bi = BlackoutInterval(
            title = row["title"],
            start = parse(row["start"]),
            end = parse(row["end"])
        )
        db.session.add(bi)
        db.session.commit()
        return jsonify(success=True, id=bi.id)
    elif request.method == 'GET':
        events = get_events()
        return jsonify(events)

# ------------------------------------------------------------------------------
# Live
# ------------------------------------------------------------------------------

@home_bp.route('/live/<path:path>', methods=['GET'])
@login_required
def livestream(path):
    response = make_response(send_file(pathlib.Path(app.config["LIVESTREAM_PATH"]) / path))
    response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response

@home_bp.route('/live', methods=['GET'])
@login_required
def live():
    return render_template(
        "live.jinja2",
        title="live",
        hls=True,
        user=current_user)

# ------------------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------------------

def get_settings_recordtime(user_id: int):
    ut = db.session.query(RecordTime).filter(RecordTime.user_id==user_id).first()
    app.logger.info("recordtime: %s", ut)
    return ut

@home_bp.route('/settings/recordtime', methods=['GET', 'PUT'])
def settings_recordtime():
    _time = get_settings_recordtime(current_user.id)
    if request.method == 'PUT':
        row = request.json
        app.logger.info("recieved new record time %s", row)
        if _time is None:
            offset = datetime.timedelta(minutes=int(row["offset"]))
            time = RecordTime(
                start = (parse(row["start"]) + offset).time(),
                end = (parse(row["end"]) + offset).time(),
                activated = row["activated"],
                user_id = current_user.id
            )
            db.session.add(time)
            db.session.commit()
            return jsonify(success=True, id=time.id)
        else:
            offset = datetime.timedelta(minutes=int(row["offset"]))
            _time.start = (parse(row["start"]) + offset).time()
            _time.end = (parse(row["end"]) + offset).time()
            _time.activated = row["activated"]
            db.session.commit()
            return jsonify(success=True, id=_time.id)
    elif request.method == 'GET':
        if _time is not None:
            return jsonify(
                {"start": _time.start.isoformat(),
                 "end": _time.end.isoformat(),
                 "activated": _time.activated})
        else:
            return jsonify(None)

@home_bp.route('/settings', methods=['GET'])
@login_required
def settings():
    recordtime = get_settings_recordtime(current_user.id)
    if recordtime is None:
        recordtime = RecordTime(
            start = parse("2:00pm").time(), #utc
            end = parse("5:00am").time(), #utc
            activated = False,
            user_id = current_user.id
        )
        db.session.add(recordtime)
        db.session.commit()
    recordstart = recordtime.start.isoformat()
    recordend = recordtime.end.isoformat()
    recordactivated = recordtime.activated
    hdd = psutil.disk_usage("/")
    total = int(hdd.total / (2**30))
    used = int(hdd.used / (2**30))
    return render_template(
        "settings.jinja2",
        title="settings",
        user=current_user,
        recordstart = recordstart,
        recordend = recordend,
        record_time_activated = recordactivated,
        hdd_used = used,
        hdd_total = total)

# ------------------------------------------------------------------------------
# Home
# ------------------------------------------------------------------------------

@home_bp.route('/', methods=['GET'])
@login_required
def home():
    """Homepage."""
    return render_template(
        "index.jinja2",
        title="home",
        user=current_user,
        events=get_events())
