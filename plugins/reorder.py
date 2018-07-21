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

And finally, the ``[tab name]`` must be:

- For a type ``muc``, the bare JID of the room
- For a type ``private``, the full JID of the user (room JID with the username as a resource)
- For a type ``dynamic``, the bare JID of the contact
- For a type ``static``, the full JID of the contact
"""

from poezio import tabs
from poezio.decorators import command_args_parser
from poezio.plugin import BasePlugin
from poezio.config import config

TEXT_TO_TAB = {
    'muc': tabs.MucTab,
    'private': tabs.PrivateTab,
    'dynamic': tabs.DynamicConversationTab,
    'static': tabs.StaticConversationTab,
    'empty': tabs.GapTab
}

TAB_TO_TEXT = {
    tabs.MucTab: 'muc',
    tabs.DynamicConversationTab: 'dynamic',
    tabs.PrivateTab: 'private',
    tabs.StaticConversationTab: 'static',
    tabs.GapTab: 'empty'
}

def parse_config(tab_config):
    result = {}
    for option in tab_config.options('reorder'):
        if not option.isdecimal():
            continue
        pos = int(option)
        if pos in result or pos <= 0:
            return None

        typ, name = tab_config.get(option, default=':').split(':', maxsplit=1)
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
        if result:
            props.append((i, '%s:%s' % (result, tab.name)))
    return props

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('reorder', self.command_reorder,
                             help='Reorder all tabs using the pre-defined'
                                  ' layout from the configuration file.')
        self.api.add_command('save_order', self.command_save_order,
                             help='Save the current tab layout')

    @command_args_parser.ignored
    def command_save_order(self):
        conf = parse_runtime_tablist(self.core.tabs)
        for key, value in conf:
            self.config.set(key, value)
        self.api.information('Tab order saved', 'Info')

    @command_args_parser.ignored
    def command_reorder(self):
        """
        /reorder
        """
        tabs_spec = parse_config(self.config)
        if not tabs_spec:
            return self.api.information('Invalid reorder config', 'Error')

        old_tabs = self.core.tabs.get_tabs()
        roster = old_tabs.pop(0)

        create_gaps = config.get('create_gaps')

        new_tabs = [roster]
        last = 0
        for pos in sorted(tabs_spec):
            if create_gaps and pos > last + 1:
                new_tabs += [tabs.GapTab(self.core) for i in range(pos - last - 1)]
            cls, name = tabs_spec[pos]
            tab = self.core.tabs.by_name_and_class(name, cls=cls)
            if tab and tab in old_tabs:
                new_tabs.append(tab)
                old_tabs.remove(tab)
            else:
                self.api.information('Tab %s not found' % name, 'Warning')
                if create_gaps:
                    new_tabs.append(tabs.GapTab(self.core))
            last = pos

        for tab in old_tabs:
            if tab:
                new_tabs.append(tab)

        self.core.tabs.replace_tabs(new_tabs)
        self.core.refresh_window()
