"""
Module for the ConversationTabs

A ConversationTab is a direct chat between two JIDs, outside of a room.

There are two different instances of a ConversationTab:
- A DynamicConversationTab that used to implement XEP-0296 (best
    practices for resource locking), which now stays on the bare JID at
    any time. This is the default.
- A StaticConversationTab that will stay focused on one resource all
    the time.

"""
import logging
log = logging.getLogger(__name__)

import curses

from poezio.tabs.basetabs import OneToOneTab, Tab

from poezio import common
from poezio import windows
from poezio import xhtml
from poezio.common import safeJID
from poezio.config import config
from poezio.decorators import refresh_wrapper
from poezio.roster import roster
from poezio.text_buffer import CorrectionError
from poezio.theming import get_theme, dump_tuple
from poezio.decorators import command_args_parser


class ConversationTab(OneToOneTab):
    """
    The tab containg a normal conversation (not from a MUC)
    Must not be instantiated, use Static or Dynamic version only.
    """
    plugin_commands = {}
    plugin_keys = {}
    additional_information = {}
    message_type = 'chat'

    def __init__(self, core, jid):
        OneToOneTab.__init__(self, core, jid)
        self.nick = None
        self.nick_sent = False
        self.state = 'normal'
        self.name = jid  # a conversation tab is linked to one specific full jid OR bare jid
        self.text_win = windows.TextWin()
        self._text_buffer.add_window(self.text_win)
        self.upper_bar = windows.ConversationStatusMessageWin()
        self.input = windows.MessageInput()
        # keys
        self.key_func['^I'] = self.completion
        # commands
        self.register_command(
            'version',
            self.command_version,
            desc=
            'Get the software version of the current interlocutor (usually its XMPP client and Operating System).',
            shortdesc='Get the software version of the user.')
        self.register_command(
            'info',
            self.command_info,
            shortdesc='Get the status of the contact.')
        self.register_command(
            'last_activity',
            self.command_last_activity,
            usage='[jid]',
            desc='Get the last activity of the given or the current contact.',
            shortdesc='Get the activity.',
            completion=self.core.completion.last_activity)
        self.register_command(
            'add',
            self.command_add,
            desc='Add the current JID to your roster, ask them to'
            ' allow you to see his presence, and allow them to'
            ' see your presence.',
            shortdesc='Add a user to your roster.')
        self.update_commands()
        self.update_keys()

    @property
    def general_jid(self):
        return safeJID(self.name).bare

    def get_info_header(self):
        raise NotImplementedError

    @staticmethod
    def add_information_element(plugin_name, callback):
        """
        Lets a plugin add its own information to the ConversationInfoWin
        """
        ConversationTab.additional_information[plugin_name] = callback

    @staticmethod
    def remove_information_element(plugin_name):
        del ConversationTab.additional_information[plugin_name]

    def completion(self):
        self.complete_commands(self.input)

    @command_args_parser.raw
    def command_say(self, line, attention=False, correct=False):
        msg = self.core.xmpp.make_message(self.get_dest_jid())
        msg['type'] = 'chat'
        msg['body'] = line
        if not self.nick_sent:
            msg['nick'] = self.core.own_nick
            self.nick_sent = True
        # trigger the event BEFORE looking for colors.
        # and before displaying the message in the window
        # This lets a plugin insert \x19xxx} colors, that will
        # be converted in xhtml.
        self.core.events.trigger('conversation_say', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        replaced = False
        if correct or msg['replace']['id']:
            msg['replace']['id'] = self.last_sent_message['id']
            if config.get_by_tabname('group_corrections', self.name):
                try:
                    self.modify_message(
                        msg['body'],
                        self.last_sent_message['id'],
                        msg['id'],
                        jid=self.core.xmpp.boundjid,
                        nickname=self.core.own_nick)
                    replaced = True
                except CorrectionError:
                    log.error('Unable to correct a message', exc_info=True)
        else:
            del msg['replace']
        if msg['body'].find('\x19') != -1:
            msg.enable('html')
            msg['html']['body'] = xhtml.poezio_colors_to_html(msg['body'])
            msg['body'] = xhtml.clean_text(msg['body'])
        if config.get_by_tabname('send_chat_states', self.general_jid):
            needed = 'inactive' if self.inactive else 'active'
            msg['chat_state'] = needed
        if attention:
            msg['attention'] = True
        self.core.events.trigger('conversation_say_after', msg, self)
        if not msg['body']:
            self.cancel_paused_delay()
            self.text_win.refresh()
            self.input.refresh()
            return
        if not replaced:
            self.add_message(
                msg['body'],
                nickname=self.core.own_nick,
                nick_color=get_theme().COLOR_OWN_NICK,
                identifier=msg['id'],
                jid=self.core.xmpp.boundjid,
                typ=1)

        self.last_sent_message = msg
        msg._add_receipt = True
        msg.send()
        self.cancel_paused_delay()
        self.text_win.refresh()
        self.input.refresh()

    @command_args_parser.quoted(0, 1)
    def command_last_activity(self, args):
        """
        /last_activity [jid]
        """
        if args and args[0]:
            return self.core.command.last_activity(args[0])

        def callback(iq):
            if iq['type'] != 'result':
                if iq['error']['type'] == 'auth':
                    self.core.information(
                        'You are not allowed to see the activity of this contact.',
                        'Error')
                else:
                    self.core.information('Error retrieving the activity',
                                          'Error')
                return
            seconds = iq['last_activity']['seconds']
            status = iq['last_activity']['status']
            from_ = iq['from']
            msg = '\x19%s}The last activity of %s was %s ago%s'
            if not safeJID(from_).user:
                msg = '\x19%s}The uptime of %s is %s.' % (
                    dump_tuple(get_theme().COLOR_INFORMATION_TEXT), from_,
                    common.parse_secs_to_str(seconds))
            else:
                msg = '\x19%s}The last activity of %s was %s ago%s' % (
                    dump_tuple(get_theme().COLOR_INFORMATION_TEXT),
                    from_,
                    common.parse_secs_to_str(seconds),
                    (' and his/her last status was %s' % status)
                    if status else '',
                )
            self.add_message(msg)
            self.core.refresh_window()

        self.core.xmpp.plugin['xep_0012'].get_last_activity(
            self.get_dest_jid(), callback=callback)

    @refresh_wrapper.conditional
    @command_args_parser.ignored
    def command_info(self):
        contact = roster[self.get_dest_jid()]
        jid = safeJID(self.get_dest_jid())
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        if resource:
            status = (
                'Status: %s' % resource.status) if resource.status else ''
            self._text_buffer.add_message(
                "\x19%(info_col)s}Show: %(show)s, %(status)s\x19o" % {
                    'show': resource.presence or 'available',
                    'status': status,
                    'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)
                })
            return True
        else:
            self._text_buffer.add_message(
                "\x19%(info_col)s}No information available\x19o" %
                {'info_col': dump_tuple(get_theme().COLOR_INFORMATION_TEXT)})
            return True

    @command_args_parser.quoted(0, 1)
    def command_version(self, args):
        """
        /version [jid]
        """
        if args:
            return self.core.command.version(args[0])
        jid = safeJID(self.name)
        if not jid.resource:
            if jid in roster:
                resource = roster[jid].get_highest_priority_resource()
                jid = resource.jid if resource else jid
        self.core.xmpp.plugin['xep_0092'].get_version(
            jid, callback=self.core.handler.on_version_result)

    @command_args_parser.ignored
    def command_add(self):
        """
        Add the current JID to the roster, and automatically
        accept the reverse subscription
        """
        jid = self.general_jid
        if jid in roster and roster[jid].subscription in ('to', 'both'):
            return self.core.information('Already subscribed.', 'Roster')
        roster.add(jid)
        roster.modified()
        self.core.information('%s was added to the roster' % jid, 'Roster')

    def resize(self):
        self.need_resize = False
        if self.size.tab_degrade_y:
            display_bar = False
            info_win_height = 0
            tab_win_height = 0
            bar_height = 0
        else:
            display_bar = True
            info_win_height = self.core.information_win_size
            tab_win_height = Tab.tab_win_height()
            bar_height = 1

        self.text_win.resize(
            self.height - 2 - bar_height - info_win_height - tab_win_height,
            self.width, bar_height, 0)
        self.text_win.rebuild_everything(self._text_buffer)
        if display_bar:
            self.upper_bar.resize(1, self.width, 0, 0)
        self.get_info_header().resize(
            1, self.width, self.height - 2 - info_win_height - tab_win_height,
            0)
        self.input.resize(1, self.width, self.height - 1, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        display_bar = display_info_win = not self.size.tab_degrade_y

        self.text_win.refresh()

        if display_bar:
            self.upper_bar.refresh(self.get_dest_jid(),
                                   roster[self.get_dest_jid()])
        self.get_info_header().refresh(
            self.get_dest_jid(), roster[self.get_dest_jid()], self.text_win,
            self.chatstate, ConversationTab.additional_information)

        if display_info_win:
            self.info_win.refresh()
        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        self.get_info_header().refresh(
            self.get_dest_jid(), roster[self.get_dest_jid()], self.text_win,
            self.chatstate, ConversationTab.additional_information)
        self.input.refresh()

    def get_nick(self):
        jid = safeJID(self.name)
        contact = roster[jid.bare]
        if contact:
            return contact.name or jid.user
        else:
            if self.nick:
                return self.nick
            return jid.user

    def on_input(self, key, raw):
        if not raw and key in self.key_func:
            self.key_func[key]()
            return False
        self.input.do_command(key, raw=raw)
        empty_after = self.input.get_text() == '' or (
            self.input.get_text().startswith('/')
            and not self.input.get_text().startswith('//'))
        self.send_composing_chat_state(empty_after)
        return False

    def on_lose_focus(self):
        contact = roster[self.get_dest_jid()]
        jid = safeJID(self.get_dest_jid())
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        if self.input.text:
            self.state = 'nonempty'
        else:
            self.state = 'normal'
        self.text_win.remove_line_separator()
        self.text_win.add_line_separator(self._text_buffer)
        if config.get_by_tabname('send_chat_states', self.general_jid):
            if resource:
                self.send_chat_state('inactive')
        self.check_scrolled()

    def on_gain_focus(self):
        contact = roster[self.get_dest_jid()]
        jid = safeJID(self.get_dest_jid())
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None

        self.state = 'current'
        curses.curs_set(1)
        if (config.get_by_tabname('send_chat_states', self.general_jid)
                and (not self.input.get_text()
                     or not self.input.get_text().startswith('//'))):
            if resource:
                self.send_chat_state('active')

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height - 3:
            return
        self.text_win.resize(
            self.height - 3 - self.core.information_win_size -
            Tab.tab_win_height(), self.width, 1, 0)
        self.get_info_header().resize(
            1, self.width, self.height - 2 - self.core.information_win_size -
            Tab.tab_win_height(), 0)

    def get_text_window(self):
        return self.text_win

    def on_close(self):
        Tab.on_close(self)
        if config.get_by_tabname('send_chat_states', self.general_jid):
            self.send_chat_state('gone')

    def matching_names(self):
        res = []
        jid = safeJID(self.name)
        res.append((2, jid.bare))
        res.append((1, jid.user))
        contact = roster[self.name]
        if contact and contact.name:
            res.append((0, contact.name))
        return res


class DynamicConversationTab(ConversationTab):
    """
    A conversation tab associated with one bare JID.  It used to
    support resource locking (as described in XEP-0296), but that was a
    bad idea so it has been removed.
    Only one DynamicConversationTab can be opened for a given jid.
    """
    plugin_commands = {}
    plugin_keys = {}

    def __init__(self, core, jid, resource=None):
        self.locked_resource = None
        self.name = safeJID(jid).bare
        ConversationTab.__init__(self, core, jid)
        self.info_header = windows.DynamicConversationInfoWin()
        self.register_command(
            'unlock', self.unlock_command, shortdesc='Deprecated, do nothing.')
        self.resize()
        self.update_commands()
        self.update_keys()

    def get_info_header(self):
        return self.info_header

    def lock(self, resource):
        pass

    def unlock_command(self, arg=None):
        pass

    def unlock(self, from_=None):
        pass

    def get_dest_jid(self):
        """
        Returns the bare jid.
        """
        return self.name

    def refresh(self):
        """
        Different from the parent class only for the info_header object.
        """
        if self.need_resize:
            self.resize()
        log.debug('  TAB   Refresh: %s', self.__class__.__name__)
        display_bar = display_info_win = not self.size.tab_degrade_y

        self.text_win.refresh()
        if display_bar:
            self.upper_bar.refresh(self.name, roster[self.name])
        displayed_jid = self.name
        self.get_info_header().refresh(displayed_jid, roster[self.name],
                                       self.text_win, self.chatstate,
                                       ConversationTab.additional_information)
        if display_info_win:
            self.info_win.refresh()

        self.refresh_tab_win()
        self.input.refresh()

    def refresh_info_header(self):
        """
        Different from the parent class only for the info_header object.
        """
        displayed_jid = self.name
        self.get_info_header().refresh(displayed_jid, roster[self.name],
                                       self.text_win, self.chatstate,
                                       ConversationTab.additional_information)
        self.input.refresh()


class StaticConversationTab(ConversationTab):
    """
    A conversation tab associated with one Full JID. It cannot be locked to
    an different resource or unlocked.
    """
    plugin_commands = {}
    plugin_keys = {}

    def __init__(self, core, jid):
        assert (safeJID(jid).resource)
        ConversationTab.__init__(self, core, jid)
        self.info_header = windows.ConversationInfoWin()
        self.resize()
        self.update_commands()
        self.update_keys()

    def get_info_header(self):
        return self.info_header
