from fabric.api import local, prefix, cd, run, env, get, lcd


env.hosts = ['orin.kylewm.com']


def getdata():
    with cd("~/redwind/redwind/_data"):
        run("git add -A")
        run("git diff-index --quiet HEAD || git commit -m \"Commit by fabric\"")
    with lcd("./redwind/_data"):
        local("git pull origin master")


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
