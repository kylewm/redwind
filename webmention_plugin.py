from webmentiontools.send import WebmentionSend
from webmentiontools.urlinfo import UrlInfo
    
def handle_new_or_edit(post):
    url = post.permalink_url
    in_reply_to = post.in_reply_to
    if url and in_reply_to:
        print "Sending webmention {} to {}".format(url, in_reply_to)
        sender = WebmentionSend(url, in_reply_to)
        success = sender.send(verify=False)
        print "Finished sending webmention: ", success
        if success:
            print sender.response
        else:
            print sender.error
