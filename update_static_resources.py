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

response = requests.get("http://www.gravatar.com/avatar/767447312a2f39bec228c3925e3edf74?s=64", stream=True)
with open('static/img/users/kyle.jpg', 'wb') as f:
    shutil.copyfileobj(response.raw, f)
del response
