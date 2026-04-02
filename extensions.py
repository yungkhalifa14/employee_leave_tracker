from flask_login import LoginManager
from flask_mail import Mail
from tracker import LeaveTracker

login_manager = LoginManager()
mail = Mail()
tracker = LeaveTracker()
