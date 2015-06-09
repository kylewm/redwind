import pytest
from redwind import contexts
from redwind.models import Context

def test_ogp_context():
    """ Check that we can get Open Graph Protocol data from a document
    """
    test_doc = '\n'.join([
        '<meta property="og:title" content="Test Doc">',
        '<meta property="og:type" content="website">',
        '<meta property="og:image" content="test_image.png">',
        '<meta property="og:site_name" content="Example.com">',
        '<meta property="og:url" content="http://example.com">',
        '<meta property="og:description" content="This is a test document">',
    ])
    test_data = [
        ('title','Test Doc'),
        ('author_image','test_image.png'),
        ('author_name','Example.com'),
        ('url','http://example.com'),
        ('permalink','http://example.com'),
        ('content','This is a test document'),
        ('content_plain','This is a test document'),
    ]

    context = Context()
    context = contexts.extract_ogp_context(
        context=context,
        doc=test_doc,
        url="http://example.com"
    )

    for inp,out in test_data:
        assert out == getattr(context,inp)
