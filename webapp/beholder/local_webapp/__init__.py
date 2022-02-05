"""Initialize Flask app."""
import sys
from flask import Flask, g
from flask_mail import Mail
from flask_security import Security, login_required, \
     SQLAlchemySessionUserDatastore, utils
from flask_security.forms import RegisterForm

def create_app():
    """Create Flask application."""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object('config.Config')

    with app.app_context():
        from .db import db
        from .db import init_app as db_init_app
        db_init_app(app)
        from .models import User, Role
        user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
        security = Security(app, user_datastore)
        mail = Mail(app)

        ## Import parts of our application
        from .home import home
        app.register_blueprint(home.home_bp)

        return app

