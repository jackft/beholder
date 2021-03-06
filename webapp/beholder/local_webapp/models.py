from flask_security import UserMixin, RoleMixin

from .db import db

class RolesUsers(db.Model):
    __tablename__ = 'roles_users'
    __table_args__ = {}
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column('user_id', db.Integer(), db.ForeignKey('user.id'))
    role_id = db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))

class Role(db.Model, RoleMixin):
    __tablename__ = 'role'
    __table_args__ = {}
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    __table_args__ = {}
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    username = db.Column(db.String(255))
    password = db.Column(db.String(255))
    last_login_at = db.Column(db.DateTime())
    current_login_at = db.Column(db.DateTime())
    last_login_ip = db.Column(db.String(100))
    current_login_ip = db.Column(db.String(100))
    login_count = db.Column(db.Integer)
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship(
        'Role',
        secondary='roles_users',
        backref=db.backref('users', lazy='dynamic')
    )

#===============================================================================
# Calendar
#===============================================================================

class BlackoutInterval(db.Model):
    __tablename__ = 'blackout_interval'
    __table_args__ = {}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column('user_id', db.Integer(), db.ForeignKey('user.id'))
    title = db.Column(db.String(255))
    description = db.Column(db.String(255))
    start = db.Column(db.DateTime)
    end = db.Column(db.DateTime)

class Timezone(db.Model):
    __tablename__ = 'timezone'
    __table_args__ = {}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column('user_id', db.Integer(), db.ForeignKey('user.id'))
    tz = db.Column(db.String(255))

class RecordTime(db.Model):
    __tablename__ = 'recordtime'
    __table_args__ = {}
    id = db.Column(db.Integer, primary_key=True)
    activated = db.Column(db.Boolean())
    start = db.Column(db.Time)
    end = db.Column(db.Time)
    user_id = db.Column('user_id', db.Integer(), db.ForeignKey('user.id'))
