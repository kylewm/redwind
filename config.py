
class Configuration(object):
    DEBUG = False
    PROFILE = False

    SQLALCHEMY_DATABASE_URI = 'sqlite:///temp.db'
    SECRET_KEY = 'this is a secret key'
    PYGMENTS_STYLE = 'tango'
    PROD_URL = 'http://boiling-plateau-1247.herokuapp.com/'
    SITE_URL = 'http://boiling-plateau-1247.herokuapp.com/'
    SHORT_SITE_URL = 'http://kyl.im'
    SHORT_SITE_CITE = 'kyl.im'
    TIMEZONE = 'America/Los_Angeles'
    #PUSH_HUB = 'https://kylewm.superfeedr.com'

    POSTS_PER_PAGE = 15
    TWITTER_CONSUMER_KEY = "fDgucAioywOuHD1CuopX0w"
    TWITTER_CONSUMER_SECRET = "cHKvrgJFMvYaU4DEMLAhYWHvZxyfIZoO3JFHqYvE"
    FACEBOOK_APP_ID = "458928027540466"
    FACEBOOK_APP_SECRET = "548f22dcd5910dc910e85f7d9ea535a2"

    PLUGINS = [
        'facebook',
        'locations',
        'push',
        'reader',
        'twitter',
        'wm_receiver',
        'wm_sender',
    ]
