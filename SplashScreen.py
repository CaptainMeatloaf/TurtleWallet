# -*- coding: utf-8 -*-
""" SplashScreen.py

This file represents the splash screen window, and the underlying
logic required for it. It loads the corresponding Glade file, of
the same name.
"""

import threading
import time
from gi.repository import Gtk, GLib
from __init__ import __version__
from ConnectionManager import WalletConnection
import global_variables
from HelperFunctions import get_wallet_daemon_path
from requests import ConnectionError
from MainWindow import MainWindow
import logging
import json
import os
from subprocess import Popen


# Maximum attempts to talk to the wallet daemon before giving up
MAX_FAIL_COUNT = 15
cur_dir = os.path.dirname(os.path.realpath(__file__))

# Get Logger made in start.py
splash_logger = logging.getLogger('trtl_log.splash')

class SplashScreen(object):
    """
    This class is used to interact with the SplashScreen glade file
    """
    def on_SplashScreenWindow_delete_event(self, object, data=None):
        """Called by GTK when the user requests the window be closed"""
        Gtk.main_quit() # Quit the GTK main loop to exit

    def update_status(self, message):
        """Updates the status label with a new message"""
        self.status_label.set_label(message) # Set the label text

    def open_main_window(self):
        """Opens the main window, closing the splash window"""
        main_window = MainWindow() # Initialise the main window
        self.window.destroy() # Destroy the splash screen window

    def initialise(self, wallet_file, wallet_password):
        """Initialises the connection to the wallet
            Note: Wallet must already be running at this point"""

        # There will be an exception if there is a failure to connect at any point
        # TODO: Handle exceptions gracefully

        time.sleep(1)
        GLib.idle_add(self.update_status, global_variables.message_dict["CONNECTING_DAEMON"])
        splash_logger.info(global_variables.message_dict["CONNECTING_DAEMON"])
        # Initialise the wallet connection
        # If we fail to talk to the server so many times, it's hopeless
        fail_count = 0
        try:
            global_variables.wallet_connection = WalletConnection(wallet_file, wallet_password)
            # Loop until the block count is greater than or equal to the known block count.
            # This should guarantee us that the daemon is running and synchronized before the main
            # window opens.
            while True:
                time.sleep(1.5)
                try:
                    # In the case that the daemon started but stopped, usually do to an
                    # invalid password.
                    if not global_variables.wallet_connection.check_daemon_running():
                        splash_logger.error(global_variables.message_dict["EXITED_DAEMON"])
                        raise ValueError(global_variables.message_dict["EXITED_DAEMON"])
                    resp = global_variables.wallet_connection.request('getStatus')
                    block_count = resp['blockCount']
                    known_block_count = resp['knownBlockCount']
                    
                    # It's possible the RPC server is running but the daemon hasn't received
                    # the known block count yet. We need to wait on that before comparing block height.
                    if known_block_count == 0:
                        GLib.idle_add(self.update_status, "Waiting on known block count...")
                        continue
                    GLib.idle_add(self.update_status, "Syncing... [{} / {}]".format(block_count, known_block_count))
                    splash_logger.debug("Syncing... [{} / {}]".format(block_count, known_block_count))
                    # Even though we check known block count, leaving it in there in case of weird edge cases
                    # Buffer the block count by 1 due to latency issues, remote node will almost always be ahead by one
                    if (known_block_count > 0) and (block_count+1 >= known_block_count):
                        GLib.idle_add(self.update_status, "Wallet is synced, opening...")
                        splash_logger.info("Wallet successfully synced, opening wallet")
                        break
                except ConnectionError as e:
                    fail_count += 1
                    print(global_variables.message_dict["CONNECTION_ERROR_DAEMON"].format(e))
                    splash_logger.warn(global_variables.message_dict["CONNECTION_ERROR_DAEMON"].format(e))
                    if fail_count >= MAX_FAIL_COUNT:
                        splash_logger.error(global_variables.message_dict["NO_COMM_DAEMON"])
                        raise ValueError(global_variables.message_dict["NO_COMM_DAEMON"])
        except ValueError as e:
            splash_logger.error(global_variables.message_dict["FAILED_CONNECT_DAEMON"].format(e))
            print(global_variables.message_dict["FAILED_CONNECT_DAEMON"].format(e))
            GLib.idle_add(self.update_status, "Failed: {}".format(e))
            time.sleep(3)
            GLib.idle_add(Gtk.main_quit)
        time.sleep(1)
        # Open the main window using glib
        GLib.idle_add(self.open_main_window)
        
        
    def create_wallet(self, name, password):
        """
        This function is responsible for creating a new wallet from the daemon.
        The user gives the name and password on a prompt, which is passed here.
        :return: Process Object Return Code
        """
        walletd = Popen([get_wallet_daemon_path(), '-w', os.path.join(cur_dir, name + ".wallet"), '-p', password, '-g'])
        return walletd.wait()

    def prompt_wallet_dialog(self):
        """
        Prompt the user to select a wallet file.
        :return: The wallet filename or none if they chose to cancel
        """
        # Opens file dialog with Open and Cancel buttons, with action set to OPEN (as compared to SAVE).
        dialog = Gtk.FileChooserDialog("Please select your wallet", self.window,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        response = dialog.run()
        filename = None
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
        dialog.destroy()
        return filename

    def prompt_wallet_password(self):
        """
        Prompt the user for their wallet password
        :return: Returns the user text or none if they chose to cancel
        """
        dialog = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.QUESTION,
                                   Gtk.ButtonsType.OK_CANCEL)

        dialog.set_title("Wallet Password")
        dialog.add_button("Use different wallet", 9)

        # Setup UI for entry box in the dialog
        dialog_box = dialog.get_content_area()
        
        #Logo control
        logoimg = Gtk.Image()
        logoimg.set_from_file ("TurtleLogo.png")
        
        #password label
        passLabel = Gtk.Label()
        passLabel.set_markup("<b>Please enter the wallet password:</b>")
        passLabel.set_margin_bottom(5)
        
        #password entry control
        userEntry = Gtk.Entry()
        userEntry.set_visibility(False)
        userEntry.set_invisible_char("*")
        userEntry.set_size_request(250, 0)
        # Trigger the dialog's response when a user hits ENTER on the text box.
        # The lamba here is a wrapper to get around the default arguments
        userEntry.connect("activate", lambda w: dialog.response(Gtk.ResponseType.OK))
        # Pack the back right to left, no expanding, no filling, 0 padding
        dialog_box.pack_end(userEntry, False, False, 0)
        dialog_box.pack_end(passLabel, False, False, 0)
        dialog_box.pack_end(logoimg, False, False, 0)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.show_all()
        # Runs dialog and waits for the response
        response = dialog.run()
        text = userEntry.get_text()
        dialog.destroy()
        if (response == Gtk.ResponseType.OK) and (text != ''):
            return (True,text)
        elif response == 9:
            #return False tuple if 'Use Different Wallet' is selected, so we may proceed differently on return
            return (False,"")
        else:
            return (None,"")

    def SplashScreen_generic_dialog(self, title, message):
        """
        This is a generic dialog that can be passed a title and message to display, and shows OK and CANCEL buttons.
        Selecting OK will return True and CANCEL will return False
        :return: True or False
        """
        dialog = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.QUESTION,
                                   Gtk.ButtonsType.OK_CANCEL,
                                   title)

        dialog.set_title(message)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        if (response == Gtk.ResponseType.OK):
            return True
        else:
            return False
        
            
    def prompt_wallet_create(self):
        """
        Prompt the user to create a wallet, if they selected to make a wallet.
        User eneters a new for a wallet and a password. The password is
        checked twice and compared to ensure its correct.
        :return: Returns a Tuple of Wallet Name and Password on success, string error on fail, or None on Cancel
        """
        dialog = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.QUESTION,
                                   Gtk.ButtonsType.OK_CANCEL,
                                   "Wallet Name:")

        dialog.set_title("Please create your wallet")

        # Setup UI for entry box in the dialog
        dialog_box = dialog.get_content_area()
        
        namelEntry = Gtk.Entry()
        namelEntry.set_visibility(True)
        namelEntry.set_size_request(250, 0)
        
        passLabel = Gtk.Label("Wallet Password:")
        
        passEntry = Gtk.Entry()
        passEntry.set_visibility(False)
        passEntry.set_invisible_char("*")
        passEntry.set_size_request(250, 0)
        
        passLabelConfirm = Gtk.Label("Confirm Password:")
        
        passEntryConfirm = Gtk.Entry()
        passEntryConfirm.set_visibility(False)
        passEntryConfirm.set_invisible_char("*")
        passEntryConfirm.set_size_request(250, 0)
        # Trigger the dialog's response when a user hits ENTER on the text box.
        # The lamba here is a wrapper to get around the default arguments
        passEntryConfirm.connect("activate", lambda w: dialog.response(Gtk.ResponseType.OK))
        # Pack the back right to left, no expanding, no filling, 0 padding
        dialog_box.pack_end(passEntryConfirm, False, False, 0)
        dialog_box.pack_end(passLabelConfirm, False, False, 0)
        dialog_box.pack_end(passEntry, False, False, 0)
        dialog_box.pack_end(passLabel, False, False, 0)
        dialog_box.pack_end(namelEntry, False, False, 0)

        dialog.show_all()
        # Runs dialog and waits for the response
        response = dialog.run()
        nameText = namelEntry.get_text()
        passText = passEntry.get_text()
        passConfirmText = passEntryConfirm.get_text()
        dialog.destroy()
        if (response == Gtk.ResponseType.OK):
            if nameText == "":
                return "Invalid name for wallet"
            elif passText != passConfirmText:
                return "Given passwords do not match"
            else:
                #return Tuple of information
                return (nameText,passText)
                
        else:
            return None
            
    def prompt_wallet_selection(self):
        """
        Prompt normally shown the first time wallet is ran.
        It will ask the user to select a old wallet or create one.
        """
        dialog = Gtk.Dialog()
        dialog.set_title("TurtleWallet v{0}".format(__version__))
        
        dialog_box = dialog.get_content_area()
        logoimg = Gtk.Image()
        logoimg.set_from_file ("TurtleLogo.png")
        selectLabel = Gtk.Label()
        selectLabel.set_markup("<b>Create or select a Turtle Wallet:</b>")
        selectLabel.set_margin_bottom(5)
        dialog_box.pack_end(selectLabel, False, False, 0)
        dialog_box.pack_end(logoimg, False, False, 0)
        create_button = dialog.add_button("Create Wallet", 8)
        select_button = dialog.add_button("Select Existing Wallet", 9)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.show_all()
        create_button.grab_default()
        dialog.show_all()
        # Runs dialog and waits for the response
        response = dialog.run()
        dialog.destroy()
        return response

    def __init__(self):

        # Flag used to determine if startup is cancelled
        # to prevent the main thread from running.
        self.startup_cancelled = False

        # Initialise the GTK builder and load the glade layout from the file
        self.builder = Gtk.Builder()
        self.builder.add_from_file("SplashScreen.glade")

        # Get the version label on the splash screen
        self.version_label = self.builder.get_object("TurtleWalletVersionLabel")

        # Set the version label to match the version of the package
        self.version_label.set_label(__version__)

        # Get the status label
        self.status_label = self.builder.get_object("StatusLabel")

        # Set the status label value to indicate the program is starting
        self.status_label.set_label("Starting...")

        # Use the methods defined in this class as signal handlers
        self.builder.connect_signals(self)

        # Get the window from the builder
        self.window = self.builder.get_object("SplashScreenWindow")

        # Set the window title to reflect the current version
        self.window.set_title("TurtleWallet v{0}".format(__version__))
        splash_logger.info("TurtleWallet v{0}".format(__version__))

        #Check for config file
        if os.path.exists(global_variables.wallet_config_file):
            with open(global_variables.wallet_config_file) as cFile:
                global_variables.wallet_config = json.loads(cFile.read())
        else:
            #No config file, create it
            with open(global_variables.wallet_config_file, 'w') as cFile:
                defaults = {"hasWallet": False, "walletPath": ""}
                global_variables.wallet_config = defaults
                cFile.write(json.dumps(defaults))
                
        #If this config has seen a wallet before, skip creation dialog
        if "hasWallet" in global_variables.wallet_config and global_variables.wallet_config['hasWallet']:
            #If user has saved path in config for wallet, use it and simply prompt password (They can change wallets at prompt also)
            if "walletPath" in global_variables.wallet_config and global_variables.wallet_config['walletPath'] and os.path.exists(global_variables.wallet_config['walletPath']):
                wallet_password = self.prompt_wallet_password()
                if wallet_password[0] is None:
                    splash_logger.info("Invalid password")
                    self.startup_cancelled = True
                elif wallet_password[0] == False:
                    #chose to use different wallet, cache old wallet just in case, rewrite config, and reset
                    global_variables.wallet_config['cachedWalletPath'] = global_variables.wallet_config['walletPath']
                    global_variables.wallet_config['walletPath'] = ""
                    with open(global_variables.wallet_config_file, 'w') as cFile:
                        cFile.write(json.dumps(global_variables.wallet_config))
                    self.__init__()
                elif wallet_password[0] == True:
                    # Show the window
                    self.window.show()

                    # Start the wallet initialisation on a new thread
                    thread = threading.Thread(target=self.initialise, args=(global_variables.wallet_config['walletPath'], wallet_password[1]))
                    thread.start()
                else:
                    self.startup_cancelled = True
            else:
                #If we are here, it means the user has a wallet, but none are default, prompt for wallet.
                wallet_file = self.prompt_wallet_dialog()
                if wallet_file:
                    splash_logger.info("Using wallet: " + wallet_file) 
                    wallet_password = self.prompt_wallet_password()
                    if wallet_password[0] is None:
                        splash_logger.info("Invalid password")
                        self.startup_cancelled = True
                    elif wallet_password[0] == False:
                        #chose to use different wallet, cache old wallet just in case, rewrite config, and reset
                        global_variables.wallet_config['cachedWalletPath'] = global_variables.wallet_config['walletPath']
                        global_variables.wallet_config['walletPath'] = ""
                        with open(global_variables.wallet_config_file, 'w') as cFile:
                            cFile.write(json.dumps(global_variables.wallet_config))
                        self.__init__()
                    elif wallet_password[0] == True:
                        # Show the window
                        self.window.show()

                        # Start the wallet initialisation on a new thread
                        thread = threading.Thread(target=self.initialise, args=(wallet_file, wallet_password[1]))
                        thread.start()
                    else:
                        self.startup_cancelled = True
                else:
                    splash_logger.warn(global_variables.message_dict["NO_INFO"])
                    self.startup_cancelled = True
        else:
            #Select or create wallet
            response = self.prompt_wallet_selection()
            if response == 8:
                #create wallet
                createReturn = self.prompt_wallet_create()
                if createReturn is None:
                    splash_logger.warn(global_variables.message_dict["NO_INFO"])
                    self.startup_cancelled = True
                elif isinstance(createReturn, basestring):
                    #error on create, display prompt and restart
                    err_dialog = self.SplashScreen_generic_dialog(createReturn,"Error on wallet create")
                    self.__init__()
                elif isinstance(createReturn, tuple):
                    self.create_wallet(createReturn[0],createReturn[1])
                    self.window.show()
                    # Start the wallet initialisation on a new thread
                    thread = threading.Thread(target=self.initialise, args=(os.path.join(cur_dir,createReturn[0] + ".wallet"), createReturn[1]))
                    thread.start()
            else:
                #select wallet
                wallet_file = self.prompt_wallet_dialog()
                if wallet_file:
                    splash_logger.info("Using wallet: " + wallet_file) 
                    wallet_password = self.prompt_wallet_password()
                    if wallet_password[0] is None:
                        splash_logger.info("Invalid password")
                        self.startup_cancelled = True
                    elif wallet_password[0] == False:
                        #chose to use different wallet, cache old wallet just in case, rewrite config, and reset
                        global_variables.wallet_config['cachedWalletPath'] = global_variables.wallet_config['walletPath']
                        global_variables.wallet_config['walletPath'] = ""
                        with open(global_variables.wallet_config_file, 'w') as cFile:
                            cFile.write(json.dumps(global_variables.wallet_config))
                        self.__init__()
                    elif wallet_password[0] == True:
                        # Show the window
                        self.window.show()

                        # Start the wallet initialisation on a new thread
                        thread = threading.Thread(target=self.initialise, args=(wallet_file, wallet_password[1]))
                        thread.start()
                    else:
                        self.startup_cancelled = True
                else:
                    splash_logger.warn(global_variables.message_dict["NO_INFO"])
                    self.startup_cancelled = True
