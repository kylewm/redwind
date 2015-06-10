import pytest
from datetime import datetime
from mf2util.dt import FixedOffset
from redwind import contexts
from redwind.models import Context

class FakeResponse():
    def __init__(self, text):
        self.text = text


def test_ogp_context():
    """ Check that we can get Open Graph Protocol data from a document
    """
    test_data = [
        ('\n'.join([
            '<meta property="og:title" content="Test Doc">',
            '<meta property="og:type" content="website">',
            '<meta property="og:image" content="test_image.png">',
            '<meta property="og:site_name" content="Example.com">',
            '<meta property="og:url" content="http://example.com">',
            '<meta property="og:description" content="This is a test document">',
        ]),
        [
            ('title','Test Doc'),
            ('author_image','test_image.png'),
            ('author_name','Example.com'),
            ('url','http://example.com'),
            ('permalink','http://example.com'),
            ('content','This is a test document'),
            ('content_plain','This is a test document'),
        ]),
        ('\n'.join([
            '<meta property="og:title" content="Test Doc">',
        ]),
        [
            ('title','Test Doc'),
            ('author_image',None),
            ('author_name',None),
            ('url',None),
            ('permalink',None),
            ('content',None),
            ('content_plain',None),
        ]),
    ]

    for doc,res in test_data:
        context = Context()
        context = contexts.extract_ogp_context(
            context=context,
            doc=doc,
            url="http://example.com"
        )

        for inp,out in res:
            assert out == getattr(context,inp)


def test_mf2_context(app):
    """ Check that we can get Microformats2 data from a document
    """
    test_input = [
        '', # empty test
        '\n'.join([
            '<div class="h-entry">',
            '<h1 class="p-name">Test Article</h1>',
            '<p class="e-content">Words words words</p>',
            '</div>',
        ]),
        '\n'.join([
            '<div class="h-entry">',
            '<p class="p-name e-content">Words words words</p>',
            '</div>',
        ]),
        '\n'.join([
            '<div class="h-entry">',
            '<h1 class="p-name">Test Article</h1>',
            '<div class="p-author h-card">',
            '<img class="u-photo" src="example.png">',
            '<a class="p-name u-url" href="http://example.com">Example Author</a>',
            '</div>',
            '<p>Published: <time class="dt-published" datetime="2015-06-10T10:00:00">June 10th, 2015 10:00am</time></p>',
            '<p class="e-content">Words words words</p>',
            '<a class="u-url" href="http://example.com/post1">permalink</a>',
            '</div>',
        ]),
    ]
    test_output = [
        (('title', None),
         ('url', None),
         ('permalink', None),
         ('author_name', None),
         ('author_url', None),
         ('author_image', None),
         ('content', None),
         ('content_plain', None),
         ('published', None),
        ),
        (('title', 'Test Article'),
         ('url', 'http://example.com'),
         ('permalink', 'http://example.com'),
         ('author_name', ''),
         ('author_url', ''),
         ('author_image', None),
         ('content', 'Words words words'),
         ('content_plain', 'Words words words'),
         ('published', None),
        ),
        (('title', None),
         ('url', 'http://example.com'),
         ('permalink', 'http://example.com'),
         ('author_name', ''),
         ('author_url', ''),
         ('author_image', None),
         ('content', 'Words words words'),
         ('content_plain', 'Words words words'),
         ('published', None),
        ),
        (('title', 'Test Article'),
         ('url', 'http://example.com'),
         ('permalink', 'http://example.com/post1'),
         ('author_name', 'Example Author'),
         ('author_url', 'http://example.com'),
         ('author_image', 'http://example.com/example.png'),
         ('content', 'Words words words'),
         ('content_plain', 'Words words words'),
         ('published', datetime(2015,6,10,10,0)),
        ),
    ]

    for inp,out in zip(test_input, test_output):
        context = Context()
        context = contexts.extract_mf2_context(
            context=context,
            doc=inp,
            url='http://example.com'
        )

        for k,v in out:
            assert v == getattr(context, k)


def test_default_context(app):
    """ Check that we can get basic website data as a fallback
    """
    test_input = [
        FakeResponse('<title>Hello, world!</title>'),
        FakeResponse('\n'.join([
            '<html>',
            '<head>',
            '<title>Hello, world!</title>',
            '</head>',
            '<body>',
            '<title>Goodbye, world!</title>',
            '</body>',
            '</html>',
        ])),
    ]
    test_output = [
        (('title','Hello, world!'),
         ('permalink','http://example.com'),
         ('url','http://example.com')),
        (('title','Hello, world!'),
         ('permalink','http://example.com'),
         ('url','http://example.com')),
    ]

    for inp,out in zip(test_input, test_output):
        context = None
        context = contexts.extract_default_context(
            context=context,
            response=inp,
            url="http://example.com"
        )

        for k,v in out:
            assert v == getattr(context, k)
