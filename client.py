import argparse
import os
import json
from tempfile import NamedTemporaryFile
from subprocess import call
import urllib.request


EDITOR="emacs"
ROOT_URI="http://localhost:5000"
USER="kyle"
PASS="****"

POSTS_URI=ROOT_URI + "/api/v1.0/posts"

auth_handler = urllib.request.HTTPBasicAuthHandler()
auth_handler.add_password(realm='Groomsman', uri=ROOT_URI,
                          user=USER, passwd=PASS)
opener = urllib.request.build_opener(auth_handler)

def request_get(uri):
    reply = opener.open(uri)
    raw = reply.read().decode("UTF-8")
    data = json.loads(raw)
    return data
    
def request_post(uri, payload=None, method='POST'):
    data = None
    if payload:
        data = json.dumps(payload).encode('UTF-8')
    req = urllib.request.Request(url=uri, data=data,
                                 headers={'Content-Type' : 'application/json'},
                                 method=method)
    reply = opener.open(req)
    return reply.read()
    
def get_posts():
    json = request_get(POSTS_URI)
    post_cache = {}

    for index, post in enumerate(json['posts']):
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

def launch_editor(**kwargs):
    tempfile = None
    with NamedTemporaryFile(delete=False) as tf:
        for key in kwargs:
            if key != 'body':
                tf.write(bytes('{}: {}\n'.format(key, kwargs[key]), "UTF-8"))

        tf.write(bytes('\n', "UTF-8"))
        tf.write(bytes(kwargs['body'], "UTF-8"))
        tempfile = tf.name

    call([EDITOR, tempfile])

    payload = {}
    with open(tempfile, 'r') as tf:
        while True:
            line = tf.readline().strip()
            if not line:
                break
            key, value = line.split(':', 1)
            payload[key.strip()] = value.strip()
        payload['body'] = tf.read().strip()

    return payload
    
def create(args):
    edited = launch_editor(title="", body="")
    request_post(POSTS_URI, edited)
    print("Success!")

def edit(args):
    uri = get_post_uri(args.id)
    post = request_get(uri)
    edited = launch_editor(post)
    request_post(uri, edited, method='PUT')
    print("Success!")

def delete(args): 
    uri = get_post_uri(args.id)
    request_post(uri, method='DELETE')
    print("Success!")
   
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
    delete_parser.add_argument("id", type=int, help="Unique id of the post to delete")
    args = parser.parse_args()
    args.func(args)
