# -*- coding: utf-8 -*-
""" SplashScreen.py

This file represents the splash screen window, and the underlying
logic required for it. It loads the corresponding Glade file, of
the same name.
"""

import threading
import time
from gi.repository import Gtk, Gdk, GLib
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
import re


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

            # The RPC server may not be running at this point yet.
            # The daemon may be busy updating the database (importing blocks from blockchain storage).
            # Need to wait until the RPC server is running before continuing.
            GLib.idle_add(self.update_status, "Waiting for RPC server...")
            splash_logger.info("Waiting for RPC server...")

            # Continuously send a request to the RPC server until we get a response.
            while global_variables.wallet_connection.walletd.poll() is None:
                try:
                    global_variables.wallet_connection.request('getStatus')
                    break
                except ConnectionError:
                    time.sleep(1)

            block_count = 0
            known_block_count = 0
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

                    # The known block count occasionally temporarily drops
                    # If it drops below the block count, we don't want to prematurely open the wallet
                    if resp['knownBlockCount'] < known_block_count:
                        splash_logger.warning("Known block count {} has dropped from its previous value {}".format(resp['knownBlockCount'], known_block_count))
                        continue

                    block_count = resp['blockCount']
                    known_block_count = resp['knownBlockCount']

                    # It's possible the RPC server is running but the daemon hasn't received
                    # the known block count yet. We need to wait on that before comparing block height.
                    if known_block_count == 0:
                        GLib.idle_add(self.update_status, "Waiting on known block count...")
                        continue

                    days_behind = ((known_block_count - block_count) * 30) / (60 * 60 * 24)
                    percent_synced = int((float(block_count) / float(known_block_count)) * 100)

                    GLib.idle_add(self.update_status, "Synchronizing...{}%\n[{} / {}] ({} days behind)".format(percent_synced, block_count, known_block_count, days_behind))
                    splash_logger.debug("Synchronizing...{}% [{} / {}] ({} days behind)".format(percent_synced, block_count, known_block_count, days_behind))
                    # Even though we check known block count, leaving it in there in case of weird edge cases
                    # Buffer the block count by 1 due to latency issues, remote node will almost always be ahead by one
                    if (known_block_count > 0) and (block_count+1 >= known_block_count):
                        GLib.idle_add(self.update_status, "Wallet is synchronized, opening...")
                        splash_logger.info("Wallet successfully synchronized, opening wallet")
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

    def create_wallet(self, name, password, view_key=None, spend_key=None):
        """
        This function is responsible for creating a wallet from the daemon.
        The user gives the name and password (and private keys if importing) on a prompt, which is passed here.
        :return: Process Object Return Code
        """
        walletd_args = [
            get_wallet_daemon_path(),
            '-w', os.path.join(cur_dir, name + ".wallet"),
            '-p', password,
            '-g'
        ]
        if view_key:
            walletd_args.extend(['--view-key', view_key])
        if spend_key:
            walletd_args.extend(['--spend-key', spend_key])
        walletd = Popen(walletd_args)
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
        logoimg.set_from_file("TurtleLogo.png")

        #Wallet name
        walletLabel = Gtk.Label()
        walletLabel.set_markup("Opening <u>{}</u>".format(os.path.splitext(os.path.basename(global_variables.wallet_config['walletPath']))[0]))
        walletLabel.set_margin_bottom(2)

        #password label
        passLabel = Gtk.Label()
        passLabel.set_markup("<b>Please enter the wallet password:</b>")
        passLabel.set_margin_bottom(2)

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
        dialog_box.pack_end(walletLabel, False, False, 0)
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

    def prompt_wallet_import(self):
        """
        Prompt the user to import a wallet, if they selected to import a wallet.
        User enters a name, password, and keys for the wallet.
        The password is checked twice and compared to ensure its correct.
        :return: Returns a Tuple of Wallet Name, Password, View Key, Spend Key on success, string error on fail, or None on Cancel
        """
        dialog = Gtk.MessageDialog(self.window,
                                   Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   Gtk.MessageType.QUESTION,
                                   Gtk.ButtonsType.OK_CANCEL,
                                   "Wallet Name:")

        dialog.set_title("Please import your wallet")

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

        viewKeyLabel = Gtk.Label("View Key:")
        viewKeyEntry = Gtk.Entry()
        viewKeyEntry.set_visibility(True)
        viewKeyEntry.set_size_request(500, 0)

        spendKeyLabel = Gtk.Label("Spend Key:")
        spendKeyEntry = Gtk.Entry()
        spendKeyEntry.set_visibility(True)
        spendKeyEntry.set_size_request(500, 0)

        # Trigger the dialog's response when a user hits ENTER on the text box.
        # The lamba here is a wrapper to get around the default arguments
        passEntryConfirm.connect("activate", lambda w: dialog.response(Gtk.ResponseType.OK))

        # Pack the back right to left, no expanding, no filling, 0 padding
        dialog_box.pack_end(spendKeyEntry, False, False, 0)
        dialog_box.pack_end(spendKeyLabel, False, False, 0)
        dialog_box.pack_end(viewKeyEntry, False, False, 0)
        dialog_box.pack_end(viewKeyLabel, False, False, 0)
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
        viewKeyText = viewKeyEntry.get_text()
        spendKeyText = spendKeyEntry.get_text()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            if nameText == "":
                return "Invalid name for wallet"
            elif passText != passConfirmText:
                return "Given passwords do not match"
            elif viewKeyText == "" or spendKeyText == "":
                return "Both view and spend keys must be specified"
            else:
                #return Tuple of information
                return (nameText,passText,viewKeyText,spendKeyText)
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
        selectLabel.set_markup("<b>Select your Turtle Wallet:</b>")
        selectLabel.set_margin_bottom(5)
        dialog_box.pack_end(selectLabel, False, False, 0)
        dialog_box.pack_end(logoimg, False, False, 0)
        create_button = dialog.add_button("Create New", 8)
        select_button = dialog.add_button("Open Existing", 9)
        import_button = dialog.add_button("Import Keys", 10)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.show_all()
        create_button.grab_default()
        dialog.show_all()
        # Runs dialog and waits for the response
        response = dialog.run()
        dialog.destroy()
        return response

    def prompt_node(self):
        """
        Display a dialog that prompts the user whether they want to connect to a local or remote node.
        :return: Gtk.ResponseType
        """
        dialog = Gtk.Dialog()
        dialog.set_title("Select Node")
        dialog_content = dialog.get_content_area()

        # Load CSS to allow for styling dialog elements
        screen = Gdk.Screen.get_default()
        gtk_provider = Gtk.CssProvider()
        gtk_context = Gtk.StyleContext()
        gtk_context.add_provider_for_screen(screen, gtk_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        gtk_provider.load_from_data("""
        #remote_node_address.red { background-image: linear-gradient(red); }
        """)

        ok_button = dialog.add_button("OK", Gtk.ResponseType.OK)
        ok_button.grab_default()
        cancel_button = dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.pack_end(ok_button, False, False, 5)
        button_box.pack_end(cancel_button, False, False, 5)

        label = Gtk.Label()
        label.set_markup("<b>Do you want to run a local node or connect to a remote node?</b>")
        label.set_padding(5, 5)

        def on_radio_button_toggled(radio_button, option):
            if radio_button.get_active():
                if option == "local":
                    # Local is selected, so disable the remote node text box
                    remote_node_address.set_sensitive(False)
                    remote_node_address.get_style_context().remove_class("red")  # Remove any highlighting
                    ok_button.set_sensitive(True)   # Ensure OK is enabled
                elif option == "remote":
                    # Remote is selected, so enable the remote node text box
                    remote_node_address.set_sensitive(True)
                    validate_remote_node_address(remote_node_address)   # Reapply any highlighting if necessary

        local_node_radio_button = Gtk.RadioButton.new_with_label_from_widget(None, "Local Node")
        local_node_radio_button.connect("toggled", on_radio_button_toggled, "local")
        remote_node_radio_button = Gtk.RadioButton.new_from_widget(local_node_radio_button)
        remote_node_radio_button.set_label("Remote Node")
        remote_node_radio_button.connect("toggled", on_radio_button_toggled, "remote")
        radio_button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        radio_button_box.pack_start(local_node_radio_button, False, False, 0)
        radio_button_box.pack_start(remote_node_radio_button, False, False, 0)

        def validate_remote_node_address(entry):
            entry_style_context = entry.get_style_context()
            regex = re.compile(
                r"^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}:[0-9]{1,5}(\/)?$",
                re.IGNORECASE)
            if re.match(regex, remote_node_address.get_text()) is None:
                # Invalid address so add the red class which will style the element with a red background
                entry_style_context.add_class("red")
                ok_button.set_sensitive(False)  # Prevent the user from clicking OK
            else:
                # Remove the red class to remove the styling applied to the element
                entry_style_context.remove_class("red")
                ok_button.set_sensitive(True)   # Allow the user to click OK

        remote_node_address = Gtk.Entry()
        remote_node_address.set_name("remote_node_address")  # This will be used as the ID of the element
        remote_node_address.set_sensitive(False)    # Disable this element since Local is the default option
        remote_node_address.connect("changed", validate_remote_node_address)

        # Check the config in case the remote daemon settings are already defined
        remote_daemon_address = global_variables.wallet_config.get('remoteDaemonAddress', None)
        remote_daemon_port = global_variables.wallet_config.get('remoteDaemonPort', None)
        if remote_daemon_address and remote_daemon_port:
            remote_node_address.set_text("%s:%s" % (remote_daemon_address, remote_daemon_port))
        else:
            # Thanks to iburnmycd for providing a public daemon service!
            remote_node_address.set_text("public.turtlenode.io:11898")

        dialog_content.pack_start(label, False, False, 0)
        dialog_content.pack_end(remote_node_address, False, False, 5)
        dialog_content.pack_end(radio_button_box, False, False, 5)
        dialog_content.pack_end(button_box, False, False, 5)

        dialog.set_position(Gtk.WindowPosition.CENTER)

        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            if remote_node_address.is_sensitive():
                # Remote option is selected so parse the address and port
                remote_daemon_address, remote_daemon_port = remote_node_address.get_text().rsplit(':', 1)
                global_variables.wallet_config['remoteDaemon'] = True
                global_variables.wallet_config['remoteDaemonAddress'] = remote_daemon_address
                global_variables.wallet_config['remoteDaemonPort'] = remote_daemon_port
            else:
                # Local option is selected so disable remote daemon
                global_variables.wallet_config['remoteDaemon'] = False

            # Save the settings to the config file
            with open(global_variables.wallet_config_file, 'w') as cFile:
                cFile.write(json.dumps(global_variables.wallet_config))

        dialog.destroy()

        return response

    def __init__(self, wallet_file_path=None):

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
                try:
                    global_variables.wallet_config = json.loads(cFile.read())
                except ValueError:
                    splash_logger.error("Failed to decode the JSON file, using defaults")
                    defaults = {"hasWallet": False, "walletPath": ""}
                    global_variables.wallet_config = defaults
        else:
            #No config file, create it
            with open(global_variables.wallet_config_file, 'w') as cFile:
                defaults = {"hasWallet": False, "walletPath": ""}
                global_variables.wallet_config = defaults
                cFile.write(json.dumps(defaults))

        if wallet_file_path:
            global_variables.wallet_config['walletPath'] = wallet_file_path
            global_variables.wallet_config['hasWallet'] = True

        #If this config has seen a wallet before, skip creation dialog
        if "hasWallet" in global_variables.wallet_config and global_variables.wallet_config['hasWallet']:
            #If user has saved path in config for wallet, use it and simply prompt password (They can change wallets at prompt also)
            if "walletPath" in global_variables.wallet_config and global_variables.wallet_config['walletPath'] and os.path.exists(global_variables.wallet_config['walletPath']):
                wallet_password = self.prompt_wallet_password()
                if wallet_password[0] is None:
                    splash_logger.info("Invalid password")
                    self.startup_cancelled = True
                elif not wallet_password[0]:
                    #chose to use different wallet, cache old wallet just in case, rewrite config, and reset
                    global_variables.wallet_config['cachedWalletPath'] = global_variables.wallet_config['walletPath']
                    global_variables.wallet_config['walletPath'] = ""
                    global_variables.wallet_config['hasWallet'] = False
                    with open(global_variables.wallet_config_file, 'w') as cFile:
                        cFile.write(json.dumps(global_variables.wallet_config))
                    self.__init__()
                elif wallet_password[0]:
                    if "remoteDaemon" not in global_variables.wallet_config:
                        if self.prompt_node() != Gtk.ResponseType.OK:
                            self.startup_cancelled = True
                            return

                    # Show the window
                    self.window.show()

                    # Start the wallet initialisation on a new thread
                    thread = threading.Thread(target=self.initialise, args=(global_variables.wallet_config['walletPath'], wallet_password[1]))
                    thread.start()
                else:
                    self.startup_cancelled = True
            else:
                #If we are here, it means the user has a wallet, but none are default, prompt for wallet.
                global_variables.wallet_config['walletPath'] = self.prompt_wallet_dialog()
                if global_variables.wallet_config['walletPath']:
                    splash_logger.info("Using wallet: " + global_variables.wallet_config['walletPath'])
                    wallet_password = self.prompt_wallet_password()
                    if wallet_password[0] is None:
                        splash_logger.info("Invalid password")
                        self.startup_cancelled = True
                    elif not wallet_password[0]:
                        #chose to use different wallet, cache old wallet just in case, rewrite config, and reset
                        global_variables.wallet_config['cachedWalletPath'] = global_variables.wallet_config['walletPath']
                        global_variables.wallet_config['walletPath'] = ""
                        with open(global_variables.wallet_config_file, 'w') as cFile:
                            cFile.write(json.dumps(global_variables.wallet_config))
                        self.__init__()
                    elif wallet_password[0]:
                        if "remoteDaemon" not in global_variables.wallet_config:
                            if self.prompt_node() != Gtk.ResponseType.OK:
                                self.startup_cancelled = True
                                return

                        # Show the window
                        self.window.show()

                        # Start the wallet initialisation on a new thread
                        thread = threading.Thread(target=self.initialise, args=(global_variables.wallet_config['walletPath'], wallet_password[1]))
                        thread.start()
                    else:
                        self.startup_cancelled = True
                else:
                    splash_logger.warn(global_variables.message_dict["NO_INFO"])
                    global_variables.wallet_config["hasWallet"] = False
                    with open(global_variables.wallet_config_file, 'w') as cFile:
                        cFile.write(json.dumps(global_variables.wallet_config))
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
                    if "remoteDaemon" not in global_variables.wallet_config:
                        if self.prompt_node() != Gtk.ResponseType.OK:
                            self.startup_cancelled = True
                            return
                    self.window.show()
                    # Start the wallet initialisation on a new thread
                    thread = threading.Thread(target=self.initialise, args=(os.path.join(cur_dir,createReturn[0] + ".wallet"), createReturn[1]))
                    thread.start()
            elif response == 9:
                #select wallet
                global_variables.wallet_config['walletPath'] = self.prompt_wallet_dialog()
                if global_variables.wallet_config['walletPath']:
                    splash_logger.info("Using wallet: " + global_variables.wallet_config['walletPath'])
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
                        if "remoteDaemon" not in global_variables.wallet_config:
                            if self.prompt_node() != Gtk.ResponseType.OK:
                                self.startup_cancelled = True
                                return

                        # Show the window
                        self.window.show()

                        # Start the wallet initialisation on a new thread
                        thread = threading.Thread(target=self.initialise, args=(global_variables.wallet_config['walletPath'], wallet_password[1]))
                        thread.start()
                    else:
                        self.startup_cancelled = True
                else:
                    splash_logger.warn(global_variables.message_dict["NO_INFO"])
                    self.startup_cancelled = True
            elif response == 10:
                # import wallet
                importReturn = self.prompt_wallet_import()
                if importReturn is None:
                    splash_logger.warn(global_variables.message_dict["NO_INFO"])
                    self.startup_cancelled = True
                elif isinstance(importReturn, basestring):
                    #error on import, display prompt and restart
                    err_dialog = self.SplashScreen_generic_dialog(importReturn,"Error on wallet import")
                    self.__init__()
                elif isinstance(importReturn, tuple):
                    self.create_wallet(importReturn[0],importReturn[1],importReturn[2],importReturn[3])
                    self.window.show()
                    # Start the wallet initialisation on a new thread
                    thread = threading.Thread(target=self.initialise, args=(os.path.join(cur_dir,importReturn[0] + ".wallet"), importReturn[1]))
                    thread.start()
            else:
                self.startup_cancelled = True
