"""
Text inputs.
"""

import logging
log = logging.getLogger(__name__)

import curses
import string

from poezio import keyboard
from poezio import common
from poezio import poopt
from poezio.windows.base_wins import Win, format_chars
from poezio.windows.funcs import find_first_format_char
from poezio.config import config
from poezio.theming import to_curses_attr

DEFAULT_ON_INPUT = lambda x: None


class Input(Win):
    """
    The simplest Input possible, provides just a way to edit a single line
    of text. It also has a clipboard, common to all Inputs.
    Doesn't have any history.
    It doesn't do anything when enter is pressed either.
    This should be herited for all kinds of Inputs, for example MessageInput
    or the little inputs in dataforms, etc, adding specific features (completion etc)
    It features two kinds of completion, but they have to be called from outside (the Tab),
    passing the list of items that can be used to complete. The completion can be used
    in a very flexible way.
    """
    text_attributes = 'bou1234567ti'
    clipboard = ''  # A common clipboard for all the inputs, this makes

    # it easy cut and paste text between various input
    def __init__(self):
        self.key_func = {
            "KEY_LEFT": self.key_left,
            "KEY_RIGHT": self.key_right,
            "KEY_END": self.key_end,
            "KEY_HOME": self.key_home,
            "KEY_DC": self.key_dc,
            '^D': self.key_dc,
            'M-b': self.jump_word_left,
            "M-[1;5D": self.jump_word_left,
            "kRIT5": self.jump_word_right,
            "kLFT5": self.jump_word_left,
            '^W': self.delete_word,
            'M-d': self.delete_next_word,
            '^K': self.delete_end_of_line,
            '^U': self.delete_beginning_of_line,
            '^Y': self.paste_clipboard,
            '^A': self.key_home,
            '^E': self.key_end,
            'M-f': self.jump_word_right,
            "M-[1;5C": self.jump_word_right,
            "KEY_BACKSPACE": self.key_backspace,
            "M-KEY_BACKSPACE": self.delete_word,
            '^?': self.key_backspace,
            "M-^?": self.delete_word,
            # '^J': self.add_line_break,
        }
        Win.__init__(self)
        self.text = ''
        self.pos = 0  # The position of the “cursor” in the text
        # (not only in the view)
        self.view_pos = 0  # The position (in the text) of the
        # first character displayed on the
        # screen
        self.on_input = DEFAULT_ON_INPUT  # callback called on any key pressed
        self.color = None  # use this color on addstr

    def on_delete(self):
        """
        Remove all references kept to a tab, so that the tab
        can be garbage collected
        """
        del self.key_func

    def set_color(self, color):
        self.color = color
        self.rewrite_text()

    def is_empty(self):
        if self.text:
            return False
        return True

    def is_cursor_at_end(self):
        """
        Whether or not the cursor is at the end of the text.
        """
        assert len(self.text) >= self.pos
        if len(self.text) == self.pos:
            return True
        return False

    def jump_word_left(self):
        """
        Move the cursor one word to the left
        """
        if self.pos == 0:
            return True
        separators = string.punctuation + ' '
        while self.pos > 0 and self.text[self.pos - 1] in separators:
            self.key_left()
        while self.pos > 0 and self.text[self.pos - 1] not in separators:
            self.key_left()
        return True

    def jump_word_right(self):
        """
        Move the cursor one word to the right
        """
        if self.is_cursor_at_end():
            return True
        separators = string.punctuation + ' '
        while not self.is_cursor_at_end() and self.text[self.pos] in separators:
            self.key_right()
        while not self.is_cursor_at_end() and self.text[self.
                                                        pos] not in separators:
            self.key_right()
        return True

    def delete_word(self):
        """
        Delete the word just before the cursor
        """
        separators = string.punctuation + ' '
        while self.pos > 0 and self.text[self.pos - 1] in separators:
            self.key_backspace()
        while self.pos > 0 and self.text[self.pos - 1] not in separators:
            self.key_backspace()
        return True

    def delete_next_word(self):
        """
        Delete the word just after the cursor
        """
        separators = string.punctuation + ' '
        while not self.is_cursor_at_end() and self.text[self.pos] in separators:
            self.key_dc()
        while not self.is_cursor_at_end() and self.text[self.
                                                        pos] not in separators:
            self.key_dc()
        return True

    def delete_end_of_line(self):
        """
        Cut the text from cursor to the end of line
        """
        if self.is_cursor_at_end():
            return False
        Input.clipboard = self.text[self.pos:]
        self.text = self.text[:self.pos]
        self.key_end()
        return True

    def delete_beginning_of_line(self):
        """
        Cut the text from cursor to the beginning of line
        """
        if self.pos == 0:
            return True
        Input.clipboard = self.text[:self.pos]
        self.text = self.text[self.pos:]
        self.key_home()
        return True

    def paste_clipboard(self):
        """
        Insert what is in the clipboard at the cursor position
        """
        if not Input.clipboard:
            return True
        for letter in Input.clipboard:
            self.do_command(letter, False)
        self.rewrite_text()
        return True

    def key_dc(self):
        """
        delete char just after the cursor
        """
        self.reset_completion()
        if self.is_cursor_at_end():
            return True  # end of line, nothing to delete
        self.text = self.text[:self.pos] + self.text[self.pos + 1:]
        self.rewrite_text()
        return True

    def key_home(self):
        """
        Go to the beginning of line
        """
        self.reset_completion()
        self.pos = 0
        self.rewrite_text()
        return True

    def key_end(self, reset=False):
        """
        Go to the end of line
        """
        if reset:
            self.reset_completion()
        self.pos = len(self.text)
        assert self.is_cursor_at_end()
        self.rewrite_text()
        return True

    def key_left(self, jump=True, reset=True):
        """
        Move the cursor one char to the left
        """
        if reset:
            self.reset_completion()
        if self.pos == 0:
            return True
        self.pos -= 1
        if reset:
            self.rewrite_text()
        return True

    def key_right(self, jump=True, reset=True):
        """
        Move the cursor one char to the right
        """
        if reset:
            self.reset_completion()
        if self.is_cursor_at_end():
            return True
        self.pos += 1
        if reset:
            self.rewrite_text()
        return True

    def key_backspace(self, reset=True):
        """
        Delete the char just before the cursor
        """
        self.reset_completion()
        if self.pos == 0:
            return False
        self.key_left()
        self.key_dc()
        return True

    def auto_completion(self, word_list, add_after='', quotify=True):
        """
        Complete the input, from a list of words
        if add_after is None, we use the value defined in completion
        plus a space, after the completion. If it's a string, we use it after the
        completion (with no additional space)
        """
        if quotify:
            for i, word in enumerate(word_list[:]):
                word_list[i] = '"' + word + '"'
        self.normal_completion(word_list, add_after)
        return True

    def new_completion(self,
                       word_list,
                       argument_position=-1,
                       add_after='',
                       quotify=True,
                       override=False):
        """
        Complete the argument at position ``argument_postion`` in the input.
        If ``quotify`` is ``True``, then the completion will operate on block of words
        (e.g. "toto titi") whereas if it is ``False``, it will operate on words (e.g
        "toto", "titi").

        The completions may modify other parts of the input when completing an argument,
        for example removing useless double quotes around single-words, or setting the
        space between each argument to only one space.

        The case where we complete the first argument is special, because we complete
        the command, and we do not want to modify anything else in the input.

        This method is the one that should be used if the command being completed
        has several arguments.
        """
        if argument_position == 0:
            self._new_completion_first(word_list)
        else:
            self._new_completion_args(word_list, argument_position, add_after,
                                      quotify, override)
        self.rewrite_text()
        return True

    def _new_completion_args(self,
                             word_list,
                             argument_position=-1,
                             add_after='',
                             quoted=True,
                             override=False):
        """
        Case for completing arguments with position ≠ 0
        """
        if quoted:
            words = common.shell_split(self.text)
        else:
            words = self.text.split()
        if argument_position >= len(words):
            current = ''
        else:
            current = words[argument_position]

        if quoted:
            split_words = words[1:]
            words = [words[0]]
            for word in split_words:
                if ' ' in word or '\\' in word:
                    words.append('"' + word + '"')
                else:
                    words.append(word)
        current_l = current.lower()
        if self.last_completion is not None:
            self.hit_list.append(self.hit_list.pop(0))
        else:
            if override:
                hit_list = word_list
            else:
                hit_list = []
                for word in word_list:
                    if word.lower().startswith(current_l):
                        hit_list.append(word)
            if not hit_list:
                return
            self.hit_list = hit_list

        if argument_position >= len(words):
            if quoted and ' ' in self.hit_list[0]:
                words.append('"' + self.hit_list[0] + '"')
            else:
                words.append(self.hit_list[0])
        else:
            if quoted and ' ' in self.hit_list[0]:
                words[argument_position] = '"' + self.hit_list[0] + '"'
            else:
                words[argument_position] = self.hit_list[0]

        new_pos = -1
        for i, word in enumerate(words):
            if argument_position >= i:
                new_pos += len(word) + 1

        self.last_completion = self.hit_list[0]
        self.text = words[0] + ' ' + ' '.join(words[1:])
        self.pos = new_pos

    def _new_completion_first(self, word_list):
        """
        Special case of completing the command itself:
        we don’t want to change anything to the input doing that
        """
        space_pos = self.text.find(' ')
        if space_pos != -1:
            current, follow = self.text[:space_pos], self.text[space_pos:]
        else:
            current, follow = self.text, ''

        if self.last_completion:
            self.hit_list.append(self.hit_list.pop(0))
        else:
            hit_list = []
            for word in word_list:
                if word.lower().startswith(current):
                    hit_list.append(word)
            if not hit_list:
                return
            self.hit_list = hit_list

        self.last_completion = self.hit_list[0]
        self.text = self.hit_list[0] + follow
        self.pos = len(self.hit_list[0])

    def get_argument_position(self, quoted=True):
        """
        Get the argument number at the current position
        """
        command_stop = self.text.find(' ')
        if command_stop == -1 or self.pos <= command_stop:
            return 0
        text = self.text[command_stop + 1:]
        pos = self.pos - len(self.text) + len(text) - 1
        val = common.find_argument(pos, text, quoted=quoted) + 1
        return val

    def reset_completion(self):
        """
        Reset the completion list (called on ALL keys except tab)
        """
        self.hit_list = []
        self.last_completion = None

    def normal_completion(self, word_list, after):
        """
        Normal completion
        """
        pos = self.pos
        if pos < len(
                self.text) and after.endswith(' ') and self.text[pos] == ' ':
            after = after[:
                          -1]  # remove the last space if we are already on a space
        if not self.last_completion:
            space_before_cursor = self.text.rfind(' ', 0, pos)
            if space_before_cursor != -1:
                begin = self.text[space_before_cursor + 1:pos]
            else:
                begin = self.text[:pos]
            hit_list = []  # list of matching hits
            for word in word_list:
                if word.lower().startswith(begin.lower()):
                    hit_list.append(word)
                elif word.startswith('"') and word.lower()[1:].startswith(
                        begin.lower()):
                    hit_list.append(word)
            if len(hit_list) == 0:
                return
            self.hit_list = hit_list
            end = len(begin)
        else:
            begin = self.last_completion
            end = len(begin) + len(after)
            self.hit_list.append(self.hit_list.pop(0))  # rotate list

        self.text = self.text[:pos - end] + self.text[pos:]
        pos -= end
        hit = self.hit_list[0]  # take the first hit
        self.text = self.text[:pos] + hit + after + self.text[pos:]
        for _ in range(end):
            try:
                self.key_left(reset=False)
            except:
                pass
        for _ in range(len(hit) + len(after)):
            self.key_right(reset=False)

        self.rewrite_text()
        self.last_completion = hit

    def do_command(self, key, reset=True, raw=False):
        if key in self.key_func:
            res = self.key_func[key]()
            if not raw and self.on_input is not DEFAULT_ON_INPUT:
                self.on_input(self.get_text())
            return res
        if not raw and (not key or len(key) > 1):
            return False  # ignore non-handled keyboard shortcuts
        if reset:
            self.reset_completion()
        # Insert the char at the cursor position
        self.text = self.text[:self.pos] + key + self.text[self.pos:]
        self.pos += len(key)
        if reset:
            self.rewrite_text()
        if self.on_input is not DEFAULT_ON_INPUT:
            self.on_input(self.get_text())

        return True

    def add_line_break(self):
        """
        Add a (real) \n to the line
        """
        self.do_command('\n')

    def get_text(self):
        """
        Return the text entered so far
        """
        return self.text

    def _addstr_colored_lite(self, text, y=None, x=None):
        """
        Just like addstr_colored, with the single-char attributes
        (\x0E to \x19 instead of \x19 + attr). We do not use any }
        char in this version
        """
        chars = format_chars + '\n'
        if y is not None and x is not None:
            self.move(y, x)
        format_char = find_first_format_char(text, chars)
        attr_italic = curses.A_ITALIC if hasattr(
            curses, 'A_ITALIC') else curses.A_REVERSE
        while format_char != -1:
            if text[format_char] == '\n':
                attr_char = '|'
            else:
                attr_char = self.text_attributes[format_chars.index(
                    text[format_char])]
            self.addstr(text[:format_char])
            self.addstr(attr_char, curses.A_REVERSE)
            text = text[format_char + 1:]
            if attr_char == 'o':
                self._win.attrset(0)
            elif attr_char == 'u':
                self._win.attron(curses.A_UNDERLINE)
            elif attr_char == 'b':
                self._win.attron(curses.A_BOLD)
            elif attr_char == 'i':
                self._win.attron(attr_italic)
            elif attr_char in string.digits and attr_char != '':
                self._win.attron(to_curses_attr((int(attr_char), -1)))
            format_char = find_first_format_char(text, chars)
        self.addstr(text)

    def rewrite_text(self):
        """
        Refresh the line onscreen, but first, always adjust the
        view_pos.  Also, each FORMAT_CHAR+attr_char count only take
        one screen column (this is done in _addstr_colored_lite), we
        have to do some special calculations to find the correct
        length of text to display, and the position of the cursor.
        """
        self.adjust_view_pos()
        text = self.text
        self._win.erase()
        if self.color:
            self._win.attron(to_curses_attr(self.color))
        displayed_text = text[self.view_pos:self.view_pos + self.width -
                              1].replace('\t', '\x18')
        self._win.attrset(0)
        self._addstr_colored_lite(displayed_text)
        # Fill the rest of the line with the input color
        if self.color:
            (_, x) = self._win.getyx()
            size = self.width - x
            self.addnstr(' ' * size, size, to_curses_attr(self.color))
        self.addstr(0, poopt.wcswidth(
            displayed_text[:self.pos - self.view_pos]), '')
        if self.color:
            self._win.attroff(to_curses_attr(self.color))
        curses.curs_set(1)
        self._refresh()

    def adjust_view_pos(self):
        """
        Adjust the position of the View, if needed (for example if the
        cursor moved and would now be out of the view, we adapt the
        view_pos so that we can always see our cursor)
        """
        # start of the input
        if self.pos == 0:
            self.view_pos = 0
            return
        # cursor outside of the screen (left)
        if self.pos <= self.view_pos:
            self.view_pos = self.pos - max(1 * self.width // 3, 1)
        # cursor outside of the screen (right)
        elif self.pos >= self.view_pos + self.width - 1:
            self.view_pos = self.pos - max(2 * self.width // 3, 2)

        if self.view_pos < 0:
            self.view_pos = 0

        # text small enough to fit inside the window entirely:
        # remove scrolling if present
        if poopt.wcswidth(self.text) < self.width:
            self.view_pos = 0

    def refresh(self):
        log.debug('Refresh: %s', self.__class__.__name__)
        self.rewrite_text()

    def clear_text(self):
        self.text = ''
        self.pos = 0
        self.rewrite_text()

    def key_enter(self):
        txt = self.get_text()
        self.clear_text()
        return txt


class HistoryInput(Input):
    """
    An input with colors and stuff, plus an history
    ^R allows to search inside the history (as in a shell)
    """
    history = []

    def __init__(self):
        Input.__init__(self)
        self.help_message = ''
        self.histo_pos = -1
        self.current_completed = ''
        self.key_func['^R'] = self.toggle_search
        self.search = False
        if config.get('separate_history'):
            self.history = []

    def toggle_search(self):
        if self.help_message:
            return
        self.search = not self.search
        self.refresh()

    def update_completed(self):
        """
        Find a match for the current text
        """
        if not self.text:
            return
        for i in self.history:
            if self.text in i:
                self.current_completed = i
                return
        self.current_completed = ''

    def history_enter(self):
        """
        Enter was pressed, set the text to the
        current completion and disable history
        search
        """
        if self.search:
            self.search = False
            if self.current_completed:
                self.text = self.current_completed
                self.current_completed = ''
            self.refresh()
            return True
        self.refresh()
        return False

    def key_up(self):
        """
        Get the previous line in the history
        """
        self.reset_completion()
        if self.histo_pos == -1 and self.get_text():
            if not self.history or self.history[0] != self.get_text():
                # add the message to history, we do not want to lose it
                self.history.insert(0, self.get_text())
                self.histo_pos += 1
        if self.histo_pos < len(self.history) - 1:
            self.histo_pos += 1
            self.text = self.history[self.histo_pos]
        self.key_end()
        return True

    def key_down(self):
        """
        Get the next line in the history
        """
        self.reset_completion()
        if self.histo_pos > 0:
            self.histo_pos -= 1
            self.text = self.history[self.histo_pos]
        elif self.histo_pos <= 0 and self.get_text():
            if not self.history or self.history[0] != self.get_text():
                # add the message to history, we do not want to lose it
                self.history.insert(0, self.get_text())
            self.text = ''
            self.histo_pos = -1
        self.key_end()
        return True


class MessageInput(HistoryInput):
    """
    The input featuring history and that is being used in
    Conversation, Muc and Private tabs
    Also letting the user enter colors or other text markups
    """
    history = []  # The history is common to all MessageInput

    def __init__(self):
        HistoryInput.__init__(self)
        self.last_completion = None
        self.key_func["KEY_UP"] = self.key_up
        self.key_func["M-A"] = self.key_up
        self.key_func["KEY_DOWN"] = self.key_down
        self.key_func["M-B"] = self.key_down
        self.key_func['^C'] = self.enter_attrib

    def enter_attrib(self):
        """
        Read one more char (c), add the corresponding char from formats_char to the text string
        """

        def cb(attr_char):
            if attr_char in self.text_attributes:
                char = format_chars[self.text_attributes.index(attr_char)]
                self.do_command(char, False)
                self.rewrite_text()

        keyboard.continuation_keys_callback = cb

    def key_enter(self):
        if self.history_enter():
            return

        txt = self.get_text()
        if len(txt) != 0:
            if not self.history or self.history[0] != txt:
                # add the message to history, but avoid duplicates
                self.history.insert(0, txt)
            self.histo_pos = -1
        self.clear_text()
        return txt


class CommandInput(HistoryInput):
    """
    An input with an help message in the left, with three given callbacks:
    one when when successfully 'execute' the command and when we abort it.
    The last callback is optional and is called on any input key
    This input is used, for example, in the RosterTab when, to replace the
    HelpMessage when a command is started
    The on_input callback
    """
    history = []

    def __init__(self, help_message, on_abort, on_success, on_input=None):
        HistoryInput.__init__(self)
        self.on_abort = on_abort
        self.on_success = on_success
        if on_input:
            self.on_input = on_input
        else:
            self.on_input = DEFAULT_ON_INPUT
        self.help_message = help_message
        self.key_func['^M'] = self.success
        self.key_func['^G'] = self.abort
        self.key_func['^C'] = self.abort
        self.key_func["KEY_UP"] = self.key_up
        self.key_func["M-A"] = self.key_up
        self.key_func["KEY_DOWN"] = self.key_down
        self.key_func["M-B"] = self.key_down

    def do_command(self, key, reset=True, raw=False):
        res = Input.do_command(self, key, reset=reset, raw=raw)
        if self.on_input is not DEFAULT_ON_INPUT:
            self.on_input(self.get_text())
        return res

    def disable_history(self):
        """
        Disable the history (up/down) keys
        """
        if 'KEY_UP' in self.key_func:
            del self.key_func['KEY_UP']
        if 'KEY_DOWN' in self.key_func:
            del self.key_func['KEY_DOWN']

    @property
    def history_disabled(self):
        return 'KEY_UP' not in self.key_func and 'KEY_DOWN' not in self.key_func

    def success(self):
        """
        call the success callback, passing the text as argument
        """
        self.on_input = DEFAULT_ON_INPUT
        if self.search:
            self.history_enter()
        res = self.on_success(self.get_text())
        return res

    def abort(self):
        """
        Call the abort callback, passing the text as argument
        """
        self.on_input = DEFAULT_ON_INPUT
        return self.on_abort(self.get_text())

    def on_delete(self):
        """
        SERIOUSLY BIG WTF.

        I can do
        self.key_func.clear()

        but not
        del self.key_func
        because that would raise an AttributeError exception. WTF.
        """
        self.on_abort = None
        self.on_success = None
        self.on_input = DEFAULT_ON_INPUT
        self.key_func.clear()

    def key_enter(self):
        txt = self.get_text()
        if len(txt) != 0:
            if not self.history or self.history[0] != txt:
                # add the message to history, but avoid duplicates
                self.history.insert(0, txt)
            self.histo_pos = -1
