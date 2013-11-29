from webmentiontools.send import WebmentionSend
from webmentiontools.urlinfo import UrlInfo
    
def handle_new_or_edit(post):
    url = post.permalink_url
    info = UrlInfo(url)
    in_reply_to = info.inReplyTo()
    
    if url and in_reply_to:
        sender = WebmentionSend(url, in_reply_to)
        sender.send()
