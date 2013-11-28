
from fabric.api import local, settings, abort, run, cd
from fabric.contrib.console import confirm

def prepare_deploy():
    local("git add -p && git commit")
    local("git push origin master")

def deploy():
    prepare_deploy()
    with cd("cd /srv/www/groomsman/public_html"):
        run("git pull origin master")
        run("sudo service groomsman restart")
