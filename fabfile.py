from fabric.api import local, prefix, cd, run, env, lcd
import datetime

env.hosts = ['orin.kylewm.com']


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
    with cd("~/redwind"):
        run("git pull origin master")
        run("git submodule update")


def restart():
    with cd("~/redwind"):
        with prefix("source venv/bin/activate"):
            run("pip install -r requirements.txt")
            run("uwsgi --reload /tmp/redwind.pid")


def deploy():
    commit()
    push()
    pull()
    restart()
