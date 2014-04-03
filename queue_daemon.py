#!/usr/bin/env python
from redwind import app
from redwind.queue import run_daemon

run_daemon(app)
