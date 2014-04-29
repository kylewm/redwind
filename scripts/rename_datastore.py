import os
import re
import subprocess
from redwind import util

os.chdir('redwind/_data')

DATADIR = '.'
POSTSDIRS = ('article', 'note', 'checkin', 'like', 'reply', 'share')

for postdir in POSTSDIRS:
    for root, dirs, files in os.walk(postdir):
        for fn in files:
            # type_idx.format
            # type_idx.mentions.json

            oldfn = os.path.join(root, fn)
            newfn = None

            m = re.match("(\w+)\.md$", fn)
            if m:
                idx = int(m.group(1))

                newfn = os.path.join(os.path.dirname(oldfn), util.base60_encode(idx) + '.md')
                print('moving', oldfn, "to", newfn)
            else:
                m = re.match("(\w+)\.mentions\.json", fn)
                if m:
                    idx = int(m.group(1))
                    newfn = os.path.join(os.path.dirname(oldfn), util.base60_encode(idx) + '.mentions.json')
                    print('moving', oldfn, 'to', newfn)

            if oldfn and newfn and oldfn != newfn:
                if not os.path.exists(os.path.dirname(newfn)):
                    os.makedirs(os.path.dirname(newfn))
                subprocess.check_call(['git', 'mv', oldfn, newfn])
                #os.renames(oldfn, newfn)
