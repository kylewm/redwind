
from fabric.api import local, settings, abort, run, cd
from fabric.contrib.console import confirm

def prepare_deploy():
    local("git add -p && git commit")
    local("git push origin master")

def deploy():
    prepare_deploy()
    with cd("~/groomsman"):
        run("git pull origin master")
        run(". venv/bin/activate")
        run("pip install -r requirements.txt")
        run("uwsgi --reload /tmp/groomsman.pid")
