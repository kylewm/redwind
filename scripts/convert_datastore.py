import json
import os
import urllib.parse
from mf2py.parser import Parser


DATADIR = 'redwind/_data/oldposts'
POSTSDIR = 'redwind/_data/posts'


def parse_json_frontmatter(fp):
    depth = 0
    json_lines = []
    for line in fp:
        p = None
        quoted = False
        for c in line:
            if c == '"' and p != '\\':
                quoted = not quoted
            else:
                if not quoted:
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
            p = c
        json_lines.append(line)
        if depth == 0:
            break
    head = json.loads(''.join(json_lines))
    body = '\n'.join(fp.readlines()).strip()
    return head, body


def write_post(blob, outpath):
    body = blob.pop('content', None)
    fmt = blob.pop('format', 'plain')
    if fmt == 'markdown':
        ext = '.md'
    elif fmt == 'html':
        ext = '.html'
    elif fmt == 'plain':
        ext = '.txt'
    else:
        raise RuntimeError("unknown content format {}".format(fmt))

    if not os.path.exists(os.path.dirname(outpath)):
        os.makedirs(os.path.dirname(outpath))

    with open(outpath + ext, 'w') as f:
        json.dump(blob, f, indent=True)
        f.write('\n')
        if body:
            f.write(body)
            f.write('\n')


def url_to_path(url):
    parsed = urllib.parse.urlparse(url)
    return os.path.join(parsed.scheme,
                        parsed.netloc.strip('/'),
                        parsed.path.strip('/'))


def write_post_to_archive(blob, target_url):
    assert 'source' in blob

    html = """<html><body><div class="h-entry">\n"""
    author = blob.get('author')
    if author:
        html += """<div class="p-author h-card">\n"""
        if 'url' in author:
            html += """<a class="u-url" href="{}">\n""".format(author['url'])
        if 'image' in author:
            html += """<img class="u-photo" src="{}" />\n""".format(
                author['image'])
        if 'name' in author:
            html += """<span class="p-name">{}</span>\n""".format(author['name'])
        if 'url' in author:
            html += "</a>\n"
        html += "</div>\n"

    if 'title' in blob:
        html += """<p class="p-name">{}</p>\n""".format(blob['title'])

    if 'pub_date' in blob:
        html += """<time class="dt-published">{}</time>\n""".format(blob['pub_date'])

    reftype = blob.get('type')
    if reftype == 'reply':
        html += """<a href="{}" class="u-in-reply-to">in reply to</a>\n""".format(target_url)
    elif reftype == 'like':
        html += """<a href="{}" class="u-like-of">liked</a>\n""".format(target_url)
    elif reftype == 'repost':
        html += """<a href="{}" class="u-repost-of">reposted</a>\n""".format(target_url)
    elif reftype == 'reference':
        html += """<a href="{}">referenced</a>\n""".format(target_url)

    if 'content' in blob:
        html += """<div class="{}">{}</div>\n""".format("e-content" if 'title' in blob else "p-name e-content", blob['content'])

    for urlprop in ('permalink', 'source'):
        if urlprop in blob:
            html += """<a class="u-url" href="{}">permalink</a><br/>\n""".format(
                blob[urlprop])
            break

    html += "</div></body></html>\n"

    source = blob.get('source')
    permalink = blob.get('permalink') or source
    path = os.path.join('redwind/_data/archive', url_to_path(source))

    if not os.path.exists(path):
        os.makedirs(path)

    html_path = os.path.join(path, 'raw.html')
    parsed_path = os.path.join(path, 'parsed.json')

    if os.path.exists(html_path):
        print("{} already exists, skipping".format(html_path))
        return

    with open(html_path, 'w') as f:
        f.write(html)

    parser = Parser(doc=html, url=permalink)
    with open(parsed_path, 'w') as f:
        json.dump(parser.to_dict(), f, indent=True)


def convert_posts():
    all_mentions = []
    all_contexts = []

    for root, dirs, files in os.walk(DATADIR):
        for filename in files:
            path = os.path.join(root, filename)
            relpath = path[len(DATADIR)+1:]
            blob = json.load(open(path, 'r'))

            # these fields are redundant with the file name
            posttype = blob.pop('type', 'note')
            dateindex = blob.pop('date_index', 0)

            mentions = blob.pop('mentions', None)
            contexts = blob.pop('context', None)

            if contexts:
                if 'reply' in contexts:
                    blob['in_reply_to'] = [reply['source'] for reply
                                           in contexts['reply']]
                if 'share' in contexts:
                    blob['repost_of'] = [share['source'] for share
                                         in contexts['share']]
                if 'like' in contexts:
                    blob['like_of'] = [like['source'] for like
                                       in contexts['like']]

            outpath = os.path.join(POSTSDIR, relpath)
            write_post(blob, outpath)

            if mentions:
                target_url = ('http://kylewm.com/' + posttype + '/'
                              + os.path.dirname(relpath) + '/'
                              + str(dateindex))

                print("target-url", target_url)
                for mention in mentions:
                    all_mentions.append((mention, target_url))
                    #write_post_to_archive(mention, target_url)

                outpath = os.path.join(POSTSDIR, relpath + '.mentions.json')
                json.dump([mention['source'] for mention in mentions],
                          open(outpath, 'w'), indent=True)

            if contexts:
                for ctxtype in ('reply', 'share', 'like'):
                    for reply in contexts.get(ctxtype, []):
                        all_contexts.append(reply)
                        #write_post_to_archive(reply, None)

    for mention, target_url in all_mentions:
        write_post_to_archive(mention, target_url)

    for context in all_contexts:
        write_post_to_archive(context, None)
