"""
``reorder`` plugin: Reorder the tabs according to a layout

Commands
--------

.. glossary::

    /reorder
        **Usage:** ``/reorder``

        Reorder the tabs according to the configuration.


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
from plugin import BasePlugin
import tabs
from decorators import command_args_parser

mapping = {
    'muc': tabs.MucTab,
    'private': tabs.PrivateTab,
    'dynamic': tabs.DynamicConversationTab,
    'static': tabs.StaticConversationTab,
    'empty': tabs.GapTab
}

def parse_config(config):
    result = {}
    for option in config.options('reorder'):
        if not option.isdecimal():
            continue
        pos = int(option)
        if pos in result or pos <= 0:
            return

        typ, name = config.get(option, default=':').split(':', maxsplit=1)
        if typ not in mapping:
            return
        result[pos] = (mapping[typ], name)

    return result

class Plugin(BasePlugin):
    def init(self):
        self.api.add_command('reorder', self.command_reorder,
                             help='Reorder all tabs using the pre-defined'
                                  ' layout from the configuration file.')

    @command_args_parser.ignored
    def command_reorder(self):
        """
        /reorder
        """
        self.core.go_to_roster()
        self.core.current_tab_nb = 0

        tabs_spec = parse_config(self.config)
        if not tabs_spec:
            return self.api.information('Invalid reorder config', 'Error')

        old_tabs = self.core.tabs[1:]
        roster = self.core.tabs[0]

        new_tabs = []
        last = 0
        for pos in sorted(tabs_spec):
            if pos > last + 1:
                new_tabs += [tabs.GapTab() for i in range(pos - last)]
            cls, name = tabs_spec[pos]
            tab = self.core.get_tab_by_name(name, typ=cls)
            if tab and tab in old_tabs:
                new_tabs.append(tab)
                old_tabs.remove(tab)
            else:
                self.api.information('Tab %s not found' % name, 'Warning')
                new_tabs.append(tabs.GapTab())
            last = pos

        for tab in old_tabs:
            if tab:
                new_tabs.append(tab)

        self.core.tabs.clear()
        self.core.tabs.append(roster)
        self.core.tabs += new_tabs

        self.core.refresh_window()

