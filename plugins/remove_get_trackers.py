"""
Remove GET trackers from URLs in sent messages.
"""
from poezio.plugin import BasePlugin
import re

class Plugin(BasePlugin):
    def init(self):
        self.api.add_event_handler('muc_say', self.remove_get_trackers)
        self.api.add_event_handler('conversation_say', self.remove_get_trackers)
        self.api.add_event_handler('private_say', self.remove_get_trackers)

    def remove_get_trackers(self, msg, tab):
        # fbclid: used globally (Facebook)
        # utm_*: used globally https://en.wikipedia.org/wiki/UTM_parameters
        # ncid: DoubleClick (Google)
        # ref_src, ref_url: twitter
        # Others exist but are excluded because they are not common.
        # See https://en.wikipedia.org/wiki/UTM_parameters
        msg['body'] = re.sub('(https?://[^ ]+)&?(fbclid|dclid|ncid|utm_source|utm_medium|utm_campaign|utm_term|utm_content|ref_src|ref_url)=[^ &#]*',
                             r'\1',
                             msg['body'])
