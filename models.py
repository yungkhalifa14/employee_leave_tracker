from flask_login import UserMixin
from extensions import login_manager, tracker

class User(UserMixin):
    def __init__(self, id, name, username, role, team_id):
        self.id = str(id)
        self.name = name
        self.username = username
        self.role = role
        self.team_id = team_id

@login_manager.user_loader
def load_user(user_id):
    u = tracker.get_user_by_id(int(user_id))
    if u:
        return User(id=u[0], name=u[1], username=u[2], role=u[4], team_id=u[6])
    return None
