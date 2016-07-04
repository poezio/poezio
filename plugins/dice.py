"""
Dice plugin: roll some dice

Usage of this plugin is not recommended.

Commands
--------

.. glossary::

    /roll [number of dice] [duration of the roll]
        Roll one or several unicode dice

Configuration
-------------

.. glossary::
    :sorted:

    refresh
        **Default:** ``0.5``

        Interval in seconds between each correction (the closest to 0 is the fastest)

    default_duration
        **Default:** ``5``

        Total duration of the animation.
"""

import random

from poezio import tabs
from poezio.decorators import command_args_parser
from poezio.plugin import BasePlugin

DICE = '\u2680\u2681\u2682\u2683\u2684\u2685'

class DiceRoll:
    __slots__ = ['duration', 'total_duration', 'dice_number', 'msgtype',
                 'jid', 'last_msgid', 'increments']
    def __init__(self, total_duration, dice_number, is_muc, jid, msgid, increments):
        self.duration = 0
        self.total_duration = total_duration
        self.dice_number = dice_number
        self.msgtype = "groupchat" if is_muc else "chat"
        self.jid = jid
        self.last_msgid = msgid
        self.increments = increments

    def reroll(self):
        self.duration += self.increments

    def is_finished(self):
        return self.duration >= self.total_duration

class Plugin(BasePlugin):
    default_config = {"dice": {"refresh": 0.5, "default_duration": 5}}

    def init(self):
        for tab_t in [tabs.MucTab, tabs.ConversationTab, tabs.PrivateTab]:
            self.api.add_tab_command(tab_t, 'roll', self.command_dice,
                                     help='Roll a die',
                                     usage='[number] [duration]')

    @command_args_parser.quoted(0, 2, ['', ''], True)
    def command_dice(self, args):
        tab = self.api.current_tab()
        duration = self.config.get('default_duration')
        num_dice = 1
        try:
            if args[0]:
                num_dice = int(args[0])
                if args[1]:
                    duration = float(args[1])
        except ValueError:
            self.core.command.help("roll")
            return
        else:
            if num_dice <= 0 or duration < 0:
                self.core.command.help("roll")
                return

        firstroll = ''.join(random.choice(DICE) for _ in range(num_dice))
        tab.command_say(firstroll)
        is_muctab = isinstance(tab, tabs.MucTab)
        msg_id = tab.last_sent_message["id"]
        increment = self.config.get('refresh')
        roll = DiceRoll(duration, num_dice, is_muctab, tab.name, msg_id, increment)
        event = self.api.create_delayed_event(increment, self.delayed_event, roll)
        self.api.add_timed_event(event)

    def delayed_event(self, roll):
        if roll.is_finished():
            return
        roll.reroll()
        message = self.core.xmpp.make_message(roll.jid)
        message["type"] = roll.msgtype
        message["body"] = ''.join(random.choice(DICE) for _ in range(roll.dice_number))
        message["replace"]["id"] = roll.last_msgid
        message.send()
        roll.last_msgid = message['id']
        event = self.api.create_delayed_event(roll.increments,
                                              self.delayed_event, roll)
        self.api.add_timed_event(event)
