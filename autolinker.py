# Copyright © 2013, 2014 Kyle Mahan
# This file is part of Red Wind.
#
# Red Wind is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Red Wind is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Red Wind.  If not, see <http://www.gnu.org/licenses/>.


import re

TWITTER_USERNAME_REGEX = r'(?<!\w)@([a-zA-Z0-9_]+)'
LINK_REGEX = r'\b(?<!=.)https?://([a-zA-Z0-9/\.\-_:%?@$#&=]+)'


def make_links(plain):
    plain = re.sub(LINK_REGEX,
                   r'<a href="\g<0>">\g<1></a>', plain)
    plain = re.sub(TWITTER_USERNAME_REGEX,
                   r'<a href="http://twitter.com/\g<1>">\g<0></a>', plain)
    return plain
