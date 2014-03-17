from fabric.api import local, prefix, cd, run, env


env.hosts = ['orin.kylewm.com']


def commit():
    local("git add -p")
    local("git diff-index --quiet HEAD || git commit")


def push():
    local("git push origin master")


def pull():
    with cd("~/red-wind"):
        run("git pull origin master")


def restart():
    with cd("~/red-wind"):
        with prefix("source venv/bin/activate"):
            run("pip install -r requirements.txt")
            run("uwsgi --reload /tmp/red-wind.pid")


def deploy():
    commit()
    push()
    pull()
    restart()
