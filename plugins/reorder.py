"""
``reorder`` plugin: Reorder the tabs according to a layout

Commands
--------

.. glossary::

    /reorder
        **Usage:** ``/reorder``

        Reorder the tabs according to the configuration.

    /save_order
        **Usage:** ``/save_order``

        Save the current tab order to the configuration.

Configuration
-------------

The configuration file must contain a section ``[reorder]`` and each option
must be formatted like ``[tab number] = [tab type]:[tab name]``.

For example:

.. code-block:: ini

    [reorder]
    1 = muc:toto@conference.example.com
    2 = muc:example@muc.example.im
    3 = dynamic:robert@example.org

The ``[tab number]`` must be at least ``1``; if the range is not entirely
covered, e.g.:

.. code-block:: ini

    [reorder]
    1 = muc:toto@conference.example.com
    3 = dynamic:robert@example.org

Poezio will insert gaps between the tabs in order to keep the specified
numbering (so in this case, there will be a tab 1, a tab 3, but no tab 2).


The ``[tab type]`` must be one of:

- ``muc`` (for multi-user chats)
- ``private`` (for chats with a specific user inside a multi-user chat)
- ``dynamic`` (for normal, dynamic conversations tabs)
- ``static`` (for conversations with a specific resource)
- ``space`` (for categorizing windows)

And finally, the ``[tab name]`` must be:

- For a type ``muc``, the bare JID of the room
- For a type ``private``, the full JID of the user (room JID with the username as a resource)
- For a type ``dynamic``, the bare JID of the contact
- For a type ``static``, the full JID of the contact
- For a type ``space``, the alphanumeric name to display
"""

from slixmpp import InvalidJID, JID

from poezio import tabs
from poezio.decorators import command_args_parser
from poezio.plugin import BasePlugin
from poezio.config import config

class SpaceTab(tabs.ListTab):
    """
    A tab listing rooms from a specific server, displaying various information,
    scrollable, and letting the user join them, etc
    """

    # TODO:
    #   - Pressing enter on a room either joins it or opens the already-joined tab
    #   - Non-joined room in the workspace should be highlighted
    #   - Expand and collapse (toggle force_display on) children of a SpaceTab, using keybindings (<>)
    #   - Where and why is the tabname sanitized, preventing to use lovely characters? ("idna validation failed")
    def __init__(self, core, name, children, logger):
        tabs.ListTab.__init__(self, core, name, "Rooms listed in that space, in your reorder.cfg",
                         '%s rooms' % name,
                         (('jid', 0), ('users', 1)))
        self.logger = logger
        self.logger('%s' % children, 'Info')
        # NOTE: Apparently ^M is Enter?!
        self.key_func['^M'] = self.join_selected
        children = list(map(lambda x: (x, 0), children))
        self.force_display = True
        # TODO: Maybe no need to refresh the display for every time? Depending on how many spaces there are to process
        # it's either a feature or a bug.
        self.listview.set_lines(children)
        self.refresh_tab_win()
        self.core.doupdate()

    def get_columns_sizes(self):
        return {
            'jid': int(self.width * 5 / 8),
            'users': int(self.width * 3 / 8)
        }

    async def join_selected(self):
        row = self.listview.get_selected_row()
        if not row:
            return
        self.logger("Joining selected chat %s" % row[0], 'Info')
        await self.core.command.join(row[0])

TEXT_TO_TAB = {
    'muc': tabs.MucTab,
    'private': tabs.PrivateTab,
    'dynamic': tabs.DynamicConversationTab,
    'static': tabs.StaticConversationTab,
    'empty': tabs.GapTab,
    'space': SpaceTab

}

TAB_TO_TEXT = {
    tabs.MucTab: 'muc',
    tabs.DynamicConversationTab: 'dynamic',
    tabs.PrivateTab: 'private',
    tabs.StaticConversationTab: 'static',
    tabs.GapTab: 'empty',
    SpaceTab: 'space'
}

def parse_config(tab_config):
    result = {}
    for option in tab_config.options('reorder'):
        if not option.isdecimal():
            continue
        pos = int(option)
        if pos in result or pos <= 0:
            return None

        spec = tab_config.get(option, default=':').split(':', maxsplit=1)
        # Gap tabs are recreated automatically if there's a gap in indices.
        if spec == 'empty':
            return None
        typ, name = spec
        if typ not in TEXT_TO_TAB:
            return None
        result[pos] = (TEXT_TO_TAB[typ], name)

    return result


def check_tab(tab):
    for cls, rep in TAB_TO_TEXT.items():
        if isinstance(tab, cls):
            return rep
    return ''


def parse_runtime_tablist(tablist):
    props = []
    i = 0
    for tab in tablist[1:]:
        i += 1
        result = check_tab(tab)
        # Don't serialize gap tabs as they're recreated automatically
        if result != 'empty':
            props.append((i, '%s:%s' % (result, tab.jid.full)))
    return props


class Plugin(BasePlugin):
    """reorder plugin"""

    def init(self):
        self.api.add_command(
            'reorder',
            self.command_reorder,
            help='Reorder all tabs using the pre-defined'
            ' layout from the configuration file.')
        self.api.add_command(
            'save_order',
            self.command_save_order,
            help='Save the current tab layout')

    @command_args_parser.ignored
    def command_save_order(self) -> None:
        """
        /save_order
        """
        conf = parse_runtime_tablist(self.core.tabs)
        for key, value in conf:
            self.config.set(key, value)
        self.api.information('Tab order saved', 'Info')

    @command_args_parser.ignored
    async def command_reorder(self) -> None:
        """
        /reorder
        """
        self.api.information('Reordering tabs', 'Info')
        tabs_spec = parse_config(self.config)
        if not tabs_spec:
            self.api.information('Invalid reorder config', 'Error')
            return None

        old_tabs = self.core.tabs.get_tabs()
        roster = old_tabs[0]

        # List of MUC JIDs to join because they were not saved on server
        # or have been closed in the meantime
        to_join = []

        create_gaps = config.get('create_gaps')

        new_tabs = [roster]
        last = 0
        self.api.information(str(type(tabs_spec)), 'Info')
        sorted_tabs = sorted(tabs_spec)
        self.api.information(str(type(tabs_spec)), 'Info')
        for pos in sorted_tabs:
            if create_gaps and pos > last + 1:
                self.api.information('Found gap', 'Debug')
                new_tabs += [
                    tabs.GapTab() for i in range(pos - last - 1)
                ]
            cls, jid = tabs_spec[pos]
            try:
                # Don't lowercase/sanitize space names
                name = jid
                jid = JID(jid)
                tab = self.core.tabs.by_name_and_class(str(jid), cls=cls)
                if tab and tab in old_tabs and not isinstance(tab, SpaceTab):
                    new_tabs.append(tab)
                else:
                    if cls == tabs.MucTab:
                        self.api.information('MUC Tab %s not found. Creating it' % jid, 'Info')
                        non_local_part = str(jid).split('@')[-1].split('/')
                        if len(non_local_part) > 1: nick = non_local_part[1]
                        else: nick = None
                        new_tab = cls(self.core, jid, nick)
                        new_tabs.append(new_tab)
                        to_join.append(str(jid))
                    elif cls in (tabs.DynamicConversationTab, tabs.StaticConversationTab):
                        self.api.information('Tab %s not found. Creating it' % jid, 'Info')
                        new_tab = cls(self.core, jid)
                        new_tabs.append(new_tab)
                    elif cls == SpaceTab:
                        # Spaces are not defined server-side yet, for now it's not a JID *at all* -> use name not jid
                        self.api.information('Space Tab %s not found. Creating it' % name, 'Info')
                        children = []
                        # Iterate until GapTab or SpaceTab or end of tabs list
                        childpos = pos
                        while True:
                            childpos += 1
                            if childpos not in tabs_spec:
                                break # end of tabs list
                            clss, jidd = tabs_spec[childpos]
                            # Encountering a new space marker, stop
                            if clss == SpaceTab: break
                            # Ignore GapTabs (TODO: is that good?)
                            if clss == tabs.GapTab: continue
                            children.append(jidd)
                            #self.api.information(tabs_spec[childpos], 'Info')
                        new_tab = cls(self.core, name, children, self.api.information)
                        new_tabs.append(new_tab)
                    else:
                        new_tabs.append(tabs.GapTab())
            except Exception as e:
                self.api.information('Failed to create tab \'%s\'.\n%s' % (jid, e), 'Error')
                #if create_gaps:
                #    new_tabs.append(tabs.GapTab())
                # Inserting a GapTab where a tab creation failed, to prevent duplicate
                # entries further down the list (not sure why)
                new_tabs.append(tabs.GapTab())
            finally:
                last = pos

        for tab in old_tabs:
            # Don't reinsert previous spacetabs and gaptabs, could break things!
            # TODO: Why does SpaceTab not match isinstance(tab, SpaceTab) here?!
            #if tab and not (tab in new_tabs or isinstance(tab, SpaceTab) or isinstance(tab, tabs.GapTab)):
            if tab and not (tab in new_tabs or tab.__class__.__name__ in ("SpaceTab", "GapTab")):
                self.api.information('    READDING %s of type %s' % (tab.name, tab.__class__.__name__), 'Info')
                new_tabs.append(tab)

        # TODO: Ensure we don't break poezio and call this with whatever
        # tablist we have. The roster tab at least needs to be in there.
        self.core.tabs.replace_tabs(new_tabs)
        self.core.refresh_window()

        for entry in to_join:
            # TODO: Make it so those joined tabs don't show activity when finished joining
            await self.core.command.join(entry)

        # TODO: Capture exception errors and re-list them now, indicate success if there was no exception
        self.api.information('Reordering is finished', 'Info')

        return None
