from .. import app
from .. import queue
from .. import archiver
from .. import views

from flask import render_template
import datetime
import json
import mf2util
import os


def register():
    pass


def load_subscriptions():
    feeds_path = os.path.join(app.root_path, '_data/feeds.json')
    if os.path.exists(feeds_path):
        feeds = json.load(open(feeds_path, 'r'))
        return feeds
    return []


@app.route('/reader/retrieve')
def reader_retrieve():
    feeds = load_subscriptions()
    for feed in feeds:
        queue.enqueue(retrieve_feed, feed)

    return """<!DOCTYPE html><html>Retrieving feeds: <ul>{}</ul><a href="{}">Read!</a></html>""".format(
        '\n'.join('<li>{}</li>'.format(feed) for feed in feeds), '/reader')


def retrieve_feed(url):
    archiver.archive_url(url)


@app.route('/reader')
def reader_handler():
    def get_pub_date(entry):
        result = entry.get('published') or entry.get('start')
        if not result:
            result = datetime.datetime(1982, 11, 24, tzinfo=datetime.timezone.utc)
        if isinstance(result, datetime.date) and not isinstance(result, datetime.datetime):
            result = datetime.datetime.combine(result, datetime.time())
        if result and hasattr(result, 'tzinfo') and not result.tzinfo:
            result = result.replace(tzinfo=datetime.timezone.utc)
        return result

    all_entries = []
    feeds = load_subscriptions()
    for feed in feeds:
        json = archiver.load_json_from_archive(feed)
        if json:
            for entry in mf2util.interpret_feed(json, feed)['feed']:
                entry['human-time'] = views.human_time(
                    entry.get('published') or entry.get('start'))
                all_entries.append(entry)

    all_entries.sort(key=get_pub_date, reverse=True)
    return render_template('reader.html', feed=all_entries)
