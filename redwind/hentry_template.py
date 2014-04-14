
def fill(author_url=None, author_name=None, author_image=None, pub_date=None,
         title=None, content=None, permalink=None):

    html = """<html><body><div class="h-entry">\n"""
    if author_name or author_image or author_url:
        html += """<div class="p-author h-card">\n"""
        if author_url:
            html += """<a class="u-url" href="{}">\n""".format(author_url)

        if author_image:
            html += """<img class="u-photo" src="{}" />\n""".format(author_image)

        if author_name:
            html += """<span class="p-name">{}</span>\n""".format(author_name)
        if author_url:
            html += "</a>\n"
        html += "</div>\n"

    if title:
        html += """<p class="p-name">{}</p>\n""".format(title)

    if pub_date:
        html += """<time class="dt-published">{}</time>\n""".format(pub_date)

    if content:
        html += """<div class="{}">{}</div>\n""".format("e-content" if title else "p-name e-content", content)

    if permalink:
        html += """<a class="u-url" href="{}">permalink</a><br/>\n""".format(permalink)

    html += "</div></body></html>\n"
