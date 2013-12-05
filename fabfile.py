
from fabric.api import *
from fabric.context_managers import prefix
from fabric.contrib.console import confirm

env.hosts = [ 'groomsman@orin.kylewm.com' ]

def commit():
    local("git add -p && git commit")

def push():
    local("git push origin master")

def pull():
    with cd("~/groomsman"):
        run("git pull origin master")

def restart():
    with cd("~/groomsman"):
        with prefix("source venv/bin/activate"):
            run("pip install -r requirements.txt")
            run("uwsgi --reload /tmp/groomsman.pid")

def deploy():
    commit()
    push()
    pull()
    restart()
