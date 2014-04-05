# Intro

Red Wind is a (micro)-blogging engine used on my personal website,
kylewm.com. I have been using it to screw around with
[IndieWeb](http://indiewebcamp.com) ideas like POSSE (Twitter and
Facebook), microformats, webmentions (sending and receiving).

The name comes from the great Raymond Chandler short story, the first paragraph of which is one my favorite things ever:

> There was a desert wind blowing that night. It was one of those hot dry Santa Ana's that come down through the mountain passes and curl your hair and make your nerves jump and your skin itch. On nights like that every booze party ends in a fight. Meek little wives feel the edge of the carving knife and study their husbands' necks. Anything can happen. You can even get a full glass of beer at a cocktail lounge.

# Requirements

Python 3.3, Flask, Redis (for the background queue). See requirements.txt for details.

# Running

I run Red Wind behind [Supervisor](http://supervisord.org) with the following configuration:

    [program:red-wind]
    directory=/home/kmahan/red-wind
    command=/home/kmahan/red-wind/venv/bin/uwsgi --master --processes 4  -s /tmp/uwsgi.sock -w main:app
              -H venv/ --chmod-socket=666
    user=kmahan

    [program:red-wind-queue]
    directory=/home/kmahan/red-wind
    command=/home/kmahan/red-wind/venv/bin/python queue_daemon.py
    user=kmahan
