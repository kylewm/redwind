import argparse
import requests
import os
import json
from tempfile import NamedTemporaryFile
from subprocess import call

EDITOR="emacs"
POSTS_URL="http://localhost:5000/api/v1.0/posts"
USER="kyle"
PASS="******"

post_cache = None

class ResponseException(Exception):
    def __init__(self, code):
        self.code = code

    def __repr__(self):
        return "ResponseException: {}".format(self.code)

def get_posts():
    global post_cache
    if post_cache:
        return post_cache
        
    r = requests.get(POSTS_URL)
    if r.status_code != requests.codes.ok:
        raise ResponseException(r.status_code)

    post_cache = {}
    for index, post in enumerate(r.json()['posts']):
        post_cache[index] = post

    return post_cache

def get_post(id):
    return get_posts()[id]

def get_post_uri(id):
    post = get_post(args.id)
    return post['uri']

def list(args):
    posts = get_posts()
    for key in sorted(posts.keys()):
        post = posts[key]
        print("id:", key)
        print("title:", post['title'])
        print("slug:", post['slug'])
        print("date:", post['pub_date'])
        print()

def create(args):
    pass

def edit(args):
    uri = get_post_uri(args.id)
    r = requests.get(uri)

    if r.status_code != requests.codes.ok:
        raise ResponseException(r.status_code)

    post = r.json()
    
    tempfile = None
    with NamedTemporaryFile(delete=False) as tf:
        tf.write(bytes('title: {}\n'.format(post['title']), "UTF-8"))
        tf.write(bytes('slug: {}\n'.format(post['slug']), "UTF-8"))
        tf.write(bytes('pub_date: {}\n\n'.format(post['pub_date']), "UTF-8"))
        tf.write(bytes(post['body'], "UTF-8"))
        tempfile = tf.name

    call([EDITOR, tempfile])

    payload = {}
    with open(tempfile, 'r') as tf:
        while True:
            line = tf.readline().strip()
            if not line:
                break
            key, value = line.split(':', 1)
            payload[key] = value
        payload['body'] = tf.read()

    os.unlink(tempfile)
    r = requests.put(uri, data=json.dumps(payload), auth=(USER, PASS), headers={'content-type': 'application/json'})
    if r.status_code == requests.codes.created:
        print("Success!")
    else:
        print("Failed with status code: ", r.status_code, "and response:", r.text)


def delete(args):
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="sub-command help")
    list_parser = subparsers.add_parser("list", help="List all existing posts")
    list_parser.set_defaults(func=list)
    create_parser = subparsers.add_parser("create", help="Create a new post")
    create_parser.set_defaults(func=create)
    edit_parser = subparsers.add_parser("edit", help="Edit an existing post")
    edit_parser.add_argument("id", type=int, help="Unique id of the post to edit")
    edit_parser.set_defaults(func=edit)
    delete_parser = subparsers.add_parser("delete", help="Delete an existing post")
    delete_parser.set_defaults(func=delete)
    args = parser.parse_args()
    args.func(args)
