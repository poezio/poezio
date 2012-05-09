from plugin import BasePlugin
import urllib.request
from urllib.parse import urlencode
import xhtml
import json

TARGET_LANG = 'en'

def translate(s, target=TARGET_LANG, source=''):
    f = urllib.request.urlopen('http://ajax.googleapis.com/ajax/services/language/translate', urlencode({ 'v': '1.0', 'q': s, 'langpair': '%s|%s' % (source, target) }).encode('utf-8'))
    response = json.loads(str(f.read(), 'utf-8'))['responseData']
    return (response['translatedText'], response['detectedSourceLanguage'])

class Plugin(BasePlugin):
    def init(self):
        self.add_event_handler('groupchat_message', self.on_groupchat_message)

    def on_groupchat_message(self, message):
        try:
            room_from = message.getMucroom()
            if message['type'] == 'error':
                return

            if room_from in self.config.options():
                target_lang = self.config.get(room_from, self.config.get('default', TARGET_LANG))
                nick_from = message['mucnick']
                body = xhtml.get_body_from_message_stanza(message)
                room = self.core.get_tab_by_name(room_from)
                text, lang = translate(body, target=target_lang)
                if lang != TARGET_LANG:
                    room.add_message(text, nickname=nick_from)
                    self.core.refresh_window()
        except Exception as e:
            import traceback
            self.core.information("Exception in translator! %s" % (traceback.format_exc(),))
