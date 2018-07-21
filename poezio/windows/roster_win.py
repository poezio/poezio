"""
Windows used with the roster (window displaying the contacts, and the
one showing detailed info on the current selection)
"""
import logging
log = logging.getLogger(__name__)

from datetime import datetime

from poezio.windows.base_wins import Win

from poezio import common
from poezio.config import config
from poezio.contact import Contact, Resource
from poezio.roster import RosterGroup
from poezio.theming import get_theme, to_curses_attr


class RosterWin(Win):
    def __init__(self):
        Win.__init__(self)
        self.pos = 0  # cursor position in the contact list
        self.start_pos = 1  # position of the start of the display
        self.selected_row = None
        self.roster_cache = []

    @property
    def roster_len(self):
        return len(self.roster_cache)

    def move_cursor_down(self, number=1):
        """
        Return True if we scrolled, False otherwise
        """
        pos = self.pos
        if self.pos < self.roster_len - number:
            self.pos += number
        else:
            self.pos = self.roster_len - 1
        if self.pos >= self.start_pos - 1 + self.height - 1:
            if number == 1:
                self.scroll_down(8)
            else:
                self.scroll_down(self.pos - self.start_pos - self.height // 2)
        self.update_pos()
        return pos != self.pos

    def move_cursor_up(self, number=1):
        """
        Return True if we scrolled, False otherwise
        """
        pos = self.pos
        if self.pos - number >= 0:
            self.pos -= number
        else:
            self.pos = 0
        if self.pos <= self.start_pos:
            if number == 1:
                self.scroll_up(8)
            else:
                self.scroll_up(self.start_pos - self.pos + self.height // 2)
        self.update_pos()
        return pos != self.pos

    def update_pos(self):
        if len(self.roster_cache) > self.pos and self.pos >= 0:
            self.selected_row = self.roster_cache[self.pos]
        elif self.roster_cache:
            self.selected_row = self.roster_cache[-1]

    def scroll_down(self, number=8):
        pos = self.start_pos
        if self.start_pos + number <= self.roster_len - 1:
            self.start_pos += number
        else:
            self.start_pos = self.roster_len - 1
        return self.start_pos != pos

    def scroll_up(self, number=8):
        pos = self.start_pos
        if self.start_pos - number > 0:
            self.start_pos -= number
        else:
            self.start_pos = 1
        return self.start_pos != pos

    def build_roster_cache(self, roster):
        """
        Regenerates the roster cache if needed
        """
        if not roster.needs_rebuild:
            return
        log.debug('The roster has changed, rebuilding the cache…')
        # This is a search
        if roster.contact_filter is not roster.DEFAULT_FILTER:
            self.roster_cache = []
            sort = config.get('roster_sort', 'jid:show') or 'jid:show'
            for contact in roster.get_contacts_sorted_filtered(sort):
                self.roster_cache.append(contact)
        else:
            show_offline = config.get('roster_show_offline')
            sort = config.get('roster_sort') or 'jid:show'
            group_sort = config.get('roster_group_sort') or 'name'
            self.roster_cache = []
            # build the cache
            for group in roster.get_groups(group_sort):
                contacts_filtered = group.get_contacts()
                if (not show_offline and group.get_nb_connected_contacts() == 0
                    ) or not contacts_filtered:
                    continue  # Ignore empty groups
                self.roster_cache.append(group)
                if group.folded:
                    continue  # ignore folded groups
                for contact in group.get_contacts(sort=sort):
                    if not show_offline and len(contact) == 0:
                        continue  # ignore offline contacts
                    self.roster_cache.append(contact)
                    if not contact.folded(group.name):
                        for resource in contact.get_resources():
                            self.roster_cache.append(resource)
        roster.last_built = datetime.now()
        if self.selected_row in self.roster_cache:
            if self.pos < self.roster_len and self.roster_cache[self.
                                                                pos] != self.selected_row:
                self.pos = self.roster_cache.index(self.selected_row)

    def refresh(self, roster):
        """
        We display a number of lines from the roster cache
        (and rebuild it if needed)
        """
        log.debug('Refresh: %s', self.__class__.__name__)
        self.build_roster_cache(roster)
        # make sure we are within bounds
        self.move_cursor_up((
            self.roster_len + self.pos) if self.pos >= self.roster_len else 0)
        if not self.roster_cache:
            self.selected_row = None
        self._win.erase()
        self._win.move(0, 0)
        self.draw_roster_information(roster)
        y = 1
        group = "none"
        # scroll down if needed
        if self.start_pos + self.height <= self.pos + 2:
            self.scroll_down(self.pos - self.start_pos - self.height +
                             (self.height // 2))
        # draw the roster from the cache
        roster_view = self.roster_cache[self.start_pos - 1:self.start_pos +
                                        self.height]

        options = {
            'show_roster_sub': config.get('show_roster_subscriptions'),
            'show_s2s_errors': config.get('show_s2s_errors'),
            'show_roster_jids': config.get('show_roster_jids')
        }

        for item in roster_view:
            draw_selected = False
            if y - 2 + self.start_pos == self.pos:
                draw_selected = True
                self.selected_row = item

            if isinstance(item, RosterGroup):
                self.draw_group(y, item, draw_selected)
                group = item.name
            elif isinstance(item, Contact):
                self.draw_contact_line(y, item, draw_selected, group,
                                       **options)
            elif isinstance(item, Resource):
                self.draw_resource_line(y, item, draw_selected)

            y += 1

        if self.start_pos > 1:
            self.draw_plus(1)
        if self.start_pos + self.height - 2 < self.roster_len:
            self.draw_plus(self.height - 1)
        self._refresh()

    def draw_plus(self, y):
        """
        Draw the indicator that shows that
        the list is longer than what is displayed
        """
        self.addstr(y, self.width - 5, '++++',
                    to_curses_attr(get_theme().COLOR_MORE_INDICATOR))

    def draw_roster_information(self, roster):
        """
        The header at the top
        """
        self.addstr(
            'Roster: %s/%s contacts' % (roster.get_nb_connected_contacts(),
                                        len(roster)),
            to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)

    def draw_group(self, y, group, colored):
        """
        Draw a groupname on a line
        """
        if colored:
            self._win.attron(to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        if group.folded:
            self.addstr(y, 0, '[+] ')
        else:
            self.addstr(y, 0, '[-] ')
        contacts = " (%s/%s)" % (group.get_nb_connected_contacts(), len(group))
        self.addstr(
            y, 4,
            self.truncate_name(group.name,
                               len(contacts) + 4) + contacts)
        if colored:
            self._win.attroff(to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        self.finish_line()

    def truncate_name(self, name, added):
        if len(name) + added <= self.width:
            return name
        return name[:self.width - added - 1] + '…'

    def draw_contact_line(self,
                          y,
                          contact,
                          colored,
                          group,
                          show_roster_sub=False,
                          show_s2s_errors=True,
                          show_roster_jids=False):
        """
        Draw on a line all information about one contact.
        This is basically the highest priority resource's information
        Use 'color' to draw the jid/display_name to show what is
        the currently selected contact in the list
        """

        theme = get_theme()
        resource = contact.get_highest_priority_resource()
        if not resource:
            # There's no online resource
            presence = 'unavailable'
            nb = ''
        else:
            presence = resource.presence
            nb = ' (%s)' % len(contact)
        color = theme.color_show(presence)
        added = 2 + len(theme.CHAR_STATUS) + len(nb)

        self.addstr(y, 0, ' ')
        self.addstr(theme.CHAR_STATUS, to_curses_attr(color))

        self.addstr(' ')
        if resource:
            self.addstr('[+] ' if contact.folded(group) else '[-] ')
        else:
            self.addstr('    ')
        added += 4

        if contact.ask:
            added += len(get_theme().CHAR_ROSTER_ASKED)
        if show_s2s_errors and contact.error:
            added += len(get_theme().CHAR_ROSTER_ERROR)
        if contact.tune:
            added += len(get_theme().CHAR_ROSTER_TUNE)
        if contact.mood:
            added += len(get_theme().CHAR_ROSTER_MOOD)
        if contact.activity:
            added += len(get_theme().CHAR_ROSTER_ACTIVITY)
        if contact.gaming:
            added += len(get_theme().CHAR_ROSTER_GAMING)
        if show_roster_sub in ('all', 'incomplete', 'to', 'from', 'both',
                               'none'):
            added += len(
                theme.char_subscription(
                    contact.subscription, keep=show_roster_sub))

        if not show_roster_jids and contact.name:
            display_name = contact.name
        elif contact.name and contact.name != contact.bare_jid:
            display_name = '%s (%s)' % (contact.name, contact.bare_jid)
        else:
            display_name = contact.bare_jid

        display_name = self.truncate_name(display_name, added) + nb

        if colored:
            self.addstr(display_name,
                        to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        else:
            self.addstr(display_name)

        if show_roster_sub in ('all', 'incomplete', 'to', 'from', 'both',
                               'none'):
            self.addstr(
                theme.char_subscription(
                    contact.subscription, keep=show_roster_sub),
                to_curses_attr(theme.COLOR_ROSTER_SUBSCRIPTION))
        if contact.ask:
            self.addstr(get_theme().CHAR_ROSTER_ASKED,
                        to_curses_attr(get_theme().COLOR_IMPORTANT_TEXT))
        if show_s2s_errors and contact.error:
            self.addstr(get_theme().CHAR_ROSTER_ERROR,
                        to_curses_attr(get_theme().COLOR_ROSTER_ERROR))
        if contact.tune:
            self.addstr(get_theme().CHAR_ROSTER_TUNE,
                        to_curses_attr(get_theme().COLOR_ROSTER_TUNE))
        if contact.activity:
            self.addstr(get_theme().CHAR_ROSTER_ACTIVITY,
                        to_curses_attr(get_theme().COLOR_ROSTER_ACTIVITY))
        if contact.mood:
            self.addstr(get_theme().CHAR_ROSTER_MOOD,
                        to_curses_attr(get_theme().COLOR_ROSTER_MOOD))
        if contact.gaming:
            self.addstr(get_theme().CHAR_ROSTER_GAMING,
                        to_curses_attr(get_theme().COLOR_ROSTER_GAMING))
        self.finish_line()

    def draw_resource_line(self, y, resource, colored):
        """
        Draw a specific resource line
        """
        color = get_theme().color_show(resource.presence)
        self.addstr(y, 4, get_theme().CHAR_STATUS, to_curses_attr(color))
        if colored:
            self.addstr(y, 8, self.truncate_name(str(resource.jid), 6),
                        to_curses_attr(get_theme().COLOR_SELECTED_ROW))
        else:
            self.addstr(y, 8, self.truncate_name(str(resource.jid), 6))
        self.finish_line()

    def get_selected_row(self):
        if self.pos >= len(self.roster_cache):
            return self.selected_row
        if len(self.roster_cache) > 0:
            self.selected_row = self.roster_cache[self.pos]
            return self.roster_cache[self.pos]
        return None


class ContactInfoWin(Win):
    def draw_contact_info(self, contact):
        """
        draw the contact information
        """
        resource = contact.get_highest_priority_resource()
        if contact:
            jid = contact.bare_jid
        elif resource:
            jid = resource.jid
        else:
            jid = 'example@example.com'  # should never happen
        if resource:
            presence = resource.presence
        else:
            presence = 'unavailable'
        i = 0
        self.addstr(0, 0, '%s (%s)' % (
            jid,
            presence,
        ), to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)
        i += 1
        self.addstr(i, 0, 'Subscription: %s' % (contact.subscription, ))
        self.finish_line()
        i += 1
        if contact.ask:
            if contact.ask == 'asked':
                self.addstr(i, 0, 'Ask: %s' % (contact.ask, ),
                            to_curses_attr(get_theme().COLOR_IMPORTANT_TEXT))
            else:
                self.addstr(i, 0, 'Ask: %s' % (contact.ask, ))
            self.finish_line()
            i += 1
        if resource:
            self.addstr(i, 0, 'Status: %s' % (resource.status))
            self.finish_line()
            i += 1

        if contact.error:
            self.addstr(i, 0, 'Error: %s' % contact.error,
                        to_curses_attr(get_theme().COLOR_ROSTER_ERROR))
            self.finish_line()
            i += 1

        if contact.tune:
            self.addstr(i, 0,
                        'Tune: %s' % common.format_tune_string(contact.tune),
                        to_curses_attr(get_theme().COLOR_NORMAL_TEXT))
            self.finish_line()
            i += 1

        if contact.mood:
            self.addstr(i, 0, 'Mood: %s' % contact.mood,
                        to_curses_attr(get_theme().COLOR_NORMAL_TEXT))
            self.finish_line()
            i += 1

        if contact.activity:
            self.addstr(i, 0, 'Activity: %s' % contact.activity,
                        to_curses_attr(get_theme().COLOR_NORMAL_TEXT))
            self.finish_line()
            i += 1

        if contact.gaming:
            self.addstr(
                i, 0, 'Game: %s' % common.format_gaming_string(contact.gaming),
                to_curses_attr(get_theme().COLOR_NORMAL_TEXT))
            self.finish_line()
            i += 1

    def draw_group_info(self, group):
        """
        draw the group information
        """
        self.addstr(0, 0, group.name,
                    to_curses_attr(get_theme().COLOR_INFORMATION_BAR))
        self.finish_line(get_theme().COLOR_INFORMATION_BAR)

    def refresh(self, selected_row):
        log.debug('Refresh: %s', self.__class__.__name__)
        self._win.erase()
        if isinstance(selected_row, RosterGroup):
            self.draw_group_info(selected_row)
        elif isinstance(selected_row, Contact):
            self.draw_contact_info(selected_row)
        # elif isinstance(selected_row, Resource):
        #     self.draw_contact_info(None, selected_row)
        self._refresh()
