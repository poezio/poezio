from datetime import datetime

FORMAT_CHAR = '\x19'
# These are non-printable chars, so they should never appear in the input,
# I guess. But maybe we can find better chars that are even less risky.
FORMAT_CHARS = '\x0E\x0F\x10\x11\x12\x13\x14\x15\x16\x17\x18\x1A'

# Short date format (only show time)
SHORT_FORMAT = '%H:%M:%S'
SHORT_FORMAT_LENGTH = len(datetime.now().strftime(SHORT_FORMAT))

# Long date format (show date and time)
LONG_FORMAT = '%Y-%m-%d %H:%M:%S'
LONG_FORMAT_LENGTH = len(datetime.now().strftime(LONG_FORMAT))
