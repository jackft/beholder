import click
from flask import current_app, g
from flask.cli import with_appcontext
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db():
    from . import models
    db.create_all()

def close_db(e=None):
    pass

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    db.init_app(app)
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(fill_db_command)


@click.command('fill-db')
@with_appcontext
def fill_db_command():
    """Fill the db with test data"""
    import pathlib
    from .models import Video, Camera, CamerasVideos, CameraGroup, Task, Provenance, VideoMetaData, TaskEnum

    for video in Video.query.all():
        task = Task(type="blah", status=TaskEnum.ready, video_id=video.id, created_by=0, assigned_to=2)
        db.session.add(task)
        db.session.commit()
        db.session.flush()


