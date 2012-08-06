"""
Module related to the argument parsing

There is a fallback to the deprecated optparse if argparse is not found
"""
from os import path

def parse_args(CONFIG_PATH=''):
    """
    Parse the arguments from the command line
    """
    try:
        from argparse import ArgumentParser, SUPPRESS
    except ImportError:
        from optparse import OptionParser
        from optparse import SUPPRESS_HELP as SUPPRESS
        parser = OptionParser()
        parser.add_option("-f", "--file", dest="filename", default=path.join(CONFIG_PATH, 'poezio.cfg'),
                            help="The config file you want to use", metavar="CONFIG_FILE")
        parser.add_option("-d", "--debug", dest="debug",
                            help="The file where debug will be written", metavar="DEBUG_FILE")
        parser.add_option("-v", "--version", dest="version",
                            help=SUPPRESS, metavar="VERSION", default="0.8-dev")
        (options, args) = parser.parse_args()
    else:
        parser = ArgumentParser()
        parser.add_argument("-f", "--file", dest="filename", default=path.join(CONFIG_PATH, 'poezio.cfg'),
                            help="The config file you want to use", metavar="CONFIG_FILE")
        parser.add_argument("-d", "--debug", dest="debug",
                            help="The file where debug will be written", metavar="DEBUG_FILE")
        parser.add_argument("-v", "--version", dest="version",
                            help=SUPPRESS, metavar="VERSION", default="0.8-dev")
        options = parser.parse_args()
    return options
