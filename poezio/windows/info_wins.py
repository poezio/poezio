"""
Module defining all the "info wins", ie the bar which is on top of the
info buffer in normal tabs
"""

import logging
log = logging.getLogger(__name__)

from poezio.common import safeJID
from poezio.config import config

from poezio.windows.base_wins import Win
from poezio.windows.funcs import truncate_nick
from poezio.theming import get_theme, to_curses_attr


class InfoWin(Win):
    """
    Base class for all the *InfoWin, used in various tabs. For example
    MucInfoWin, etc. Provides some useful methods.
    """

    def __init__(self):
        Win.__init__(self)

    def print_scroll_position(self, window):
        """
        Print, like in Weechat, a -MORE(n)- where n
        is the number of available lines to scroll
        down
        """
        if window.pos > 0:
            plus = ' -MORE(%s)-' % window.pos
            self.addstr(plus,
                        to_curses_attr(get_theme().COLOR_SCROLLABLE_NUMBER))


class XMLInfoWin(InfoWin):
    """
    Info about the latest xml filter used and the state of the buffer.
    """

    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, filter_t='', filter='', window=None):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        bar = to_curses_attr(get_theme().COLOR_INFORMATION_BAR)
        if not filter_t:
            self.addstr('[No filter]', bar)
        else:
            info = '[%s] %s' % (filter_t, filter)
            self.addstr(info, bar)
        self.print_scroll_position(window)
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()


class PrivateInfoWin(InfoWin):
    """
    The line above the information window, displaying information
    about the MUC user we are talking to
    """

    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, name, window, chatstate, information):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        self.write_room_name(name)
        self.print_scroll_position(window)
        self.write_chatstate(chatstate)
        self.write_additional_information(information, name)
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()

    def write_additional_information(self, information, jid):
        """
        Write all information added by plugins by getting the
        value returned by the callbacks.
        """
        for key in information:
            self.addstr(information[key](jid),
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_room_name(self, name):
        jid = safeJID(name)
        room_name, nick = jid.bare, jid.resource
        self.addstr(nick, to_curses_attr(get_theme().COLOR_PRIVATE_NAME))
        txt = ' from room %s' % room_name
        self.addstr(txt, to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_chatstate(self, state):
        if state:
            self.addstr(' %s' % (state, ),
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))


class MucListInfoWin(InfoWin):
    """
    The live above the information window, displaying informatios
    about the muc server being listed
    """

    def __init__(self, message=''):
        InfoWin.__init__(self)
        self.message = message

    def refresh(self, name=None, window=None):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        if name:
            self.addstr(name,
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        else:
            self.addstr(self.message,
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        if window:
            self.print_scroll_position(window)
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()


class ConversationInfoWin(InfoWin):
    """
    The line above the information window, displaying information
    about the user we are talking to
    """

    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, jid, contact, window, chatstate, information):
        # contact can be None, if we receive a message
        # from someone not in our roster. In this case, we display
        # only the maximum information from the message we can get.
        log.debug('Refresh: %s', self.__class__.__name__)
        jid = safeJID(jid)
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        # if contact is None, then resource is None too:
        # user is not in the roster so we know almost nothing about it
        # If contact is a Contact, then
        # resource can now be a Resource: user is in the roster and online
        # or resource is None: user is in the roster but offline
        self._win.erase()
        if config.get('show_jid_in_conversations'):
            self.write_contact_jid(jid)
        self.write_contact_information(contact)
        self.write_resource_information(resource)
        self.print_scroll_position(window)
        self.write_chatstate(chatstate)
        self.write_additional_information(information, jid)
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()

    def write_additional_information(self, information, jid):
        """
        Write all information added by plugins by getting the
        value returned by the callbacks.
        """
        for key in information:
            self.addstr(information[key](jid),
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_resource_information(self, resource):
        """
        Write the information about the resource
        """
        if not resource:
            presence = "unavailable"
        else:
            presence = resource.presence
        color = get_theme().color_show(presence)
        if not presence:
            presence = get_theme().CHAR_STATUS
        self.addstr('[', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(presence, to_curses_attr(color))
        if resource and resource.status:
            shortened = resource.status[:20] + (resource.status[:20] and '…')
            self.addstr(' %s' % shortened,
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(']', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_contact_information(self, contact):
        """
        Write the information about the contact
        """
        if not contact:
            self.addstr("(contact not in roster)",
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
            return
        display_name = contact.name
        if display_name:
            self.addstr('%s ' % (display_name),
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_contact_jid(self, jid):
        """
        Just write the jid that we are talking to
        """
        self.addstr('[', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(jid.full,
                    to_curses_attr(get_theme().COLOR_CONVERSATION_NAME))
        self.addstr('] ', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_chatstate(self, state):
        if state:
            self.addstr(' %s' % (state, ),
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))


class DynamicConversationInfoWin(ConversationInfoWin):
    def write_contact_jid(self, jid):
        """
        Just displays the resource in an other color
        """
        log.debug("write_contact_jid DynamicConversationInfoWin, jid: %s",
                  jid.resource)
        self.addstr('[', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(jid.bare,
                    to_curses_attr(get_theme().COLOR_CONVERSATION_NAME))
        if jid.resource:
            self.addstr(
                "/%s" % (jid.resource, ),
                to_curses_attr(get_theme().COLOR_CONVERSATION_RESOURCE))
        self.addstr('] ', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))


class MucInfoWin(InfoWin):
    """
    The line just above the information window, displaying information
    about the MUC we are viewing
    """

    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, room, window=None, user=None):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        self.write_room_name(room)
        self.write_participants_number(room)
        self.write_own_nick(room)
        self.write_disconnected(room)
        self.write_role(room, user)
        if window:
            self.print_scroll_position(window)
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()

    def write_room_name(self, room):
        self.addstr('[', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(room.name,
                    to_curses_attr(get_theme().COLOR_GROUPCHAT_NAME))
        self.addstr(']', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_participants_number(self, room):
        self.addstr('{', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.addstr(
            str(len(room.users)),
            to_curses_attr(get_theme().COLOR_GROUPCHAT_NAME))
        self.addstr('} ', to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_disconnected(self, room):
        """
        Shows a message if the room is not joined
        """
        if not room.joined:
            self.addstr(' -!- Not connected ',
                        to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_own_nick(self, room):
        """
        Write our own nick in the info bar
        """
        nick = room.own_nick
        if not nick:
            return
        self.addstr(
            truncate_nick(nick, 13),
            to_curses_attr(get_theme().COLOR_INFORMATION_BAR))

    def write_role(self, room, user):
        """
        Write our own role and affiliation
        """
        if not user:
            return
        txt = ' ('
        if user.affiliation != 'none':
            txt += user.affiliation + ', '
        txt += user.role + ')'
        self.addstr(txt, to_curses_attr(get_theme().COLOR_INFORMATION_BAR))


class ConversationStatusMessageWin(InfoWin):
    """
    The upper bar displaying the status message of the contact
    """

    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, jid, contact):
        log.debug('Refresh: %s', self.__class__.__name__)
        jid = safeJID(jid)
        if contact:
            if jid.resource:
                resource = contact[jid.full]
            else:
                resource = contact.get_highest_priority_resource()
        else:
            resource = None
        self._win.erase()
        if resource:
            self.write_status_message(resource)
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()

    def write_status_message(self, resource):
        self.addstr(resource.status,
                    to_curses_attr(get_theme().COLOR_INFORMATION_BAR))


class BookmarksInfoWin(InfoWin):
    def __init__(self):
        InfoWin.__init__(self)

    def refresh(self, preferred):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        self.write_remote_status(preferred)
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        self._refresh()

    def write_remote_status(self, preferred):
        self.addstr('Remote storage: %s' % preferred,
                    to_curses_attr(get_theme().COLOR_INFORMATION_BAR))


class ConfirmStatusWin(Win):
    def __init__(self, text, critical=False):
        Win.__init__(self)
        self.text = text
        self.critical = critical

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        if self.critical:
            color = get_theme().COLOR_WARNING_PROMPT
        else:
            color = get_theme().COLOR_INFORMATION_BAR
        c_color = to_curses_attr(color)
        self.addstr(self.text, c_color)
        self.finish_line(color)
        self._refresh()
