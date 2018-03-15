# -*- coding: utf-8 -*-
""" HelperFunctions.py

Stores commonly used functions used across the wallet
"""
import os
from gi.repository import Gtk, Gdk
import global_variables
from uuid import uuid4

def get_wallet_daemon_path():
    """
    Tries to find where walletd exists. Looks for TURTLE_HOME env and falls
    back to looking at the current working directory.
    For Windows (nt), the extension .exe is appended.
    :return: path to the walletd executable
    
    Note: We need a duplicate of this function in the splash to find the exe,
    to create a wallet before connection happens.
    """
    walletd_filename = "walletd" if os.name != 'nt' else "walletd.exe"
    walletd_exec = os.path.join(os.getenv('TURTLE_HOME', '.'), walletd_filename)
    if not os.path.isfile(walletd_exec):
        WC_logger.error("Cannot find wallet at location: {}".format(walletd_exec))
        raise ValueError("Cannot find wallet at location: {}".format(walletd_exec))

    return walletd_exec



def copy_text(text_to_copy, length=-1):
    """
    Copy text to the GTK clipboard
    :param text_to_copy: string to copy to the clipboard
    :param length: length of text to copy or -1 to copy the entire string
    :return:
    """
    # From GTK doc: copies the text and the length of text, in bytes, or -1, to calculate the length
    Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text_to_copy, -1)


def get_rpc_password():
    return str(uuid4())

