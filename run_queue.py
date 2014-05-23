#!/usr/bin/env python
from redwind import app
from redwind import queue_daemon

queue_daemon.queue_daemon(app)
