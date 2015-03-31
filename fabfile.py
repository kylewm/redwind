from fabric.api import local, prefix, cd, run, env, lcd, sudo
import datetime

env.hosts = ['orin.kylewm.com']

REMOTE_PATH = '/srv/www/kylewm.com/redwind'


def backup():
    backup_dir = '~/Backups/kylewm.com/{}/'.format(
        datetime.date.isoformat(datetime.date.today()))
    local('mkdir -p ' + backup_dir)
    local('scp orin.kylewm.com:kylewm.com.db ' + backup_dir)


def commit():
    local("git add -p")
    local("git diff-index --quiet HEAD || git commit")


def push():
    local("git push origin master")


def pull():
    with cd(REMOTE_PATH):
        run("git pull origin master")
        run("git submodule update")


def restart():
    with cd(REMOTE_PATH):
        with prefix("source venv/bin/activate"):
            run("pip install --upgrade -r requirements.txt")
            # run("uwsgi --reload /tmp/redwind.pid")
            # run("supervisorctl restart rw:*")
        sudo("restart redwind")


def tail():
    sudo("tail -n 60 -f /var/log/upstart/redwind.log")


def deploy():
    commit()
    push()
    pull()
    restart()
