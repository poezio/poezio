import poezio.theming

class CleanTheme(poezio.theming.Theme):
    # Message text color
    COLOR_NORMAL_TEXT = (-1, -1)
    COLOR_INFORMATION_TEXT = (12, -1) # TODO
    COLOR_WARNING_TEXT = (1, -1)

    # Color of the commands in the help message
    COLOR_HELP_COMMANDS = (208, -1)

    # "reverse" is a special value, available only for this option. It just
    # takes the nick colors and reverses it. A theme can still specify a
    # fixed color if need be.
    COLOR_HIGHLIGHT_NICK = "reverse"

    # Color of the participant JID in a MUC
    COLOR_MUC_JID = (4, -1)

    # User list color
    COLOR_USER_VISITOR = (239, -1)
    COLOR_USER_PARTICIPANT = (4, -1)
    COLOR_USER_NONE = (0, -1)
    COLOR_USER_MODERATOR = (1, -1)

    # nickname colors
    COLOR_REMOTE_USER = (13, -1)

    # The character printed in color (COLOR_STATUS_*) before the nickname
    # in the user list
    CHAR_STATUS = '┃'
    #CHAR_STATUS = '●'
    #CHAR_STATUS = '◆'

    # The characters used for the chatstates in the user list
    # in a MUC
    CHAR_CHATSTATE_ACTIVE = 'A'
    CHAR_CHATSTATE_COMPOSING = 'X'
    CHAR_CHATSTATE_PAUSED = 'p'

    # These characters are used for the affiliation in the user list
    # in a MUC
    CHAR_AFFILIATION_OWNER = '~'
    CHAR_AFFILIATION_ADMIN = '&'
    CHAR_AFFILIATION_MEMBER = '+'
    CHAR_AFFILIATION_NONE = '-'


    # XML Tab
    CHAR_XML_IN = 'IN '
    CHAR_XML_OUT = 'OUT'
    COLOR_XML_IN = (1, -1)
    COLOR_XML_OUT = (2, -1)

    # Color for the /me message
    COLOR_ME_MESSAGE = (6, -1)

    # Color for the number of revisions of a message
    COLOR_REVISIONS_MESSAGE = (3, -1, 'b')

    # Color for various important text. For example the "?" before JIDs in
    # the roster that require an user action.
    COLOR_IMPORTANT_TEXT = (3, 5, 'b')

    # Separators
    COLOR_VERTICAL_SEPARATOR = (4, -1)
    COLOR_NEW_TEXT_SEPARATOR = (2, -1)
    COLOR_MORE_INDICATOR = (6, 4)

    # Time
    CHAR_TIME_LEFT = ''
    CHAR_TIME_RIGHT = ''
    COLOR_TIME_STRING = (-1, -1)

    # Tabs
    COLOR_TAB_NORMAL = (-1, 0)
    COLOR_TAB_NONEMPTY = (7, 4)
    COLOR_TAB_SCROLLED = (5, 4)
    COLOR_TAB_JOINED = (82, 4)
    COLOR_TAB_CURRENT = (0, 13)
    COLOR_TAB_COMPOSING = (7, 5)
    COLOR_TAB_NEW_MESSAGE = (7, 5)
    COLOR_TAB_HIGHLIGHT = (7, 3)
    COLOR_TAB_PRIVATE = (7, 2)
    COLOR_TAB_ATTENTION = (7, 1)
    COLOR_TAB_DISCONNECTED = (7, 8)

    COLOR_VERTICAL_TAB_NORMAL = (4, -1)
    COLOR_VERTICAL_TAB_NONEMPTY = (4, -1)
    COLOR_VERTICAL_TAB_JOINED = (82, -1)
    COLOR_VERTICAL_TAB_SCROLLED = (66, -1)
    COLOR_VERTICAL_TAB_CURRENT = (7, 4)
    COLOR_VERTICAL_TAB_NEW_MESSAGE = (5, -1)
    COLOR_VERTICAL_TAB_COMPOSING = (5, -1)
    COLOR_VERTICAL_TAB_HIGHLIGHT = (3, -1)
    COLOR_VERTICAL_TAB_PRIVATE = (2, -1)
    COLOR_VERTICAL_TAB_ATTENTION = (1, -1)
    COLOR_VERTICAL_TAB_DISCONNECTED = (8, -1)

    # Nickname colors
    # A list of colors randomly attributed to nicks in MUCs
    # Setting more colors makes it harder to have two nicks with the same color,
    # avoiding confusions.
    LIST_COLOR_NICKNAMES = [
        (1, -1), (2, -1), (3, -1), (4, -1), (5, -1), (6, -1), (7, -1),
        (8, -1), (9, -1), (10, -1), (11, -1), (12, -1), (13, -1), (14, -1)
    ]

    # This is your own nickname
    COLOR_OWN_NICK = (-1, -1)

    COLOR_LOG_MSG = (8, -1)
    # This is for in-tab error messages
    COLOR_ERROR_MSG = (9, -1, 'b')
    # Status color
    COLOR_STATUS_XA = (90, 0)
    COLOR_STATUS_NONE = (4, 0)
    COLOR_STATUS_DND = (1, 0)
    COLOR_STATUS_AWAY = (3, 0)
    COLOR_STATUS_CHAT = (2, 0)
    COLOR_STATUS_UNAVAILABLE = (8, 0)
    COLOR_STATUS_ONLINE = (4, 0)

    # Bars
    COLOR_WARNING_PROMPT = (16, 1, 'b')
    COLOR_INFORMATION_BAR = (7, 0)
    COLOR_TOPIC_BAR = (7, 0)
    COLOR_SCROLLABLE_NUMBER = (220, 4, 'b')
    COLOR_SELECTED_ROW = (0, 13)
    COLOR_PRIVATE_NAME = (-1, 4)
    COLOR_CONVERSATION_NAME = (2, 0)
    COLOR_CONVERSATION_RESOURCE = (121, 0)
    COLOR_GROUPCHAT_NAME = (10, 0)
    COLOR_COLUMN_HEADER = (36, 4)
    COLOR_COLUMN_HEADER_SEL = (4, 36)

    # Strings for special messages (like join, quit, nick change, etc)
    # Special messages
    CHAR_JOIN = '--->'
    CHAR_QUIT = '<---'
    CHAR_KICK = '-!-'
    CHAR_NEW_TEXT_SEPARATOR = ' ─'
    CHAR_OK = '✔'
    CHAR_ERROR = '✖'
    CHAR_EMPTY = ' '
    CHAR_ACK_RECEIVED = CHAR_OK
    CHAR_NACK = CHAR_ERROR
    CHAR_COLUMN_ASC = ' ▲'
    CHAR_COLUMN_DESC = ' ▼'
    CHAR_ROSTER_ERROR = CHAR_ERROR
    CHAR_ROSTER_TUNE = '♪'
    CHAR_ROSTER_ASKED = '?'
    CHAR_ROSTER_ACTIVITY = 'A'
    CHAR_ROSTER_MOOD = 'M'
    CHAR_ROSTER_GAMING = 'G'
    CHAR_ROSTER_FROM = '←'
    CHAR_ROSTER_BOTH = '↔'
    CHAR_ROSTER_TO = '→'
    CHAR_ROSTER_NONE = '⇹'

    COLOR_CHAR_ACK = (2, -1)
    COLOR_CHAR_NACK = (1, -1)

    COLOR_ROSTER_GAMING = (6, -1)
    COLOR_ROSTER_MOOD = (2, -1)
    COLOR_ROSTER_ACTIVITY = (3, -1)
    COLOR_ROSTER_TUNE = (6, -1)
    COLOR_ROSTER_ERROR = (1, -1)
    COLOR_ROSTER_SUBSCRIPTION = (-1, -1)

    COLOR_JOIN_CHAR = (4, -1)
    COLOR_QUIT_CHAR = (1, -1)
    COLOR_KICK_CHAR = (1, -1)

    # Vertical tab list color
    COLOR_VERTICAL_TAB_NUMBER = (34, -1)

    # Info messages color (the part before the ">")
    INFO_COLORS = {
            'info': (2, -1),
            'error': (1, -1, 'b'),
            'warning': (1, -1),
            'roster': (2, -1),
            'help': (10, -1),
            'headline': (11, -1, 'b'),
            'tune': (6, -1),
            'gaming': (6, -1),
            'mood': (5, -1),
            'activity': (3, -1),
            'default': (-1, -1),
    }

theme = CleanTheme()
