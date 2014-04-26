import os
import re
import subprocess

os.chdir('redwind/_data')

DATADIR = '.'
POSTSDIR = 'posts'


for root, dirs, files in os.walk(POSTSDIR):
    for fn in files:
        # type_idx.format
        # type_idx.mentions.json

        path = root[len(POSTSDIR)+1:]
        oldfn = os.path.join(root, fn)
        newfn = None

        m = re.match("([a-z]+)_(\w+)\.([a-z]+)$", fn)
        if m:
            content_type = m.group(1)
            idx = m.group(2)
            ext = m.group(3)

            newfn = os.path.join(DATADIR, content_type, path, idx + '.md')
            print('moving', oldfn, "to", newfn)
        else:
            m = re.match("([a-z]+)_(\w+)\.mentions\.json", fn)
            if m:
                content_type = m.group(1)
                idx = m.group(2)
                newfn = os.path.join(DATADIR, content_type, path, idx + '.mentions.json')
                print('moving', oldfn, 'to', newfn)

        if oldfn and newfn:
            if not os.path.exists(os.path.dirname(newfn)):
                os.makedirs(os.path.dirname(newfn))
            subprocess.check_call(['git', 'mv', oldfn, newfn])
            #os.renames(oldfn, newfn)
