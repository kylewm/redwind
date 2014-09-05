from fabric.api import local, prefix, cd, run, env, lcd

env.hosts = ['orin.kylewm.com']


def getdata():
    # remote data is stored in central repository at
    # git@orin.kylewm.com:kylewm.com-data.git
    with cd("~/redwind/redwind/_data"):
        run("git add -A")
        run("git diff-index --quiet HEAD || git commit -m \"Commit by fabric\"")
        run("git push origin master")

    with cd("~/redwind/redwind/_archive"):
        run("git add -A")
        run("git diff-index --quiet HEAD || git commit -m \"Commit by fabric\"")
        run("git push origin master")

    with lcd("./redwind/_data"):
        local("git checkout -- .")
        local("git clean -df")
        local("git pull origin master")

    with lcd("./redwind/_archive"):
        local("git checkout -- .")
        local("git clean -df")
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
