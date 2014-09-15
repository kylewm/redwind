from . import login_mgr
from .models import User


@login_mgr.user_loader
def load_user(domain):
    user = User.load(domain)
    if user:
        user.authenticated = True
        return user
    else:
        # guest user
        return User(domain)
