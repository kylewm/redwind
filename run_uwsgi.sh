#!/bin/sh
uwsgi --master --processes 4  -s /tmp/uwsgi.sock -w main:app -H venv/ --chmod-socket=666 --pidfile /tmp/red-wind.pid
