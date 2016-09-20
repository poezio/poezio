"""
Module related to the argument parsing

There is a fallback to the deprecated optparse if argparse is not found
"""
from os import path
from argparse import ArgumentParser, SUPPRESS

def parse_args(CONFIG_PATH=''):
    """
    Parse the arguments from the command line
    """
    parser = ArgumentParser('poezio')
    parser.add_argument("-c", "--check-config", dest="check_config",
                        action='store_true',
                        help='Check the config file')
    parser.add_argument("-d", "--debug", dest="debug",
                        help="The file where debug will be written",
                        metavar="DEBUG_FILE")
    parser.add_argument("-f", "--file", dest="filename",
                        default=path.join(CONFIG_PATH, 'poezio.cfg'),
                        help="The config file you want to use",
                        metavar="CONFIG_FILE")
    parser.add_argument("-v", "--version", dest="version",
                        help=SUPPRESS, metavar="VERSION",
                        default="0.10-dev")
    options = parser.parse_args()
    return options
