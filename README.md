# Intro

Red Wind is a (micro)-blogging engine used on my personal website,
kylewm.com. I have been using it to screw around with
[IndieWeb](http://indiewebcamp.com) ideas like POSSE (Twitter and
Facebook), microformats, webmentions (sending and receiving).

The name comes from the great Raymond Chandler short story, the first
paragraph of which is one my favorite things ever:

> There was a desert wind blowing that night. It was one of those hot
> dry Santa Ana's that come down through the mountain passes and curl
> your hair and make your nerves jump and your skin itch. On nights
> like that every booze party ends in a fight. Meek little wives feel
> the edge of the carving knife and study their husbands'
> necks. Anything can happen. You can even get a full glass of beer at
> a cocktail lounge.


# Disclaimer

I'm building Red Wind for my own personal use in exploring Indieweb
ideas and technologies. The documentation is bad or non-existent, and
there are not good tests or testing procedures. I make widespread and
irresponsible changes and break things, frequently.

It's decidedly not and may never be "ready for prime time".

That said, I do have a lot of my own data in this thing that I don't
want to lose, so I make an effort to do proper migrations and avoid
breaking anything *permanently* :) I'm very willing to help others who
want to mess around with it and am open to suggestions. I'm kylewm in
the #indiewebcamp channel on Freenode IRC if you want to discuss.


# Installation

[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy?template=https://github.com/kylewm/redwind)

# Requirements

Python 3.3+, Flask, uWSGI, SQLite (MySQL or Postgres should also
work), and Redis. See requirements.txt for details.
