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
    assert result == 'This is a simple link to <a href="http://example.com">example.com</a>'

    result = util.autolink('A link without a schema jason.com/friday13th maybe?')
    assert result == 'A link without a schema <a href="http://jason.com/friday13th">jason.com/friday13th</a> maybe?'

    result = util.autolink('Shortened link is.gd/me for ex.')
    assert result == 'Shortened link <a href="http://is.gd/me">is.gd/me</a> for ex.'


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


def test_autolink_at_names(contacts, mocker):
    mirror = mocker.patch('redwind.util.mirror_image')
    mirror.side_effect = lambda src, side: src

    result = util.autolink("@luke this is @leia tell @obiwan he\'s our only help!")
    assert result == """<a class="microcard h-card" href="http://tatooine.com/moseisley"><img src="http://tatooine.com/luke.jpg"/>Luke Skywalker</a> this is <a class="microcard h-card" href="http://aldera.an"><img src="http://aldera.an/leia.png"/>Princess Leia</a> tell <a href="https://twitter.com/obiwan">@obiwan</a> he's our only help!"""
