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
        '\n'.join([
            '<div class="h-entry">',
            '<h1 class="p-name">Lorem ipsum dolor sit amet, consectetur adipiscing elit. Fusce non ultricies nulla. Quisque a tristique massa. Nullam eu mi dapibus, dictum diam vel, sodales nulla. Nulla lobortis lacus a odio mattis, tincidunt aliquet risus semper. Proin laoreet magna nec elit scelerisque gravida. Quisque nec sollicitudin eros, et gravida libero. Sed ac vehicula velit, non aliquam diam. Suspendisse tincidunt mi et justo sagittis, vitae auctor dui malesuada. Donec aliquet volutpat ex, nec molestie mauris porttitor imperdiet. Integer laoreet tellus in arcu maximus, sit amet suscipit augue consequat. Suspendisse sit amet nulla nec ante venenatis finibus in ac elit.</h1>',
            '<div class="e-content">',
            '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis in tincidunt lectus, tincidunt mattis mi. Fusce vitae sollicitudin diam, rhoncus euismod ex. Vestibulum vehicula metus sed massa sagittis, a molestie tortor tristique. Integer vel scelerisque tellus. Fusce ornare cursus arcu, dapibus faucibus dui lacinia in. Morbi mattis commodo sem, accumsan mollis turpis ornare nec. Etiam tempus odio a tincidunt sagittis. Phasellus quis sodales libero. Quisque semper feugiat dui, id tempus nisl aliquam quis. Quisque venenatis ullaumcorper neque, ut cursus risus auctor at. Mauris a suscipit sapien. Duis eget malesuada eros. Donec nec massa id odio sodales eleifend nec sagittis justo.</p>',
            '<p>Donec quis ligula leo. Sed vulputate egestas suscipit. Aliquam a eleifend risus. Suspendisse a iaculis justo. Fusce vitae aliquet justo. Maecenas ac turpis facilisis, lacinia libero ut, vulputate ex. Pellentesque pretium convallis ligula volutpat sodales. Aliquam erat volutpat. Integer non libero sed lorem placerat rutrum a eu turpis. Sed iaculis massa ac condimentum commodo. Praesent erat massa, iaculis eget mauris sit amet, dignissim dictum nisl. Ut tempor tincidunt vestibulum.</p>',
            '<p>Suspendisse eu mi posuere, viverra quam quis, faucibus quam. In quis arcu urna. Cras at lectus id sapien volutpat efficitur eu sed sapien. Maecenas at ante eros. Nulla eu mauris et dolor dignissim congue eu sed diam. Proin quam orci, malesuada eu quam a, porta commodo arcu. Aliquam non nunc tincidunt, mattis ipsum eu, lobortis justo. Donec rutrum ac massa at efficitur.</p>',
            '<p>Proin lobortis mi eu tellus molestie facilisis. Ut rhoncus placerat gravida. Suspendisse eu placerat eros, a iaculis lorem. Nulla id risus mauris. Vivamus sodales dui ac risus bibendum egestas. Pellentesque at condimentum ipsum, a iaculis nunc. Fusce commodo sodales justo eget facilisis. Donec vulputate, ex id tincidunt sollicitudin, urna justo luctus neque, sed efficitur tellus lorem ac tortor. Suspendisse potenti. Mauris non venenatis erat. Quisque massa ligula, euismod eu hendrerit ut, aliquam nec orci. Suspendisse vel est elementum, aliquet mi quis, sollicitudin ex. Maecenas lobortis felis bibendum, laoreet metus sed, facilisis diam. Sed facilisis arcu non lectus tristique placerat. Duis semper eget dui eu suscipit. Ut eleifend viverra est, ac ultrices leo pretium sit amet.</p>',
            '<p>Nullam nec lobortis massa, in bibendum turpis. Praesent nec dolor et neque volutpat viverra eu eget ex. Morbi a dui viverra, cursus turpis sit amet, pulvinar felis. Ut orci massa, eleifend et sagittis nec, convallis malesuada ligula. Phasellus accumsan laoreet dolor, vel lacinia turpis vestibulum vitae. Proin vitae augue sit amet dolor pellentesque eleifend in eu justo. Morbi pharetra auctor risus, vel finibus est tincidunt egestas. Aenean ac justo ac turpis accumsan maximus quis id metus. Suspendisse a lectus congue, suscipit enim a, laoreet tortor. Maecenas congue lobortis dui non suscipit. Sed a ex at ipsum volutpat vehicula. Duis ex augue, vestibulum porta lorem quis, varius imperdiet quam. Nam ut dui a elit finibus aliquam.</p>',
            '</div>',
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
        (('title', 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Fusce non ultricies nulla. Quisque a tristique massa. Nullam eu mi dapibus, dictum diam vel, sodales nulla. Nulla lobortis lacus a odio mattis, tincidunt aliquet risus semper. Proin laoreet magna nec elit scelerisque gravida. Quisque nec sollicitudin eros, et gravida libero. Sed ac vehicula velit, non aliquam diam. Suspendisse tincidunt mi et justo sagittis, vitae auctor dui malesuada. Donec aliquet volutpat ex, nec molestie mauris porttitor imperdiet'),
         ('url', 'http://example.com'),
         ('permalink', 'http://example.com'),
         ('author_name', ''),
         ('author_url', ''),
         ('author_image', None),
         ('content', '\n'.join([
            '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis in tincidunt lectus, tincidunt mattis mi. Fusce vitae sollicitudin diam, rhoncus euismod ex. Vestibulum vehicula metus sed massa sagittis, a molestie tortor tristique. Integer vel scelerisque tellus. Fusce ornare cursus arcu, dapibus faucibus dui lacinia in. Morbi mattis commodo sem, accumsan mollis turpis ornare nec. Etiam tempus odio a tincidunt sagittis. Phasellus quis sodales libero. Quisque semper feugiat dui, id tempus nisl aliquam quis. Quisque venenatis ullaumcorper neque, ut cursus risus auctor at. Mauris a suscipit sapien. Duis eget malesuada eros. Donec nec massa id odio sodales eleifend nec sagittis justo.</p>',
            '<p>Donec quis ligula leo. Sed vulputate egestas suscipit. Aliquam a eleifend risus. Suspendisse a iaculis justo. Fusce vitae aliquet justo. Maecenas ac turpis facilisis, lacinia libero ut, vulputate ex. Pellentesque pretium convallis ligula volutpat sodales. Aliquam erat volutpat. Integer non libero sed lorem placerat rutrum a eu turpis. Sed iaculis massa ac condimentum commodo. Praesent erat massa, iaculis eget mauris sit amet, dignissim dictum nisl. Ut tempor tincidunt vestibulum.</p>',
            '<p>Suspendisse eu mi posuere, viverra quam quis, faucibus quam. In quis arcu urna. Cras at lectus id sapien volutpat efficitur eu sed sapien. Maecenas at ante eros. Nulla eu mauris et dolor dignissim congue eu sed diam. Proin quam orci, malesuada eu quam a, porta commodo arcu. Aliquam non nunc tincidunt, mattis ipsum eu, lobortis justo. Donec rutrum ac massa at efficitur.</p>',
            '<p>Proin lobortis mi eu tellus molestie facilisis. Ut rhoncus placerat gravida. Suspendisse eu placerat eros, a iaculis lorem. Nulla id risus mauris. Vivamus sodales dui ac risus bibendum egestas. Pellentesque at condimentum ipsum, a iaculis nunc. Fusce commodo sodales justo eget facilisis. Donec vulputate, ex id tincidunt sollicitudin, urna justo luctus neque, sed efficitur tellus lorem ac tortor. Suspendisse potenti. Mauris non venenatis erat. Quisque massa ligula, euismod eu hendrerit ut, aliquam nec orci. Suspendisse vel est elementum, aliquet mi quis, sollicitudin ex. Maecenas lobortis felis bibendum, laoreet metus sed, facilisis diam. Sed facilisis arcu non lectus tristique placerat. Duis semper eget dui eu suscipit. Ut eleifend viverra est, ac ultrices leo pretium sit amet.</p>',
            '<p>Nullam nec lobortis massa, in bibendum turpis. Praesent nec dolor et neque volutpat viverra eu eget ex. Morbi a dui viverra, cursus turpis sit amet, pulvinar felis. Ut orci massa, eleifend et sagittis nec, convallis malesuada ligula. Phasellus accumsan laoreet dolor, vel lacinia turpis vestibulum vitae. Proin vitae augue sit amet dolor pellentesque eleifend in eu justo. Morbi pharetra auctor risus, vel finibus est tincidunt egestas. Aenean ac justo ac turpis accumsan maximus quis id metus. Suspendisse a lectus congue, suscipit enim a, laoreet tortor. Maecenas congue lobortis dui non suscipit. Sed a ex at ipsum volutpat vehicula. Duis ex augue, vestibulum porta lorem quis, varius imperdiet quam. Nam ut dui a elit finibus aliquam.</p>'])),
         ('content_plain', '\n'.join([
            'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis in tincidunt lectus, tincidunt mattis mi. Fusce vitae sollicitudin diam, rhoncus euismod ex. Vestibulum vehicula metus sed massa sagittis, a molestie tortor tristique. Integer vel scelerisque tellus. Fusce ornare cursus arcu, dapibus faucibus dui lacinia in. Morbi mattis commodo sem, accumsan mollis turpis ornare nec. Etiam tempus odio a tincidunt sagittis. Phasellus quis sodales libero. Quisque semper feugiat dui, id tempus nisl aliquam quis. Quisque venenatis ullaumcorper neque, ut cursus risus auctor at. Mauris a suscipit sapien. Duis eget malesuada eros. Donec nec massa id odio sodales eleifend nec sagittis justo.',
            'Donec quis ligula leo. Sed vulputate egestas suscipit. Aliquam a eleifend risus. Suspendisse a iaculis justo. Fusce vitae aliquet justo. Maecenas ac turpis facilisis, lacinia libero ut, vulputate ex. Pellentesque pretium convallis ligula volutpat sodales. Aliquam erat volutpat. Integer non libero sed lorem placerat rutrum a eu turpis. Sed iaculis massa ac condimentum commodo. Praesent erat massa, iaculis eget mauris sit amet, dignissim dictum nisl. Ut tempor tincidunt vestibulum.',
            'Suspendisse eu mi posuere, viverra quam quis, faucibus quam. In quis arcu urna. Cras at lectus id sapien volutpat efficitur eu sed sapien. Maecenas at ante eros. Nulla eu mauris et dolor dignissim congue eu sed diam. Proin quam orci, malesuada eu quam a, porta commodo arcu. Aliquam non nunc tincidunt, mattis ipsum eu, lobortis justo. Donec rutrum ac massa at efficitur.',
            'Proin lobortis mi eu tellus molestie facilisis. Ut rhoncus placerat gravida. Suspendisse eu placerat eros, a iaculis lorem. Nulla id risus mauris. Vivamus sodales dui ac risus bibendum egestas. Pellentesque at condimentum ipsum, a iaculis nunc. Fusce commodo sodales justo eget facilisis. Donec vulputate, ex id tincidunt sollicitudin, urna justo luctus neque, sed efficitur tellus lorem ac tortor. Suspendisse potenti. Mauris non venenatis erat. Quisque massa ligula, euismod eu hendrerit ut, aliquam nec orci. Suspendisse vel est elementum, aliquet mi quis, sollicitudin ex. Maecenas lobortis felis bibendum, laoreet metus sed, facilisis diam. Sed facilisis arcu non lectus tristique placerat. Duis semper eget dui eu suscipit. Ut eleifend viverra est, ac ultrices leo pretium sit amet.',
            'Nullam nec lobortis massa, in bibendum turpis. Praesent nec dolor et neque volutpat viverra eu eget ex. Morbi a dui viverra, cursus turpis sit amet, pulvinar felis. Ut orci massa, eleifend et sagittis nec, convallis malesuada ligula. Phasellus accumsan laoreet dolor, vel lacinia turpis vestibulum vitae. Proin vitae augue sit amet dolor pellentesque eleifend in eu justo. Morbi pharetra auctor risus, vel finibus est tincidunt egestas. Aenean ac justo ac turpis accumsan maximus quis id metus. Suspendisse a lectus congue, suscipit enim a, laoreet tortor. Maecenas congue lobortis dui non suscipit. Sed a ex at ipsum volutpat vehicula. Duis ex augue, vestibulum porta lorem quis, varius imperdiet quam. Nam ut dui a elit finibus aliquam.'])),
         ('published', None),
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
        FakeResponse(''),
        None,
    ]
    test_output = [
        (('title','Hello, world!'),
         ('permalink','http://example.com'),
         ('url','http://example.com')),
        (('title','Hello, world!'),
         ('permalink','http://example.com'),
         ('url','http://example.com')),
        (('title',None),
         ('permalink','http://example.com'),
         ('url','http://example.com')),
        (('title',None),
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
