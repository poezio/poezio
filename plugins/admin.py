from plugin import BasePlugin
from tabs import MucTab

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
        for role in ['visitor', 'participant' , 'moderator']:
            self.add_tab_command(MucTab, role, self.role(role),
                    '/%s <nick>\n%s: Set the role of a nick to %s.' %
                        (role, role.capitalize(), role), self.complete_nick)

        for aff in ['member', 'owner', 'admin']:
            self.add_tab_command(MucTab, aff, self.affiliation(aff),
                    '/%s <nick>\n%s: set the affiliation of a nick to %s' %
                        (aff, aff.capitalize(), aff), self.complete_nick)

        self.add_tab_command(MucTab, 'noaffiliation', self.affiliation('none'),
                    '/noaffiliation <nick>\nNoAffiliation: set the affiliation of a nick to none.',
                    self.complete_nick)
        self.add_tab_command(MucTab, 'voice', self.affiliation('member'),
                    '/voice <nick>\nVoice: set the affiliation of a nick to member.',
                    self.complete_nick)
        self.add_tab_command(MucTab, 'op', self.role('moderator'),
                    '/op <nick>\nOp: set the role of a nick to moderator.',
                    self.complete_nick)

    def role(self, role):
        return lambda args: self.core.current_tab().command_role(args+' '+role)

    def affiliation(self, affiliation):
        return lambda args: self.core.current_tab().command_affiliation(
                                    args+' '+affiliation)

    def complete_nick(self, the_input):
        tab = self.core.current_tab()
        compare_users = lambda x: x.last_talked
        word_list = [user.nick for user in sorted(tab.users, key=compare_users, reverse=True)\
                         if user.nick != tab.own_nick]
        return the_input.auto_completion(word_list, '')



