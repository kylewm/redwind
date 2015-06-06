from redwind import create_app
from redwind import util
from redwind import admin
from redwind.models import Post, Attachment
from redwind.extensions import db
import os
import datetime
import random
import string
import mimetypes
import shutil
from flask import current_app

app = create_app()


def convert_file_to_attachment(post, filename):
    fullpath = os.path.join(current_app.root_path, '_data',
                            post.path, 'files', filename)
    if not os.path.exists(fullpath):
        print('could not find', fullpath)
        return
    now = post.published
    storage_path = '{}/{:02d}/{:02d}/{}'.format(
        now.year, now.month, now.day,
        ''.join(random.choice(string.ascii_letters + string.digits)
                for _ in range(8)) + '-' + filename)
    mimetype, _ = mimetypes.guess_type(filename)
    attachment = Attachment(filename=filename,
                            mimetype=mimetype,
                            storage_path=storage_path)

    print(attachment.disk_path)
    os.makedirs(os.path.dirname(attachment.disk_path), exist_ok=True)
    shutil.copy2(fullpath, attachment.disk_path)
    post.attachments.append(attachment)


with app.app_context():
    for post in Post.query.all():
        for a in post.attachments:
            if os.path.exists(a.disk_path):
                os.remove(a.disk_path)
            db.session.delete(a)

        if not post.photos:
            # check for files
            filedir = os.path.join(
                current_app.root_path, '_data', post.path, 'files')
            if os.path.exists(filedir):
                for filename in os.listdir(filedir):
                    convert_file_to_attachment(post, filename)
        else:
            for photo in (post.photos or []):
                filename = photo.get('filename')
                convert_file_to_attachment(post, filename)
    db.session.commit()
