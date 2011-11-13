from plugin import BasePlugin
import curses
import common
import timed_events

class Plugin(BasePlugin):

    def init(self):
        self.add_command('remind', self.command_remind, "Usage: /reminder <time in seconds> <todo>\nReminder: remind you of <todo> every <time> seconds..", None)
        self.add_command('done', self.command_done, "Usage: /done <id>\nDone: Stop reminding you do the task identified by <id>", None)
        self.add_command('tasks', self.command_tasks, "Usage: /tasks\nTasks: List all the current tasks and their ids.", None)
        self.tasks = {}
        self.count = 0

    def command_remind(self, arg):
        args = common.shell_split(arg)
        if len(args) < 2:
            return
        try:
           time = int(args[0])
        except:
            return

        self.tasks[self.count] = (time, args[1])
        timed_event = timed_events.DelayedEvent(time, self.remind, self.count)
        self.core.add_timed_event(timed_event)
        self.count += 1

    def command_done(self, arg="0"):
        try:
            id = int(arg)
        except:
            return
        if not id in self.tasks:
            return

        del self.tasks[id]

    def command_tasks(self, arg):
        s = ''
        for key in self.tasks:
            s += '%s: %s\n' % key, self.tasks[key][1]
        if s:
            self.core.information(s, 'Info')

    def remind(self, id=0):
        if not id in self.tasks:
            return
        self.core.information('Task %s: %s' % (id, self.tasks[id][1]), 'Info')
        if self.config.get('beep', '') == 'true':
            curses.beep()
        timed_event = timed_events.DelayedEvent(self.tasks[id][0], self.remind, id)
        self.core.add_timed_event(timed_event)



