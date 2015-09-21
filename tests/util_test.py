import pytest
from redwind.models import Contact, Nick
from redwind import util

TEST_CONTACTS = [
    ('Luke Skywalker',
     'http://tatooine.com/moseisley',
     'http://tatooine.com/luke.jpg',
     {'twitter': 'luke14', 'facebook': 'luke.skywalker'},
     ['luke']),
    ('Princess Leia',
     'http://aldera.an',
     'http://aldera.an/leia.png',
     {'twitter': 'princess_leia'},
     ['leia', 'princess']),
    ('Han Solo',
     'https://millennium.falcon',
     'https://millennium.falcon/parsecs.gif',
     {'twitter': 'ishotfirst', 'facebook': 'han.solo'},
     ['han']),
    ('Chewbacca',
     'https://millennium.falcon/chewie',
     'https://millennium.falcon/fuzzball.jpg',
     {'kashyyyk-konnect': 'chewie'},
     ['chewie'])
]


@pytest.fixture
def contacts(db):
    for c in TEST_CONTACTS:
        # create some contacts
        contact = Contact()
        contact.name = c[0]
        contact.url = c[1]
        contact.image = c[2]
        contact.social = c[3]
        contact.nicks = [Nick(name=n) for n in c[4]]
        db.session.add(contact)
    db.session.commit()


def test_autolink_simple():
    result = util.autolink('This is a simple link to http://example.com')
    assert result == 'This is a simple link to <a class="auto-link" href="http://example.com">http://example.com</a>'

    result = util.autolink('A link without a schema jason.com/friday13th maybe?')
    assert result == 'A link without a schema <a class="auto-link" href="http://jason.com/friday13th">jason.com/friday13th</a> maybe?'

    result = util.autolink('Shortened link is.gd/me for ex.')
    assert result == 'Shortened link <a class="auto-link" href="http://is.gd/me">is.gd/me</a> for ex.'


def test_convert_legacy_people_to_at_names(contacts):
    result = util.convert_legacy_people_to_at_names(
        'Hi [[Han Solo]] this is [[Chewbacca]] calling')
    assert result == 'Hi @han this is @chewie calling'


def test_autolink_no_consecutive_periods():
    result = util.autolink('and....now for something completely different')
    assert '<a' not in result


def test_autolink_word_boundaries():
    result = util.autolink('common.language runtime')
    assert '<a' not in result


def test_autolink_trailing_slash():
    result = util.autolink('http://hel.ly/world/')
    assert result == '<a class="auto-link" href="http://hel.ly/world/">http://hel.ly/world/</a>'


def test_no_autolink_in_code_block():
    result = util.markdown_filter("""
Don't autolink @-names or URLs inside a fenced code block.

```python
from flask import app
import requests
@app.route('/asdf')
def asdf():
    requests.get('http://example.com')
    return 'hello, world.'
```
""")
    assert '<a' not in result


def test_process_at_names(contacts, mocker):
    result = util.process_people_to_microcards("@luke this is @leia tell @obiwan he's our only hope!")
    assert result == """<a class="microcard h-card" href="http://tatooine.com/moseisley"><img alt="" src="/imageproxy?url=http%3A%2F%2Ftatooine.com%2Fluke.jpg&amp;size=24&amp;sig=97ad9f9406cf09a03a0c5ecc333de3d1" />Luke Skywalker</a> this is <a class="microcard h-card" href="http://aldera.an"><img alt="" src="/imageproxy?url=http%3A%2F%2Faldera.an%2Fleia.png&amp;size=24&amp;sig=f5803c340d2511eac014af8af029de2c" />Princess Leia</a> tell <a class="microcard h-card" href="https://twitter.com/obiwan">@obiwan</a> he's our only hope!"""


def test_autolink_urls():
    """Exercise the URL matching regex
    """
    test_cases = [
        ('this should be link.gy',
         'this should be <a class="auto-link" href="http://link.gy">link.gy</a>'),
        ('this should not be link.linked',
         'this should not be link.linked'),
        ('a link to is.gd/supplies, should end at the comma',
         'a link to <a class="auto-link" href="http://is.gd/supplies">is.gd/supplies</a>, should end at the comma'),
        ('A link to example.com/q?u=a75$qrst&v should not terminate early',
         'A link to <a class="auto-link" href="http://example.com/q?u=a75$qrst&v">example.com/q?u=a75$qrst&v</a> should not terminate early'),
        ('HTML links <a href="http://google.com">google.com</a> should not be affected',
         'HTML links <a href="http://google.com">google.com</a> should not be affected'),
        ('Neither should <code><pre>http://fenced.code/blocks</pre></code>',
         'Neither should <code><pre>http://fenced.code/blocks</pre></code>')
    ]

    for inp, out in test_cases:
        assert out == util.autolink(inp)


def test_autolink_people(db):
    """Exercise the @-name matching regex, without contacts
    """
    def simple_name_marker(contact, nick):
        return '<' + nick + '>'

    test_cases = [
        ('@han should be linked', '<han> should be linked'),
        ('chewbacca@chewie.com should not be',
         'chewbacca@chewie.com should not be'),
        ('@leia @luke @han', '<leia> <luke> <han>'),
        ('@leia@luke@han', '@leia@luke@han'),
        ('match a name at the end @kylewm',
         'match a name at the end <kylewm>'),
        ('match a name followed by a period @kylewm.',
         'match a name followed by a period <kylewm>.'),
        ('followed by a @comma, right?',
         'followed by a <comma>, right?'),
    ]

    for inp, out in test_cases:
        assert out == util.process_people(simple_name_marker, inp)


def test_parsing_hashtags():
    """Exercise the #-tag matching regex
    """

    test_cases = [
        ('#hashtag should be linked',
         '<a href="/tags/hashtag">#hashtag</a> should be linked',
         ['hashtag']),
        ('hashtag should not be linked',
         'hashtag should not be linked',
         []),
        ('match #hashtags in the middle',
         'match <a href="/tags/hashtags">#hashtags</a> in the middle',
         ['hashtags']),
        ('match a tag at the #end',
         'match a tag at the <a href="/tags/end">#end</a>',
         ['end']),
        ('#1 should not be linked',
         '#1 should not be linked',
         []),
        ('#12345 should be linked',
         '<a href="/tags/12345">#12345</a> should be linked',
         ['12345']),
        ('#.foobar should not be linked',
         '#.foobar should not be linked',
         []),
        ('#foo.bar should be partially linked',
         '<a href="/tags/foo">#foo</a>.bar should be partially linked',
         ['foo']),
        ('capital letters in #HashTags will be lowercased',
         'capital letters in <a href="/tags/hashtags">#HashTags</a> will be lowercased',
         ['hashtags']),
        ('duplicate #hashtags should parse both #hashtags fine',
         'duplicate <a href="/tags/hashtags">#hashtags</a> should parse both <a href="/tags/hashtags">#hashtags</a> fine',
         ['hashtags','hashtags']),
        ('Lorem ipsum dolor sit amet, consectetur adipiscing elit. Praesent tincidunt aliquam sem, in tempus elit lacinia vel. Integer accumsan cursus purus et euismod. Nullam ultricies nunc sit amet ante consequat porta. Pellentesque et porta odio. Sed et neque cursus, iaculis lorem nec, laoreet odio. Donec molestie volutpat vestibulum. Curabitur rhoncus elit ut massa pretium luctus. #Nullam sollicitudin ligula vitae tincidunt suscipit. Maecenas in neque porta, scelerisque metus at, mollis nunc. Fusce accumsan imperdiet velit, in tincidunt tellus aliquam ac. Nullam iaculis vel urna sed vulputate. Aliquam erat volutpat. Etiam et tortor turpis. Vivamus mattis enim lacus, in aliquet nulla blandit.',
         'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Praesent tincidunt aliquam sem, in tempus elit lacinia vel. Integer accumsan cursus purus et euismod. Nullam ultricies nunc sit amet ante consequat porta. Pellentesque et porta odio. Sed et neque cursus, iaculis lorem nec, laoreet odio. Donec molestie volutpat vestibulum. Curabitur rhoncus elit ut massa pretium luctus. <a href="/tags/nullam">#Nullam</a> sollicitudin ligula vitae tincidunt suscipit. Maecenas in neque porta, scelerisque metus at, mollis nunc. Fusce accumsan imperdiet velit, in tincidunt tellus aliquam ac. Nullam iaculis vel urna sed vulputate. Aliquam erat volutpat. Etiam et tortor turpis. Vivamus mattis enim lacus, in aliquet nulla blandit.',
         ['nullam']),
        ('this hash#tag will not be parsed',
         'this hash#tag will not be parsed',
         []),
        ('http://example.com/path#fragment',
         '<a class="auto-link" href="http://example.com/path#fragment">http://example.com/path#fragment</a>',
         []),
    ]

    for inp, out, tags in test_cases:
        ts = util.find_hashtags(inp)
        res = util.autolink(inp)
        assert out == res
        assert tags == ts
