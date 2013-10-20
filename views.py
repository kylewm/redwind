
from flask import request, redirect, url_for, render_template, flash

from app import *
from models import *

@app.route('/')
def index():
    posts = Post.query.all()
    return render_template('index.html', posts=posts)

@app.route("/css/pygments.css")
def pygments_css():
    import pygments.formatters
    pygments_css = (pygments.formatters.HtmlFormatter(style=app.config['PYGMENTS_STYLE'])
                    .get_style_defs('.codehilite'))
    return app.response_class(pygments_css, mimetype='text/css')
    
@app.template_filter('strftime')
def _jinja2_filter_strftime(date, fmt='%Y %b %d'):
    return date.strftime(fmt)
