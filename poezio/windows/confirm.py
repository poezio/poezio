from poezio.windows.base_wins import Win

from poezio.theming import get_theme, to_curses_attr


class Dialog(Win):
    __slots__ = ('text', 'accept', 'critical')

    str_accept = " Accept "
    str_refuse = " Reject "

    def __init__(self, helper_text: str, critical: bool = False) -> None:
        self.text = helper_text
        self.accept = False
        self.critical = critical

    def refresh(self) -> None:
        self._win.erase()
        self.addstr(self.text + "\n   ")

        if self.critical:
            col = to_curses_attr(get_theme().COLOR_WARNING_PROMPT)
        else:
            col = to_curses_attr(get_theme().COLOR_TAB_NORMAL)

        if self.accept:
            self.addstr(self.str_accept, col)
        else:
            self.addstr(self.str_accept)

        self.addstr("   ")

        if self.accept:
            self.addstr(self.str_refuse)
        else:
            self.addstr(self.str_refuse, col)

        self._refresh()

    def toggle_choice(self) -> None:
        self.accept = not self.accept
