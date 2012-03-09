"""
Recreational plugin.

Message parser that can generate sentences based on what he has already seen
before.

"""
from plugin import BasePlugin
from random import choice
from re import split as rsplit
import pickle
import tabs

class Dico(object):
    def __init__(self):
        self.start_words = []
        self.end_words = []
        self.words = {}

    def add_next(self, word, next):
        w = self.words[word]
        if next in w:
            w[next] += 1
        else:
            w[next] = 1

    def add_word(self, word):
        if not word in self.words:
            self.words[word] = {}

    def select_next(self, word):
        d = sorted(self.words[word], key=lambda w: self.words[word][w], reverse=True)
        if not d:
            return ''
        nexts =  d[:10]
        for i in range(0, len(d) // 10):
            nexts.append(choice(d[9:]))
        return choice(nexts)

    def create_sentence(self, length):
        if not self.start_words:
            return ''
        current = choice(self.start_words)
        i = 1
        sent = current.capitalize()
        while current and self.words[current] and i < length:
            current = self.select_next(current)
            sent += " " + current
            i += 1
        return sent

    def save(self, fname):
        file = open(fname, 'wb')
        pickle.dump(self, file)
        file.close

spaces =  '   '
end_sentence = ['.', '?', '!']

def end_re():
    r = '('
    for i in end_sentence[:]:
        end_sentence.append('%s ' % i)
        i = '\%s'% i
        r += '%s$|%s |' % (i, i)
    r = r[:-1]
    r += ')'
    return r

end = end_re()


class Analyzer(object):
    dico = None
    def __init__(self):
        pass

    def parse(self, text):
        text = text.replace('\n', '')
        res = rsplit(end, text)
        for i in res[:]:
            if i == '':
                continue
            elif i in end_sentence:
                continue
            self.analyze(i)

    def analyze(self, text):
        prev = None
        for word in rsplit('[%s]'%spaces, text):
            if word in spaces: continue
            word = word.lower()
            self.dico.add_word(word)
            if prev:
                self.dico.add_next(prev, word)
            else:
                self.dico.start_words.append(word)
            prev = word

class Plugin(BasePlugin):
    def init(self):
        self.add_event_handler('groupchat_message', self.on_groupchat_message)
        self.add_tab_command(tabs.MucTab, 'random', self.command_random, '/random [n]\nRandom: Send a random message, if n is provided and is integer > 1, the message will have a maximum number of n words', None)
        self.add_tab_command(tabs.MucTab, 'start', self.command_start, '/start\nStart: Start parsing the messages', None)
        self.add_tab_command(tabs.MucTab, 'stop', self.command_stop, '/stop\nStop: Stop parsing the messages', None)
        self.add_tab_command(tabs.MucTab, 'flush', self.command_flush, '/flush\nFlush: Flush the database', None)
        self.add_tab_command(tabs.MucTab, 'save', self.command_save, '/save <filepath>\nSave: Save the database to a file', None)
        self.add_tab_command(tabs.MucTab, 'load_db', self.command_load_db, '/load_db <filepath>\nLoad: Load the database from a file', None)
        self.tabs = {}
        self.analyzer = Analyzer()

    def command_start(self, arg):
        name = self.core.current_tab().get_name()
        if not name in self.tabs:
            self.tabs[name] = Dico()
            self.core.information('Started analyzing in %s' % name, 'Info')
        else:
            self.core.information('Already started', 'Info')

    def command_stop(self, arg):
        name = self.core.current_tab().get_name()
        if name in self.tabs:
            del self.tabs[name]
            self.core.information('Stopped analyzing in %s' % name, 'Info')
        else:
            self.core.information('Nothing to stop', 'Info')

    def command_save(self, arg):
        name = self.core.current_tab().get_name()
        if name in self.tabs:
            try:
                self.tabs[name].save(arg)
            except:
                self.core.information('Could not save the file', 'Info')
        else:
            self.core.information('Nothing to save', 'Info')

    def command_flush(self, arg):
        name = self.core.current_tab().get_name()
        if name in self.tabs:
            del self.tabs[name]
            self.tabs[name] = Dico()
            self.core.information('Database flushed', 'Info')
        else:
            self.core.information('Nothing to flush', 'Info')

    def command_load_db(self, arg):
        name = self.core.current_tab().get_name()
        try:
            file = open(arg, 'rb')
            self.tabs[name] = pickle.load(file)
            file.close()
            self.core.information('File loaded', 'Info')
        except:
            self.core.information('Could not load the file', 'Info')

    def on_groupchat_message(self, message):
        if not message['body']:
            return
        jid = message['from']
        if jid.bare not in self.tabs or jid.resource == self.core.current_tab().own_nick:
            return
        jid = jid.bare

        self.analyzer.dico = self.tabs[jid]
        self.analyzer.parse(message['body'])

    def command_random(self, arg):
        name = self.core.current_tab().get_name()
        try:
            i = int(arg)
            if i < 1:
                i = 1
        except:
            i = 25
        if name in self.tabs:
            self.core.send_message(self.tabs[name].create_sentence(i))
