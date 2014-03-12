#import sys
#sys.path.append('mf2py')

from collections import namedtuple
from mf2py.parser import Parser

Author = namedtuple('Author', ['name', 'url', 'photo'])
Reference = namedtuple('Reference', ['url', 'reftype'])
Entry = namedtuple('Entry', ['author', 'permalink', 'references', 'content'])


def parse_hentry(txt):
    def parse_references(objs, reftype):
        refs = []
        for obj in objs:
            if isinstance(obj, str):
                refs.append(Reference(obj, reftype))
            else:
                refs += [Reference(url, reftype) for url
                         in obj.get('properties', {}).get('url', [])]
        return refs

    def parse_author(objs):
        for obj in objs:
            if isinstance(obj, str):
                return Author(obj, None, None)
            else:
                names = obj['properties'].get('name')
                photos = obj['properties'].get('photo')
                urls = obj['properties'].get('url')
                return Author(names and names[0],
                              urls and urls[0],
                              photos and photos[0],)

    p = Parser(doc=txt)
    d = p.to_dict()
    references = []

    for rel, url in d['rels'].items():
        if rel in ('like', 'like-of'):
            references.append(Reference(url, 'like'))
        elif rel in ('reply', 'reply-to', 'in-reply-to'):
            references.append(Reference(url, 'reply'))

    for item in d['items']:
        if 'h-entry' in item['type']:
            hentry = item
            permalink = (next((perma for perma
                              in hentry['properties'].get('url', [])), None)
                         or url)
            references += parse_references(
                hentry['properties'].get('in-reply-to', []), 'reply')
            references += parse_references(
                hentry['properties'].get('like-of', []), 'like')
            content = ''.join(content['value'].strip() for content
                              in hentry['properties'].get('content', []))
            author = parse_author(
                hentry['properties'].get('author', []))
            return Entry(author, permalink, references, content)


if __name__ == '__main__':
    import requests
    urls = [
        'https://snarfed.org/2014-03-10_re-kyle-mahan',
        'https://brid-gy.appspot.com/like/facebook/12802152/10100820912531629/'
        '1347771058',
        'https://brid-gy.appspot.com/comment/googleplus/109622249060170703374/'
        'z12vyphidxaodbb0223qdj0pwkvuytpja04/'
        'z12vyphidxaodbb0223qdj0pwkvuytpja04.1334830661177000',
        'http://tantek.com/2014/030/t1/'
        'handmade-art-indieweb-reply-webmention-want']

    for url in urls:
        txt = requests.get(url).content
        print(parse_hentry(txt))
        print()
