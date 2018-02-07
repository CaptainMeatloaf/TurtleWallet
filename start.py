# -*- coding: utf-8 -*-
""" start.py

This file launches the wallet and starts the main GTK loop.
"""

import global_variables

import signal
import gi
import argparse
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from SplashScreen import SplashScreen
import logging
from logging.handlers import RotatingFileHandler

# create logger for entire wallet application
logger = logging.getLogger('trtl_log')
logger.setLevel(logging.INFO)
# create handle to log file that will hold all events. This log file
# is rotating, up to 20MB and up to 5 back up logs.
fh = RotatingFileHandler('trtl.log', maxBytes=20971520, backupCount=5)
fh.setLevel(logging.INFO)

#check if a argument has been set
parser = argparse.ArgumentParser()
#add verbosity argument
parser.add_argument('-v', '--verbose', help='Change verbosity to DEBUG', required=False, action='store_true')
args = parser.parse_args()

#check if verbosity arg is set
verbose = args.verbose
if verbose:
    logger.setLevel(logging.DEBUG)
    fh.setLevel(logging.DEBUG)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)

# --- This is the logger for CLI, we do not need it for now.
# ch.setFormatter(formatter)
# logger.addHandler(ch)
# ---

logger.info("Tutle Wallet Stated")
signal.signal(signal.SIGINT, signal.SIG_DFL) # Required to handle interrupts closing the program
logger.info("Starting Splash Screen")
splash_screen = SplashScreen() # Create a new instance of the splash screen

# Make sure the splash screen wasn't cancelled by the user
if not splash_screen.startup_cancelled:
    Gtk.main() # Start the main GTK loop
else:
    logger.info("Tutle Wallet exiting")

if global_variables.wallet_connection:
    logger.info("Stopping wallet daemon")
    global_variables.wallet_connection.stop_wallet_daemon()
