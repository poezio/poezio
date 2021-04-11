"""
Module related to the argument parsing
"""
import pkg_resources
import stat
import sys
from argparse import ArgumentParser, SUPPRESS, Namespace
from pathlib import Path
from shutil import copy2
from typing import Tuple

from poezio.version import __version__
from poezio import xdg


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
    return parser.parse_args()


def run_cmdline_args() -> Tuple[Namespace, bool]:
    "Parse the command line arguments"
    options = parse_args(xdg.CONFIG_HOME)
    firstrun = False

    # Copy a default file if none exists
    if not options.filename.is_file():
        try:
            options.filename.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            sys.stderr.write(
                'Poezio was unable to create the config directory: %s\n' % e)
            sys.exit(1)
        default = Path(__file__).parent / '..' / 'data' / 'default_config.cfg'
        other = Path(
            pkg_resources.resource_filename('poezio', 'default_config.cfg'))
        if default.is_file():
            copy2(str(default), str(options.filename))
        elif other.is_file():
            copy2(str(other), str(options.filename))

        # Inside the nixstore and possibly other distributions, the reference
        # file is readonly, so is the copy.
        # Make it writable by the user who just created it.
        if options.filename.exists():
            options.filename.chmod(options.filename.stat().st_mode
                                   | stat.S_IWUSR)
        firstrun = True

    return (options, firstrun)
