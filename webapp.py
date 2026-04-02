import os
import dotenv
from flask import Flask
from db import init_db

from extensions import login_manager, mail, tracker
from blueprints.auth import auth_bp
from blueprints.dashboard import dashboard_bp
from blueprints.management import management_bp
# We must import load_user so that the decorator is registered by Flask-Login
from models import load_user

dotenv.load_dotenv()

app = Flask(__name__)
# Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'localhost')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 1025))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@leave-tracker.com')

# Security config
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me')

if os.environ.get('FLASK_ENV') == 'production':
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_HTTPONLY=True
    )

# Extension init
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
mail.init_app(app)

# DB initialization
init_db()
tracker.prefill_polish_holidays()

# Blueprint registration
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(management_bp)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', debug=debug_mode, port=port)
