import poezio.theming

class IrssiTheme(poezio.theming.Theme):
    COLOR_INFORMATION_BAR = (6, 4)

    COLOR_TAB_NEW_MESSAGE = (15, 4)
    COLOR_TAB_CURRENT = (7, 12)
    COLOR_TAB_HIGHLIGHT = (13, 4)
    COLOR_TAB_DISCONNECTED = (9, 4)

    COLOR_HIGHLIGHT_NICK = (11, -1, 'b')
    COLOR_ME_MESSAGE = (15, -1)

    def __init__(self):
        super().__init__()
        self.LIST_COLOR_NICKNAMES = self.LIST_COLOR_NICKNAMES[:]
        self.LIST_COLOR_NICKNAMES.remove((19, -1))
        self.LIST_COLOR_NICKNAMES.remove((20, -1))
        self.LIST_COLOR_NICKNAMES.remove((226, -1))
        self.LIST_COLOR_NICKNAMES.remove((227, -1))

theme = IrssiTheme()


