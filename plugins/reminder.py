"""
Usage
-----

This plugin defines three new global commands: :term:`/remind`,
:term:`/done`, and :term:`/tasks`.

.. glossary::

    /remind
        **Usage:** ``/remind <time> <todo>``

        This command will remind you to do ``todo`` every ``time``.

    /done
        **Usage:** ``/done <id>``
        Remove a reminder.

        The ``id`` is found using :term:`/tasks`.


    /tasks

        Print a list of the tasks, their ids, and their frequency, into the
        information buffer.

Time format
-----------

In seconds:

.. code-block:: none

    /remind 600 Work!

Will remind you to work every 10 minutes.

Defining the time in seconds is not really practical, so you can describe it
with days, hours, and minutes, in a time-string, e.g:

.. code-block:: python

    /remind 1h23m "Get up"

Will remind you to get up every 1 hour 23 minutes.


"""

from poezio.core.structs import Completion
from poezio.plugin import BasePlugin
from poezio import timed_events
from poezio import common
import curses

class Plugin(BasePlugin):

    def init(self):
        self.api.add_command('remind', self.command_remind,
                usage='<seconds> <todo>',
                help='Remind you of <todo> every <time> seconds.',
                short='Remind you of a task',
                completion=self.completion_remind)
        self.api.add_command('done', self.command_done,
                usage='<id>',
                help='Stop reminding you do the task identified by <id>.',
                short='Remove a task',
                completion=self.completion_done)
        self.api.add_command('tasks', self.command_tasks,
                usage='',
                help='List all the current tasks and their ids.',
                short='List current tasks')
        self.tasks = {}
        self.count = 0

        for option in self.config.options(self.__module__):
            id, secs = option.split(',')
            id = int(id)
            if id > self.count:
                self.count = id
            value = self.config.get(option, '')
            self.tasks[id] = (int(secs), value)
            self.config.remove_section(self.__module__)
            self.config.add_section(self.__module__)
        if self.tasks:
            self.count += 1
            self.command_tasks('', nocommand=True)

    def command_remind(self, arg):
        args = common.shell_split(arg)
        if len(args) < 2:
            return
        time = common.parse_str_to_secs(args[0])
        if not time:
            return

        self.tasks[self.count] = (time, args[1])
        timed_event = timed_events.DelayedEvent(time, self.remind, self.count)
        self.api.add_timed_event(timed_event)
        self.api.information('Task %s added: %s every %s.' % (self.count, args[1],
            common.parse_secs_to_str(time)), 'Info')
        self.count += 1

    def completion_remind(self, the_input):
        txt = the_input.get_text()
        args = common.shell_split(txt)
        n = len(args)
        if txt.endswith(' '):
            n += 1
        if n == 2:
            return Completion(the_input.auto_completion, ["60", "5m", "15m", "30m", "1h", "10h", "1d"], '')

    def completion_done(self, the_input):
        return Completion(the_input.auto_completion, ["%s" % key for key in self.tasks], '')

    def command_done(self, arg="0"):
        try:
            id_ = int(arg)
        except ValueError:
            return
        if id_ not in self.tasks:
            return

        self.api.information('Task %s: %s [DONE]' % (id_, self.tasks[id_][1]), 'Info')
        del self.tasks[id_]

    def command_tasks(self, arg, nocommand=None):
        if nocommand:
            s = 'The following tasks were loaded:\n'
        else:
            s = 'The following tasks are active:\n'
        for key in self.tasks:
            s += 'Task %s: %s every %s.\n' % (key, repr(self.tasks[key][1]),
                    common.parse_secs_to_str(self.tasks[key][0]))
        if s:
            self.api.information(s, 'Info')

    def remind(self, id_=0):
        if id_ not in self.tasks:
            return
        self.api.information('Task %s: %s' % (id_, self.tasks[id_][1]), 'Info')
        if self.config.get('beep', '') == 'true':
            curses.beep()
        timed_event = timed_events.DelayedEvent(self.tasks[id_][0], self.remind, id_)
        self.api.add_timed_event(timed_event)

    def cleanup(self):
        if self.tasks:
            self.config.remove_section(self.__module__)
            self.config.add_section(self.__module__)
            for task in self.tasks:
                self.config.set('%s,%s' % (task, self.tasks[task][0]), self.tasks[task][1])
        self.config.write()
