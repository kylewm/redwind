import requests
import pygments.formatters
import shutil

#['fruity', 'perldoc', 'trac', 'native', 'autumn', 'emacs', 'vs',
#'rrt', 'colorful', 'monokai', 'pastie', 'default', 'borland',
#'manni', 'vim', 'bw', 'friendly', 'tango', 'murphy']
PYGMENTS_STYLE = 'tango'
pygments_css = (pygments.formatters.HtmlFormatter(style=PYGMENTS_STYLE)
                .get_style_defs('.codehilite'))
with open('static/css/pygments.css', 'w') as f:
    f.write(pygments_css)


def curl(url, file):
    response = requests.get(url, stream=True)
    with open(file, 'wb') as f:
        shutil.copyfileobj(response.raw, f)
        del response

curl('http://www.gravatar.com/avatar/767447312a2f39bec228c3925e3edf74?s=64',
     'static/img/users/kyle.jpg')

curl('http://www.gravatar.com/avatar/767447312a2f39bec228c3925e3edf74?s=128',
     'static/img/users/kyle_large.jpg')
