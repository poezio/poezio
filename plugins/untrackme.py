"""
    UntrackMe wannabe plugin
"""

from typing import Callable, Dict, List, Tuple, Union

import re
import logging
from slixmpp import Message
from poezio import tabs
from poezio.plugin import BasePlugin
from urllib.parse import quote as urlquote


log = logging.getLogger(__name__)

ChatTabs = Union[
    tabs.MucTab,
    tabs.DynamicConversationTab,
    tabs.StaticConversationTab,
    tabs.PrivateTab,
]

RE_URL: re.Pattern = re.compile('https?://(?P<host>[^/]+)(?P<rest>[^ ]*)')

SERVICES: Dict[str, Tuple[str, bool]] = {  # host: (service, proxy)
    'm.youtube.com': ('invidious', False),
    'www.youtube.com': ('invidious', False),
    'youtube.com': ('invidious', False),
    'youtu.be': ('invidious', False),
    'youtube-nocookie.com': ('invidious', False),
    'mobile.twitter.com': ('nitter', False),
    'www.twitter.com': ('nitter', False),
    'twitter.com': ('nitter', False),
    'pic.twitter.com': ('nitter_img', True),
    'pbs.twimg.com': ('nitter_img', True),
    'instagram.com': ('bibliogram', False),
    'www.instagram.com': ('bibliogram', False),
    'm.instagram.com': ('bibliogram', False),
}

def proxy(service: str) -> Callable[[str], str]:
    """Some services require the original url"""
    def inner(origin: str) -> str:
        return service + urlquote(origin)
    return inner


class Plugin(BasePlugin):
    """UntrackMe"""

    default_config: Dict[str, Dict[str, Union[str, bool]]] = {
        'default': {
            'cleanup': True,
            'redirect': True,
            'display_corrections': False,
        },
        'services': {
            'invidious': 'https://invidious.snopyta.org',
            'nitter': 'https://nitter.net',
            'bibliogram': 'https://bibliogram.art',
        },
    }

    def init(self):
        nitter_img = self.config.get('nitter', section='services') + '/pic/'
        self.config.set('nitter_img', nitter_img, section='services')

        self.api.add_event_handler('muc_say', self.handle_msg)
        self.api.add_event_handler('conversation_say', self.handle_msg)
        self.api.add_event_handler('private_say', self.handle_msg)

        self.api.add_event_handler('muc_msg', self.handle_msg)
        self.api.add_event_handler('conversation_msg', self.handle_msg)
        self.api.add_event_handler('private_msg', self.handle_msg)

    def map_services(self, match: re.Match) -> str:
        """
            If it matches a host that we know about, change the domain for the
            alternative service. Some hosts needs to be proxied instead (such
            as twitter pictures), so they're url encoded and appended to the
            proxy service.
        """

        host = match.group('host')

        dest = SERVICES.get(host)
        if dest is None:
            return match.group(0)

        destname, proxy = dest
        replaced = self.config.get(destname, section='services')
        result = replaced + match.group('rest')

        if proxy:
            url = urlquote(match.group(0))
            result = replaced + url

            # TODO: count parenthesis?
            # Removes comma at the end of a link.
            if result[-3] == '%2C':
                result = result[:-3] + ','

        return result

    def handle_msg(self, msg: Message, tab: ChatTabs) -> None:
        orig = msg['body']

        if self.config.get('cleanup', section='default'):
            msg['body'] = self.cleanup_url(msg['body'])
        if self.config.get('redirect', section='default'):
            msg['body'] = self.redirect_url(msg['body'])

        if self.config.get('display_corrections', section='default') and \
           msg['body'] != orig:
            log.debug(
                'UntrackMe in tab \'%s\':\nOriginal: %s\nModified: %s',
                tab.name, orig, msg['body'],
            )

            self.api.information(
                'UntrackMe in tab \'{}\':\nOriginal: {}\nModified: {}'.format(
                    tab.name, orig, msg['body']
                ),
                'Info',
            )

    def cleanup_url(self, txt: str) -> str:
        # fbclid: used globally (Facebook)
        # utm_*: used globally https://en.wikipedia.org/wiki/UTM_parameters
        # ncid: DoubleClick (Google)
        # ref_src, ref_url: twitter
        # Others exist but are excluded because they are not common.
        # See https://en.wikipedia.org/wiki/UTM_parameters
        return re.sub('(https?://[^ ]+)&?(fbclid|dclid|ncid|utm_source|utm_medium|utm_campaign|utm_term|utm_content|ref_src|ref_url)=[^ &#]*',
                             r'\1',
                             txt)

    def redirect_url(self, txt: str) -> str:
        return RE_URL.sub(self.map_services, txt)
