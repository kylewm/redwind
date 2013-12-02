
from fabric.api import *
from fabric.context_managers import prefix
from fabric.contrib.console import confirm

env.hosts = [ 'groomsman@orin.kylewm.com' ]

def prepare_deploy():
    local("git add -p && git commit")
    local("git push origin master")

def update_server():
    with cd("~/groomsman"):
        with prefix("source venv/bin/activate"):
            run("git pull origin master")
            run("pip install -r requirements.txt")
            run("uwsgi --reload /tmp/groomsman.pid")

def deploy():
    prepare_deploy()
    update_server()
    
