import re

TWITTER_USERNAME_REGEX = r'(?<!\w)@([a-zA-Z0-9_]+)'
LINK_REGEX = r'\b(?<!=.)https?://([a-zA-Z0-9/\.\-_:%?@$#&=]+)'


def make_links(plain):
    plain = re.sub(LINK_REGEX,
                   r'<a href="\g<0>">\g<1></a>', plain)
    plain = re.sub(TWITTER_USERNAME_REGEX,
                   r'<a href="http://twitter.com/\g<1>">\g<0></a>', plain)
    return plain
