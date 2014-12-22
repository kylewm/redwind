import pystache
from redwind.models import Post
from sqlalchemy import desc
import isodate

FEED_TEMPLATE = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{{{title}}}</title>
    <style>

body {
  font-family: sans-serif;
  max-width:800px;
}

h1,h2,h3,h4 {
  font-size: 1em;
}

li {
  list-style: none;
}

.p-category {
  list-style: none;
  border: 1px solid #ddd;
  border-radius:2px;
  display: inline;
  padding: 2px;
  margin: 5px;
}

.dt-published {
  margin-top:1em;
}
    </style>

  </head>
  <body class="h-feed">
    <h1 class="p-name">{{{title}}}</h1>
    <ul>
    {{#bookmarks}}
      <li class="h-entry">
        <h2 class="p-bookmark h-cite"><a href="{{bookmark}}">{{title}}</a></h2>
        {{#content}}<div class="e-content">{{{.}}}</div>{{/content}}
        {{#categories}}<span class="p-category">{{.}}</span>{{/categories}}
        <div class="dt-published">{{published}}</div>
      </li>
    {{/bookmarks}}
    </ul>
  </body>
</html>
"""

blob = {
    'title': 'Kylewm&rsquo;s Bookmarks',
    'bookmarks': []
}


for bmark in Post.query.filter_by(post_type='bookmark').order_by(desc(Post.published)).all():
    blob['bookmarks'].append({
        'title': bmark.bookmark_contexts[0].title,
        'bookmark': bmark.bookmark_of[0],
        'content': bmark.content_html,
        'categories': [t.name for t in bmark.tags],
        'published': isodate.datetime_isoformat(bmark.published),
    })

print(pystache.render(FEED_TEMPLATE, blob))
