"""
Windows used by the DataFormsTab.

We only need to export the FormWin (which is not a real Win, as it
does not inherit from the Win base class), as it will create the
others when needed.
"""

from poezio.windows import base_wins
from poezio.windows.base_wins import Win
from poezio.windows.inputs import Input

from poezio.theming import to_curses_attr, get_theme


class FieldInput:
    """
    All input types in a data form should inherit this class,
    in addition with windows.Input or any relevant class from the
    'windows' library.
    """

    def __init__(self, field):
        self._field = field
        self.color = get_theme().COLOR_NORMAL_TEXT

    def update_field_value(self, value):
        raise NotImplementedError

    def is_dummy(self):
        return False

    def reply(self):
        """
        Set the correct response value in the field
        """
        raise NotImplementedError

    def get_help_message(self):
        """
        Should return a string explaining the keys of the input.
        Will be displayed at each refresh on a line at the bottom of the tab.
        """
        return ''


class FieldInputMixin(FieldInput, Win):
    "Mix both FieldInput and Win"

    def __init__(self, field):
        FieldInput.__init__(self, field)
        Win.__init__(self)

    def resize(self, height, width, y, x):
        self._resize(height, width, y, x)

    def set_color(self, color):
        self.color = color
        self.refresh()


class ColoredLabel(Win):
    def __init__(self, text):
        self.text = text
        self.color = get_theme().COLOR_NORMAL_TEXT
        Win.__init__(self)

    def resize(self, height, width, y, x):
        self._resize(height, width, y, x)

    def set_color(self, color):
        self.color = color
        self.refresh()

    def refresh(self):
        self._win.erase()
        self._win.attron(to_curses_attr(self.color))
        self.addstr(0, 0, self.text)
        self._win.attroff(to_curses_attr(self.color))
        self._refresh()


class DummyInput(FieldInputMixin):
    """
    Used for fields that do not require any input ('fixed')
    """

    def __init__(self, field):
        FieldInputMixin.__init__(self, field)

    def do_command(self, *args, **kwargs):
        return

    def refresh(self):
        return

    def is_dummy(self):
        return True


class BooleanWin(FieldInputMixin):
    def __init__(self, field):
        FieldInputMixin.__init__(self, field)
        self.last_key = 'KEY_RIGHT'
        self.value = bool(field.get_value())

    def do_command(self, key, raw=False):
        if key == 'KEY_LEFT' or key == 'KEY_RIGHT':
            self.value = not self.value
            self.last_key = key
        self.refresh()

    def refresh(self):
        self._win.erase()
        self._win.attron(to_curses_attr(self.color))
        self.addnstr(0, 0, ' ' * (8), self.width)
        self.addstr(0, 2, "%s" % self.value)
        self.addstr(0, 8, '→')
        self.addstr(0, 0, '←')
        if self.last_key == 'KEY_RIGHT':
            self.addstr(0, 8, '')
        else:
            self.addstr(0, 0, '')
        self._win.attroff(to_curses_attr(self.color))
        self._refresh()

    def reply(self):
        self._field['label'] = ''
        self._field.set_answer(self.value)

    def get_help_message(self):
        return '← and →: change the value between True and False'


class TextMultiWin(FieldInputMixin):
    def __init__(self, field):
        FieldInputMixin.__init__(self, field)
        options = field.get_value()
        if isinstance(options, list):
            self.options = options
        else:
            self.options = options.split('\n') if options else []
        self.val_pos = 0
        self.edition_input = None
        if not isinstance(self.options, list):
            if isinstance(self.options, str):
                self.options = [self.options]
            else:
                self.options = []
        self.options.append('')

    def do_command(self, key, raw=False):
        if not self.edition_input:
            if key == 'KEY_LEFT':
                if self.val_pos > 0:
                    self.val_pos -= 1
            elif key == 'KEY_RIGHT':
                if self.val_pos < len(self.options) - 1:
                    self.val_pos += 1
            elif key == '^M':
                self.edition_input = Input()
                self.edition_input.color = self.color
                self.edition_input.resize(self.height, self.width, self.y,
                                          self.x)
                self.edition_input.text = self.options[self.val_pos]
                self.edition_input.key_end()
        else:
            if key == '^M':
                self.options[self.val_pos] = self.edition_input.get_text()
                if not self.options[self.val_pos] and self.val_pos != len(
                        self.options) - 1:
                    del self.options[self.val_pos]
                    if self.val_pos == len(self.options) - 1:
                        self.val_pos -= 1
                self.edition_input = None
                if not self.options or self.options[-1] != '':
                    self.options.append('')
            else:
                self.edition_input.do_command(key)
        self.refresh()

    def refresh(self):
        if not self.edition_input:
            self._win.erase()
            self._win.attron(to_curses_attr(self.color))
            self.addnstr(0, 0, ' ' * self.width, self.width)
            option = self.options[self.val_pos]
            self.addstr(0, self.width // 2 - len(option) // 2, option)
            if self.val_pos > 0:
                self.addstr(0, 0, '←')
            if self.val_pos < len(self.options) - 1:
                self.addstr(0, self.width - 1, '→')
            self._win.attroff(to_curses_attr(self.color))
            self._refresh()
        else:
            self.edition_input.refresh()

    def reply(self):
        values = [val for val in self.options if val]
        self._field.set_answer(values)

    def get_help_message(self):
        if not self.edition_input:
            help_msg = '← and →: browse the available entries. '
            if self.val_pos == len(self.options) - 1:
                help_msg += 'Enter: add an entry'
            else:
                help_msg += 'Enter: edit this entry'
        else:
            help_msg = 'Enter: finish editing this entry.'
        return help_msg


class ListMultiWin(FieldInputMixin):
    def __init__(self, field):
        FieldInputMixin.__init__(self, field)
        values = field.get_value() or []
        self.options = [[option, True if option['value'] in values else False]\
                        for option in field.get_options()]
        self.val_pos = 0

    def do_command(self, key, raw=False):
        if key == 'KEY_LEFT':
            if self.val_pos > 0:
                self.val_pos -= 1
        elif key == 'KEY_RIGHT':
            if self.val_pos < len(self.options) - 1:
                self.val_pos += 1
        elif key == ' ':
            self.options[self.val_pos][1] = not self.options[self.val_pos][1]
        else:
            return
        self.refresh()

    def refresh(self):
        self._win.erase()
        self._win.attron(to_curses_attr(self.color))
        self.addnstr(0, 0, ' ' * self.width, self.width)
        if self.val_pos > 0:
            self.addstr(0, 0, '←')
        if self.val_pos < len(self.options) - 1:
            self.addstr(0, self.width - 1, '→')
        if self.options:
            option = self.options[self.val_pos]
            self.addstr(0, self.width // 2 - len(option) // 2,
                        option[0]['label'])
            self.addstr(0, 2, '✔' if option[1] else '☐')
        self._win.attroff(to_curses_attr(self.color))
        self._refresh()

    def reply(self):
        self._field['label'] = ''
        self._field.delOptions()
        values = [
            option[0]['value'] for option in self.options if option[1] is True
        ]
        self._field.set_answer(values)

    def get_help_message(self):
        return '←, →: Switch between the value. Space: select or unselect a value'


class ListSingleWin(FieldInputMixin):
    def __init__(self, field):
        FieldInputMixin.__init__(self, field)
        # the option list never changes
        self.options = field.get_options()
        # val_pos is the position of the currently selected option
        self.val_pos = 0
        for i, option in enumerate(self.options):
            if field.get_value() == option['value']:
                self.val_pos = i

    def do_command(self, key, raw=False):
        if key == 'KEY_LEFT':
            if self.val_pos > 0:
                self.val_pos -= 1
        elif key == 'KEY_RIGHT':
            if self.val_pos < len(self.options) - 1:
                self.val_pos += 1
        else:
            return
        self.refresh()

    def refresh(self):
        self._win.erase()
        self._win.attron(to_curses_attr(self.color))
        self.addnstr(0, 0, ' ' * self.width, self.width)
        if self.val_pos > 0:
            self.addstr(0, 0, '←')
        if self.val_pos < len(self.options) - 1:
            self.addstr(0, self.width - 1, '→')
        if self.options:
            option = self.options[self.val_pos]['label']
            self.addstr(0, self.width // 2 - len(option) // 2, option)
        self._win.attroff(to_curses_attr(self.color))
        self._refresh()

    def reply(self):
        self._field['label'] = ''
        self._field.delOptions()
        self._field.set_answer(self.options[self.val_pos]['value'])

    def get_help_message(self):
        return '←, →: Select a value amongst the others'


class TextSingleWin(FieldInputMixin, Input):
    def __init__(self, field):
        FieldInputMixin.__init__(self, field)
        Input.__init__(self)
        self.text = field.get_value() if isinstance(field.get_value(), str)\
            else ""
        self.pos = len(self.text)
        self.color = get_theme().COLOR_NORMAL_TEXT

    def reply(self):
        self._field['label'] = ''
        self._field.set_answer(self.get_text())

    def get_help_message(self):
        return 'Edit the text'


class TextPrivateWin(TextSingleWin):
    def __init__(self, field):
        TextSingleWin.__init__(self, field)

    def rewrite_text(self):
        self._win.erase()
        if self.color:
            self._win.attron(to_curses_attr(self.color))
        self.addstr(
            '*' * len(self.text[self.view_pos:self.view_pos + self.width - 1]))
        if self.color:
            (y, x) = self._win.getyx()
            size = self.width - x
            self.addnstr(' ' * size, size, to_curses_attr(self.color))
        self.addstr(0, self.pos, '')
        if self.color:
            self._win.attroff(to_curses_attr(self.color))
        self._refresh()

    def get_help_message(self):
        return 'Edit the secret text'


class FormWin:
    """
    A window, with some subwins (the various inputs).
    On init, create all the subwins.
    On resize, move and resize all the subwin and define how the text will be written
    On refresh, write all the text, and refresh all the subwins
    """
    input_classes = {
        'boolean': BooleanWin,
        'fixed': DummyInput,
        'jid-multi': TextMultiWin,
        'jid-single': TextSingleWin,
        'list-multi': ListMultiWin,
        'list-single': ListSingleWin,
        'text-multi': TextMultiWin,
        'text-private': TextPrivateWin,
        'text-single': TextSingleWin,
    }

    def __init__(self, form, height, width, y, x):
        self._form = form
        self._win = base_wins.TAB_WIN.derwin(height, width, y, x)
        self.scroll_pos = 0
        self.current_input = 0
        self.inputs = []  # dict list
        for (name, field) in self._form.getFields().items():
            if field['type'] == 'hidden':
                continue
            try:
                input_class = self.input_classes[field['type']]
            except IndexError:
                continue
            label = field['label']
            desc = field['desc']
            if field['type'] == 'fixed':
                label = field.get_value()
            inp = input_class(field)
            self.inputs.append({
                'label': ColoredLabel(label),
                'description': desc,
                'input': inp
            })

    def resize(self, height, width, y, x):
        self.height = height
        self.width = width
        self._win = base_wins.TAB_WIN.derwin(height, width, y, x)
        # Adjust the scroll position, if resizing made the window too small
        # for the cursor to be visible
        while self.current_input - self.scroll_pos > self.height - 1:
            self.scroll_pos += 1

    def reply(self):
        """
        Set the response values in the form, for each field
        from the corresponding input
        """
        for inp in self.inputs:
            if inp['input'].is_dummy():
                continue
            else:
                inp['input'].reply()
        self._form['title'] = ''
        self._form['instructions'] = ''

    def go_to_next_input(self):
        if not self.inputs:
            return
        if self.current_input == len(self.inputs) - 1:
            return
        self.inputs[self.current_input]['input'].set_color(
            get_theme().COLOR_NORMAL_TEXT)
        self.inputs[self.current_input]['label'].set_color(
            get_theme().COLOR_NORMAL_TEXT)
        self.current_input += 1
        jump = 0
        while self.current_input + jump != len(
                self.inputs) - 1 and self.inputs[self.current_input +
                                                 jump]['input'].is_dummy():
            jump += 1
        if self.inputs[self.current_input + jump]['input'].is_dummy():
            return
        self.current_input += jump
        # If moving made the current input out of the visible screen, we
        # adjust the scroll position and we redraw the whole thing. We don’t
        # call refresh() if this is not the case, because
        # refresh_current_input() is always called anyway, so this is not
        # needed
        if self.current_input - self.scroll_pos > self.height - 1:
            self.scroll_pos += 1
            self.refresh()
        self.inputs[self.current_input]['input'].set_color(
            get_theme().COLOR_SELECTED_ROW)
        self.inputs[self.current_input]['label'].set_color(
            get_theme().COLOR_SELECTED_ROW)

    def go_to_previous_input(self):
        if not self.inputs:
            return
        if self.current_input == 0:
            return
        self.inputs[self.current_input]['input'].set_color(
            get_theme().COLOR_NORMAL_TEXT)
        self.inputs[self.current_input]['label'].set_color(
            get_theme().COLOR_NORMAL_TEXT)
        self.current_input -= 1
        jump = 0
        while self.current_input - jump > 0 and self.inputs[self.current_input
                                                            +
                                                            jump]['input'].is_dummy(
                                                            ):
            jump += 1
        if self.inputs[self.current_input + jump]['input'].is_dummy():
            return
        # Adjust the scroll position if the current_input would be outside
        # of the visible area
        if self.current_input < self.scroll_pos:
            self.scroll_pos = self.current_input
            self.refresh()
        self.current_input -= jump
        self.inputs[self.current_input]['input'].set_color(
            get_theme().COLOR_SELECTED_ROW)
        self.inputs[self.current_input]['label'].set_color(
            get_theme().COLOR_SELECTED_ROW)

    def on_input(self, key, raw=False):
        if not self.inputs:
            return
        self.inputs[self.current_input]['input'].do_command(key, raw=raw)

    def refresh(self):
        self._win.erase()
        y = -self.scroll_pos
        i = 0
        for name, field in self._form.getFields().items():
            if field['type'] == 'hidden':
                continue
            self.inputs[i]['label'].resize(1, self.width // 2, y + 1, 0)
            self.inputs[i]['input'].resize(1, self.width // 2, y + 1,
                                           self.width // 2)
            # TODO: display the field description
            y += 1
            i += 1
        self._win.refresh()
        for i, inp in enumerate(self.inputs):
            if i < self.scroll_pos:
                continue
            if i >= self.height + self.scroll_pos:
                break
            inp['label'].refresh()
            inp['input'].refresh()
            inp['label'].refresh()
        if self.inputs and self.current_input < self.height - 1:
            self.inputs[self.current_input]['input'].set_color(
                get_theme().COLOR_SELECTED_ROW)
            self.inputs[self.current_input]['input'].refresh()
            self.inputs[self.current_input]['label'].set_color(
                get_theme().COLOR_SELECTED_ROW)
            self.inputs[self.current_input]['label'].refresh()

    def refresh_current_input(self):
        self.inputs[self.current_input]['input'].refresh()

    def get_help_message(self):
        if self.inputs and self.current_input < self.height - 1 and self.inputs[self.
                                                                                current_input]['input']:
            return self.inputs[self.current_input]['input'].get_help_message()
        return ''
