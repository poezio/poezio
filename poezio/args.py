"""
Module related to the argument parsing

There is a fallback to the deprecated optparse if argparse is not found
"""
from pathlib import Path
from argparse import ArgumentParser, SUPPRESS

from poezio.version import __version__


def parse_args(CONFIG_PATH: Path):
    """
    Parse the arguments from the command line
    """
    parser = ArgumentParser('poezio')
    parser.add_argument(
        "-c",
        "--check-config",
        dest="check_config",
        action='store_true',
        help='Check the config file')
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="The file where debug will be written",
        metavar="DEBUG_FILE")
    parser.add_argument(
        "-f",
        "--file",
        dest="filename",
        default=CONFIG_PATH / 'poezio.cfg',
        type=Path,
        help="The config file you want to use",
        metavar="CONFIG_FILE")
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version='Poezio v%s' % __version__,
    )
    parser.add_argument(
        "--custom-version",
        dest="custom_version",
        help=SUPPRESS,
        metavar="VERSION",
        default=__version__
    )
    options = parser.parse_args()
    return options
