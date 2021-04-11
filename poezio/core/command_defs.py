from typing import Callable, List, Optional

from poezio.core.commands import CommandCore
from poezio.core.completions import CompletionCore
from poezio.plugin_manager import PluginManager
from poezio.types import TypedDict


CommandDict = TypedDict(
    "CommandDict",
    {
        "name": str,
        "func": Callable,
        "shortdesc": str,
        "desc": str,
        "usage": str,
        "completion": Optional[Callable],
    },
    total=False,
)


def get_commands(commands: CommandCore, completions: CompletionCore, plugin_manager: PluginManager) -> List[CommandDict]:
    """
    Get the set of default poezio commands.
    """
    return [
        {
            "name": "help",
            "func": commands.help,
            "usage": "[command]",
            "shortdesc": "\\_o< KOIN KOIN KOIN",
            "completion": completions.help,
        },
        {
            "name": "join",
            "func": commands.join,
            "usage": "[room_name][@server][/nick] [password]",
            "desc": (
                "Join the specified room. You can specify a nickname "
                "after a slash (/). If no nickname is specified, you will"
                " use the default_nick in the configuration file. You can"
                " omit the room name: you will then join the room you're"
                " looking at (useful if you were kicked). You can also "
                "provide a room_name without specifying a server, the "
                "server of the room you're currently in will be used. You"
                " can also provide a password to join the room.\nExamples"
                ":\n/join room@server.tld\n/join room@server.tld/John\n"
                "/join room2\n/join /me_again\n/join\n/join room@server"
                ".tld/my_nick password\n/join / password"
            ),
            "shortdesc": "Join a room",
            "completion": completions.join,
        },
        {
            "name": "exit",
            "func": commands.quit,
            "desc": "Just disconnect from the server and exit poezio.",
            "shortdesc": "Exit poezio.",
        },
        {
            "name": "quit",
            "func": commands.quit,
            "desc": "Just disconnect from the server and exit poezio.",
            "shortdesc": "Exit poezio.",
        },
        {
            "name": "next",
            "func": commands.rotate_rooms_right,
            "shortdesc": "Go to the next room.",
        },
        {
            "name": "prev",
            "func": commands.rotate_rooms_left,
            "shortdesc": "Go to the previous room.",
        },
        {
            "name": "win",
            "func": commands.win,
            "usage": "<number or name>",
            "shortdesc": "Go to the specified room",
            "completion": completions.win,
        },
        {
            "name": "w",
            "func": commands.win,
            "usage": "<number or name>",
            "shortdesc": "Go to the specified room",
            "completion": completions.win,
        },
        {
            "name": "wup",
            "func": commands.wup,
            "usage": "<prefix>",
            "shortdesc": "Go to the tab whose name uniquely starts with prefix",
            "completion": completions.win,
        },
        {
            "name": "move_tab",
            "func": commands.move_tab,
            "usage": "<source> <destination>",
            "desc": (
                "Insert the <source> tab at the position of "
                "<destination>. This will make the following tabs shift in"
                " some cases (refer to the documentation). A tab can be "
                "designated by its number or by the beginning of its "
                'address. You can use "." as a shortcut for the current '
                "tab."
            ),
            "shortdesc": "Move a tab.",
            "completion": completions.move_tab,
        },
        {
            "name": "destroy_room",
            "func": commands.destroy_room,
            "usage": "[room JID]",
            "desc": (
                "Try to destroy the room [room JID], or the current"
                " tab if it is a multi-user chat and [room JID] is "
                "not given."
            ),
            "shortdesc": "Destroy a room.",
            "completion": None,
        },
        {
            "name": "status",
            "func": commands.status,
            "usage": "<availability> [status message]",
            "desc": (
                "Sets your availability and (optionally) your status "
                'message. The <availability> argument is one of "available'
                ', chat, away, afk, dnd, busy, xa" and the optional '
                "[status message] argument will be your status message."
            ),
            "shortdesc": "Change your availability.",
            "completion": completions.status,
        },
        {
            "name": "show",
            "func": commands.status,
            "usage": "<availability> [status message]",
            "desc": (
                "Sets your availability and (optionally) your status "
                'message. The <availability> argument is one of "available'
                ', chat, away, afk, dnd, busy, xa" and the optional '
                "[status message] argument will be your status message."
            ),
            "shortdesc": "Change your availability.",
            "completion": completions.status,
        },
        {
            "name": "bookmark_local",
            "func": commands.bookmark_local,
            "usage": "[roomname][/nick] [password]",
            "desc": (
                "Bookmark Local: Bookmark locally the specified room "
                "(you will then auto-join it on each poezio start). This"
                " commands uses almost the same syntaxe as /join. Type "
                "/help join for syntax examples. Note that when typing "
                '"/bookmark" on its own, the room will be bookmarked '
                "with the nickname you're currently using in this room "
                "(instead of default_nick)"
            ),
            "shortdesc": "Bookmark a room locally.",
            "completion": completions.bookmark_local,
        },
        {
            "name": "bookmark",
            "func": commands.bookmark,
            "usage": "[roomname][/nick] [autojoin] [password]",
            "desc": (
                "Bookmark: Bookmark online the specified room (you "
                "will then auto-join it on each poezio start if autojoin"
                " is specified and is 'true'). This commands uses almost"
                " the same syntax as /join. Type /help join for syntax "
                'examples. Note that when typing "/bookmark" alone, the'
                " room will be bookmarked with the nickname you're "
                "currently using in this room (instead of default_nick)."
            ),
            "shortdesc": "Bookmark a room online.",
            "completion": completions.bookmark,
        },
        {
            "name": "accept",
            "func": commands.accept,
            "usage": "[jid]",
            "desc": (
                "Allow the provided JID (or the selected contact "
                "in your roster), to see your presence."
            ),
            "shortdesc": "Allow a user your presence.",
            "completion": completions.roster_barejids,
        },
        {
            "name": "add",
            "func": commands.add,
            "usage": "<jid>",
            "desc": (
                "Add the specified JID to your roster, ask them to"
                " allow you to see his presence, and allow them to"
                " see your presence."
            ),
            "shortdesc": "Add a user to your roster.",
        },
        {
            "name": "deny",
            "func": commands.deny,
            "usage": "[jid]",
            "desc": (
                "Deny your presence to the provided JID (or the "
                "selected contact in your roster), who is asking"
                "you to be in their roster."
            ),
            "shortdesc": "Deny a user your presence.",
            "completion": completions.roster_barejids,
        },
        {
            "name": "remove",
            "func": commands.remove,
            "usage": "[jid]",
            "desc": (
                "Remove the specified JID from your roster. This "
                "will unsubscribe you from its presence, cancel "
                "its subscription to yours, and remove the item "
                "from your roster."
            ),
            "shortdesc": "Remove a user from your roster.",
            "completion": completions.remove,
        },
        {
            "name": "reconnect",
            "func": commands.command_reconnect,
            "usage": "[reconnect]",
            "desc": (
                "Disconnect from the remote server if you are "
                "currently connected and then connect to it again."
            ),
            "shortdesc": "Disconnect and reconnect to the server.",
        },
        {
            "name": "set",
            "func": commands.set,
            "usage": "[plugin|][section] <option> [value]",
            "desc": (
                "Set the value of an option in your configuration file."
                " You can, for example, change your default nickname by "
                "doing `/set default_nick toto` or your resource with `/set"
                " resource blabla`. You can also set options in specific "
                "sections with `/set bindings M-i ^i` or in specific plugin"
                " with `/set mpd_client| host 127.0.0.1`. `toggle` can be "
                "used as a special value to toggle a boolean option."
            ),
            "shortdesc": "Set the value of an option",
            "completion": completions.set,
        },
        {
            "name": "set_default",
            "func": commands.set_default,
            "usage": "[section] <option>",
            "desc": (
                "Set the default value of an option. For example, "
                "`/set_default resource` will reset the resource "
                "option. You can also reset options in specific "
                "sections by doing `/set_default section option`."
            ),
            "shortdesc": "Set the default value of an option",
            "completion": completions.set_default,
        },
        {
            "name": "toggle",
            "func": commands.toggle,
            "usage": "<option>",
            "desc": "Shortcut for /set <option> toggle",
            "shortdesc": "Toggle an option",
            "completion": completions.toggle,
        },
        {
            "name": "theme",
            "func": commands.theme,
            "usage": "[theme name]",
            "desc": (
                "Reload the theme defined in the config file. If theme"
                "_name is provided, set that theme before reloading it."
            ),
            "shortdesc": "Load a theme",
            "completion": completions.theme,
        },
        {
            "name": "list",
            "func": commands.list,
            "usage": "[server]",
            "desc": "Get the list of public rooms" " on the specified server.",
            "shortdesc": "List the rooms.",
            "completion": completions.list,
        },
        {
            "name": "message",
            "func": commands.message,
            "usage": "<jid> [optional message]",
            "desc": (
                "Open a conversation with the specified JID (even if it"
                " is not in our roster), and send a message to it, if the "
                "message is specified."
            ),
            "shortdesc": "Send a message",
            "completion": completions.message,
        },
        {
            "name": "version",
            "func": commands.version,
            "usage": "<jid>",
            "desc": (
                "Get the software version of the given JID (usually its"
                " XMPP client and Operating System)."
            ),
            "shortdesc": "Get the software version of a JID.",
            "completion": completions.version,
        },
        {
            "name": "server_cycle",
            "func": commands.server_cycle,
            "usage": "[domain] [message]",
            "desc": "Disconnect and reconnect in all the rooms in domain.",
            "shortdesc": "Cycle a range of rooms",
            "completion": completions.server_cycle,
        },
        {
            "name": "bind",
            "func": commands.bind,
            "usage": "<key> <equ>",
            "desc": (
                "Bind a key to another key or to a “command”. For "
                'example "/bind ^H KEY_UP" makes Control + h do the'
                " same same as the Up key."
            ),
            "completion": completions.bind,
            "shortdesc": "Bind a key to another key.",
        },
        {
            "name": "load",
            "func": commands.load,
            "usage": "<plugin> [<otherplugin> …]",
            "shortdesc": "Load the specified plugin(s)",
            "completion": plugin_manager.completion_load,
        },
        {
            "name": "unload",
            "func": commands.unload,
            "usage": "<plugin> [<otherplugin> …]",
            "shortdesc": "Unload the specified plugin(s)",
            "completion": plugin_manager.completion_unload,
        },
        {
            "name": "plugins",
            "func": commands.plugins,
            "shortdesc": "Show the plugins in use.",
        },
        {
            "name": "presence",
            "func": commands.presence,
            "usage": "<JID> [type] [status]",
            "desc": "Send a directed presence to <JID> and using"
            " [type] and [status] if provided.",
            "shortdesc": "Send a directed presence.",
            "completion": completions.presence,
        },
        {
            "name": "rawxml",
            "func": commands.rawxml,
            "usage": "<xml>",
            "shortdesc": "Send a custom xml stanza.",
        },
        {
            "name": "invite",
            "func": commands.invite,
            "usage": "<jid> <room> [reason]",
            "desc": "Invite jid in room with reason.",
            "shortdesc": "Invite someone in a room.",
            "completion": completions.invite,
        },
        {
            "name": "impromptu",
            "func": commands.impromptu,
            "usage": "<jid> [jid ...]",
            "desc": "Invite specified JIDs into a newly created room.",
            "shortdesc": "Invite specified JIDs into newly created room.",
            "completion": completions.impromptu,
        },
        {
            "name": "invitations",
            "func": commands.invitations,
            "shortdesc": "Show the pending invitations.",
        },
        {
            "name": "bookmarks",
            "func": commands.bookmarks,
            "shortdesc": "Show the current bookmarks.",
        },
        {
            "name": "remove_bookmark",
            "func": commands.remove_bookmark,
            "usage": "[jid]",
            "desc": "Remove the specified bookmark, or the "
            "bookmark on the current tab, if any.",
            "shortdesc": "Remove a bookmark",
            "completion": completions.remove_bookmark,
        },
        {
            "name": "xml_tab",
            "func": commands.xml_tab,
            "shortdesc": "Open an XML tab.",
        },
        {
            "name": "runkey",
            "func": commands.runkey,
            "usage": "<key>",
            "shortdesc": "Execute the action defined for <key>.",
            "completion": completions.runkey,
        },
        {
            "name": "self",
            "func": commands.self_,
            "shortdesc": "Remind you of who you are.",
        },
        {
            "name": "last_activity",
            "func": commands.last_activity,
            "usage": "<jid>",
            "desc": "Informs you of the last activity of a JID.",
            "shortdesc": "Get the activity of someone.",
            "completion": completions.last_activity,
        },
        {
            "name": "ad-hoc",
            "func": commands.adhoc,
            "usage": "<jid>",
            "shortdesc": "List available ad-hoc commands on the given jid",
        },
        {
            "name": "reload",
            "func": commands.reload,
            "shortdesc": "Reload the config. You can achieve the same by "
            "sending SIGUSR1 to poezio.",
        },
        {
            "name": "debug",
            "func": commands.debug,
            "usage": "[debug_filename]",
            "shortdesc": "Enable or disable debug logging according to the "
            "presence of [debug_filename].",
        },
    ]
