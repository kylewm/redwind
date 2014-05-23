#!/bin/bash
celery multi start 1 -A redwind.celery -l debug --pidfile=/tmp/celery-%n.pid
