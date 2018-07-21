"""
Defines the data-forms Tab
"""

import logging
log = logging.getLogger(__name__)

from poezio import windows
from poezio.bookmarks import Bookmark, BookmarkList
from poezio.tabs import Tab
from poezio.common import safeJID


class BookmarksTab(Tab):
    """
    A tab displaying lines of bookmarks, each bookmark having
    a 4 widgets to set the jid/password/autojoin/storage method
    """
    plugin_commands = {}

    def __init__(self, core, bookmarks: BookmarkList):
        Tab.__init__(self, core)
        self.name = "Bookmarks"
        self.bookmarks = bookmarks
        self.new_bookmarks = []
        self.removed_bookmarks = []
        self.header_win = windows.ColumnHeaderWin(
            ('name', 'room@server/nickname', 'password', 'autojoin',
             'storage'))
        self.bookmarks_win = windows.BookmarksWin(
            self.bookmarks, self.height - 4, self.width, 1, 0)
        self.help_win = windows.HelpText('Ctrl+Y: save, Ctrl+G: cancel, '
                                         '↑↓: change lines, tab: change '
                                         'column, M-a: add bookmark, C-k'
                                         ': delete bookmark')
        self.info_header = windows.BookmarksInfoWin()
        self.key_func['KEY_UP'] = self.bookmarks_win.go_to_previous_line_input
        self.key_func['KEY_DOWN'] = self.bookmarks_win.go_to_next_line_input
        self.key_func['^I'] = self.bookmarks_win.go_to_next_horizontal_input
        self.key_func['^G'] = self.on_cancel
        self.key_func['^Y'] = self.on_save
        self.key_func['M-a'] = self.add_bookmark
        self.key_func['^K'] = self.del_bookmark
        self.resize()
        self.update_commands()

    def add_bookmark(self):
        new_bookmark = Bookmark(
            safeJID('room@example.tld/nick'), method='local')
        self.new_bookmarks.append(new_bookmark)
        self.bookmarks_win.add_bookmark(new_bookmark)

    def del_bookmark(self):
        current = self.bookmarks_win.del_current_bookmark()
        if current in self.new_bookmarks:
            self.new_bookmarks.remove(current)
        else:
            self.removed_bookmarks.append(current)

    def on_cancel(self):
        self.core.close_tab(self)
        return True

    def on_scroll_down(self):
        return self.bookmarks_win.go_to_next_page()

    def on_scroll_up(self):
        return self.bookmarks_win.go_to_previous_page()

    def on_save(self):
        self.bookmarks_win.save()
        if find_duplicates(self.new_bookmarks):
            self.core.information(
                'Duplicate bookmarks in list (saving aborted)', 'Error')
            return
        for bm in self.new_bookmarks:
            if safeJID(bm.jid):
                if not self.bookmarks[bm.jid]:
                    self.bookmarks.append(bm)
            else:
                self.core.information(
                    'Invalid JID for bookmark: %s/%s' % (bm.jid, bm.nick),
                    'Error')
                return

        for bm in self.removed_bookmarks:
            if bm in self.bookmarks:
                self.bookmarks.remove(bm)

        def send_cb(success):
            if success:
                self.core.information('Bookmarks saved.', 'Info')
            else:
                self.core.information('Remote bookmarks not saved.', 'Error')

        self.bookmarks.save(self.core.xmpp, callback=send_cb)
        self.core.close_tab(self)
        return True

    def on_input(self, key, raw=False):
        if key in self.key_func:
            res = self.key_func[key]()
            if res:
                return res
            self.bookmarks_win.refresh_current_input()
        else:
            self.bookmarks_win.on_input(key)

    def resize(self):
        self.need_resize = False
        self.header_win.resize_columns({
            'name':
            self.width // 4,
            'room@server/nickname':
            self.width // 4,
            'password':
            self.width // 6,
            'autojoin':
            self.width // 6,
            'storage':
            self.width // 6
        })
        info_height = self.core.information_win_size
        tab_height = Tab.tab_win_height()
        self.header_win.resize(1, self.width, 0, 0)
        self.bookmarks_win.resize(self.height - 3 - tab_height - info_height,
                                  self.width, 1, 0)
        self.help_win.resize(1, self.width, self.height - 1, 0)
        self.info_header.resize(1, self.width,
                                self.height - 2 - tab_height - info_height, 0)

    def on_info_win_size_changed(self):
        if self.core.information_win_size >= self.height - 3:
            return
        info_height = self.core.information_win_size
        tab_height = Tab.tab_win_height()
        self.bookmarks_win.resize(self.height - 3 - tab_height - info_height,
                                  self.width, 1, 0)
        self.info_header.resize(1, self.width,
                                self.height - 2 - tab_height - info_height, 0)

    def refresh(self):
        if self.need_resize:
            self.resize()
        self.header_win.refresh()
        self.refresh_tab_win()
        self.help_win.refresh()
        self.info_header.refresh(self.bookmarks.preferred)
        self.info_win.refresh()
        self.bookmarks_win.refresh()


def find_duplicates(bm_list):
    jids = set()
    for bookmark in bm_list:
        if bookmark.jid in jids:
            return True
        jids.add(bookmark.jid)
    return False
