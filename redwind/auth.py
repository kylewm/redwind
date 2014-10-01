from . import login_mgr
from .models import User


@login_mgr.user_loader
def load_user(domain):
    return User(domain)
