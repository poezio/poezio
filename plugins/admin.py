"""
This plugin adds several convenient aliases, to shorten
roles/affiliation management.

Aliases defined
---------------

All those commands take a nick or a JID as a parameter.

For roles
~~~~~~~~~

.. glossary::
    :sorted:

    /visitor
    /mute
        Set the role to ``visitor``

    /participant
        Set the role to ``participant``

    /moderator
    /op
        Set the role to ``moderator``


For affiliations
~~~~~~~~~~~~~~~~

.. glossary::
    :sorted:

    /admin
        Set the affiliation to ``admin``

    /member
    /voice
        Set the affiliation to ``member``

    /noaffiliation
        Set the affiliation to ``none``

    /owner
        Set the affiliation to ``owner``





"""


from poezio.plugin import BasePlugin
from poezio.tabs import MucTab
from poezio.core.structs import Completion

class Plugin(BasePlugin):
    """
    Adds several convenient aliases to /affiliation and /role:
        /visitor
        /participant
        /moderator == /op
        /member == /voice
        /owner
        /admin
        /noaffiliation
    """
    def init(self):
        for role in ('visitor', 'participant' , 'moderator'):
            self.api.add_tab_command(MucTab, role, self.role(role),
                    help='Set the role of a nick to %s' % role,
                    usage= '<nick>',
                    short='Set the role to %s' % role,
                    completion=self.complete_nick)

        for aff in ('member', 'owner', 'admin'):
            self.api.add_tab_command(MucTab, aff, self.affiliation(aff),
                    usage='<nick>',
                    help='Set the affiliation of a nick to %s' % aff,
                    short='Set the affiliation to %s' % aff,
                    completion=self.complete_nick)

        self.api.add_tab_command(MucTab, 'noaffiliation', self.affiliation('none'),
                    usage='<nick>',
                    help='Set the affiliation of a nick to none.',
                    short='Set the affiliation to none.',
                    completion=self.complete_nick)
        self.api.add_tab_command(MucTab, 'voice', self.affiliation('member'),
                    usage='<nick>',
                    help='Set the affiliation of a nick to member.',
                    short='Set the affiliation to member.',
                    completion=self.complete_nick)
        self.api.add_tab_command(MucTab, 'op', self.role('moderator'),
                    usage='<nick>',
                    help='Set the role of a nick to moderator.',
                    short='Set the role to moderator.',
                    completion=self.complete_nick)
        self.api.add_tab_command(MucTab, 'mute', self.role('visitor'),
                    usage='<nick>',
                    help='Set the role of a nick to visitor.',
                    short='Set the role to visitor.',
                    completion=self.complete_nick)

    def role(self, role):
        return lambda args: self.api.current_tab().command_role(args+' '+role)

    def affiliation(self, affiliation):
        return lambda args: self.api.current_tab().command_affiliation(
                                    args+' '+affiliation)

    def complete_nick(self, the_input):
        tab = self.api.current_tab()
        compare_users = lambda x: x.last_talked
        word_list = [user.nick for user in sorted(tab.users, key=compare_users, reverse=True)\
                         if user.nick != tab.own_nick]
        return Completion(the_input.auto_completion, word_list, '')



