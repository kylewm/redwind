# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.


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
