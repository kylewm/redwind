from fabric.api import local, prefix, cd, run, env, get


env.hosts = ['orin.kylewm.com']


def getdata():
    with cd("~/red-wind"):
        run("tar czvf data.tar.gz _data")
    get('~/red-wind/data.tar.gz', '.')
    local("tar zxvf data.tar.gz")


def commit():
    local("git add -p")
    local("git diff-index --quiet HEAD || git commit")


def push():
    local("git push origin master")


def pull():
    with cd("~/red-wind"):
        run("git pull origin master")
        run("git submodule update")


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
