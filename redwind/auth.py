from .extensions import login_mgr
from .models import User


@login_mgr.user_loader
def load_user(id):
    return User.query.get(id)
