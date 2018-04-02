# -*- coding: utf-8 -*-
""" MainWindow.py

This file represents the main wallet window, and the underlying
logic required for it. It loads the corresponding Glade file, of
the same name.
"""

from datetime import datetime
import threading
import time
from gi.repository import Gtk, Gdk, GLib
import tzlocal
from requests import ConnectionError
from __init__ import __version__
import global_variables
import logging
import json
from string import Template

from HelperFunctions import copy_text

# Get Logger made in start.py
main_logger = logging.getLogger('trtl_log.main')

class UILogHandler(logging.Handler):
    """
    This class is a custom Logging.Handler that fires off every time
    a message is added to the applications log. This shows similar to
    what the log file does, but the verbose is set to INFO instead of
    debug to keep logs in UI slim, and logs in the file more beefy.
    """
    def __init__(self, textbuffer):
        logging.Handler.__init__(self)
        self.textbuffer = textbuffer

    def handle(self, rec):
        #everytime logging occurs this handle will add the
        #message to our log textview, however the UI only
        #logs relevant things like TX sends, receives, and errors.
        end_iter = self.textbuffer.get_end_iter() #Gets the position of the end of the string in the logBuffer
        self.textbuffer.insert(end_iter, "\n" + rec.msg) #Appends new message to the end of buffer, which reflects in LogTextView

class MainWindow(object):
    """
    This class is used to interact with the MainWindow glade file
    """
    def on_MainWindow_destroy(self, object, data=None):
        """Called by GTK when the main window is destroyed"""
        Gtk.main_quit() # Quit the GTK main loop
        self._stop_update_thread.set() # Set the event to stop the thread
        threading.Thread.join(self.update_thread, 5) # Wait until the thread terminates

    def on_CopyButton_clicked(self, object, data=None):
        """Called by GTK when the copy button is clicked"""
        self.builder.get_object("AddressTextBox")
        copy_text(self.builder.get_object("AddressTextBox").get_text())

    def on_FeeSuggestionCheck_clicked(self, object, data=None):
        """Called by GTK when the FeeSuggestionCheck Checkbox is Toggled"""
        fee_entry = self.builder.get_object("FeeEntry")
        #Check if FeeSuggestionCheck is checked
        if object.get_active():
            #disable fee entry
            fee_entry.set_sensitive(False)
        else:
            #enable fee entry
            fee_entry.set_sensitive(True)

    def on_LogsMenuItem_activate(self, object, data=None):
        """Called by GTK when the LogsMenuItem Menu Item is Clicked
            This shows the log page on the main window"""
        #Shows the Logs Window
        noteBook = self.builder.get_object("MainNotebook")
        #Get Log Page
        logBox = self.builder.get_object("LogBox")
        #Check if it is already viewed
        if noteBook.page_num(logBox) == -1:
            #If not get the label and page, and show it
            logLabel = self.builder.get_object("LogTabLabel")
            noteBook.append_page(logBox,logLabel)
            self.builder.get_object("LogsMenuItem").set_active(True)
        else:
            noteBook.remove_page(noteBook.page_num(logBox))
            self.builder.get_object("LogsMenuItem").set_active(False)

    def on_RPCMenuItem_activate(self, object, data=None):
        """Called by GTK when the LogsMenuItem Menu Item is Clicked
            This shows the RPC page on the main window"""
        #Shows the RPC Window
        noteBook = self.builder.get_object("MainNotebook")
        #Get RPC Page
        RPCBox = self.builder.get_object("RPCBox")
        #Check if it is already viewed
        if noteBook.page_num(RPCBox) == -1:
            #If not get the label and page, and show it
            RPCLabel = self.builder.get_object("RPCTabLabel")
            noteBook.append_page(RPCBox,RPCLabel)
            self.builder.get_object("RPCMenuItem").set_active(True)
        else:
            noteBook.remove_page(noteBook.page_num(RPCBox))
            self.builder.get_object("RPCMenuItem").set_active(False)

    def on_RPCMethodComboBox_changed(self, object):
        """ Called by GTK when the selected RPC method is changed """
        # Determine which method has been selected
        method = self.rpc_method_list_store[self.builder.get_object("RPCMethodComboBox").get_active()][0]

        # Show the description for the selected method
        self.builder.get_object("RPCMethodDescriptionLabel").set_text(self.RPCCommands[method]['Description'])

        # Get a valid transaction hash (for use within the arguments)
        transaction_hash = ""
        if self.blocks:
            transaction_hash = self.blocks[-1]['transactions'][-1]['transactionHash']

        # Populate the arguments text field with appropriate data based on the selected method
        self.builder.get_object("RPCArgumentsTextBuffer").set_text(self.RPCCommands[method]['Arguments'].safe_substitute(dict(
            address=self.addresses[0] if self.addresses else "",
            transactionHash=transaction_hash
        )))

    def on_rpcSendButton_clicked(self, object, data=None):
        """ Called by GTK when the RPCSend button has been clicked """
        # Determine which method has been selected
        method = self.rpc_method_list_store[self.builder.get_object("RPCMethodComboBox").get_active()][0]

        # Get the arguments
        args_text_buffer = self.builder.get_object("RPCArgumentsTextBuffer")
        start_iter = args_text_buffer.get_start_iter()
        end_iter = args_text_buffer.get_end_iter()
        args = args_text_buffer.get_text(start_iter, end_iter, True)

        # Validate the method and arguments are somewhat valid
        if method == "":
            end_iter = self.RPCbuffer.get_end_iter()
            self.RPCbuffer.insert(end_iter, "> \nERROR: Must specify a method" + "\n\n")
            return
        if args == "":
            # If no arguments specified, assume an empty dictionary
            args_dict = {}
        else:
            try:
                args_dict = json.loads(args)
            except ValueError:
                end_iter = self.RPCbuffer.get_end_iter()
                self.RPCbuffer.insert(end_iter, "> " + method + "()\nERROR: Arguments are not in valid JSON format\n\n")
                return

        # Send the request to RPC server and print results on textview
        try:
            r = global_variables.wallet_connection.request(method, args_dict)
            end_iter = self.RPCbuffer.get_end_iter()
            self.RPCbuffer.insert(end_iter, "> " + method + "()\n" + json.dumps(r) + "\n\n")
        except Exception as e:
            end_iter = self.RPCbuffer.get_end_iter()
            self.RPCbuffer.insert(end_iter, "> " + method + "()\nERROR: " + str(e) + "\n\n")

    def on_rpcClearButton_clicked(self, object, data=None):
        """ Called by GTK when the RPCClear button has been clicked """
        start_iter = self.RPCbuffer.get_start_iter()
        end_iter = self.RPCbuffer.get_end_iter()
        self.RPCbuffer.delete(start_iter, end_iter)

    def on_RPCTextView_size_allocate(self, *args):
        """The GTK Auto Scrolling method used to scroll RPC view when info is added"""
        adj = self.RPCScroller.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def on_LogTextView_size_allocate(self, *args):
        """The GTK Auto Scrolling method used to scroll Log view when info is added"""
        adj = self.LogScroller.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())


    def on_AboutMenuItem_activate(self, object, data=None):
        """Called by GTK when the 'About' menu item is clicked"""
        # Get the about dialog from the builder
        about_dialog = self.builder.get_object("AboutDialog")

        # Set the version on the about dialog to correspond to that of the init file
        about_dialog.set_version("v{0}".format(__version__))

        # Run the dialog and await for it's response (in this case to be closed)
        about_dialog.run()

        # Hide the dialog upon it's closure
        about_dialog.hide()

    def on_ResetMenuItem_activate(self, object, data=None):
        """
        Attempts to call the reset action on the wallet API.
        On success, shows success message to user.
        On error, shows error message to user.
        :param object: unused
        :param data: unused
        :return:
        """
        try:
            global_variables.wallet_connection.request("reset")

            # Re-initialize wallet data so the UI doesn't refresh with outdated data
            self.balances = []
            self.addresses = []
            self.status = []
            self.blocks = []

            # Clear/reset UI fields immediately rather than waiting for refresh UI task
            self.builder.get_object("AvailableBalanceAmountLabel").set_label("{:,.2f}".format(0))
            self.builder.get_object("LockedBalanceAmountLabel").set_label("{:,.2f}".format(0))
            self.transactions_list_store.clear()
            self.builder.get_object("MainStatusLabel").set_markup("<b>Loading...</b>")

            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, "Wallet Reset")
            dialog.format_secondary_text(global_variables.message_dict["SUCCESS_WALLET_RESET"])
            main_logger.info(global_variables.message_dict["SUCCESS_WALLET_RESET"])
            dialog.run()
            dialog.destroy()

        except ValueError as e:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.CANCEL, "Error resetting")
            dialog.format_secondary_text(global_variables.message_dict["FAILED_WALLET_RESET"])
            main_logger.error(global_variables.message_dict["FAILED_WALLET_RESET"])
            dialog.run()
            dialog.destroy()

    def on_ExportKeysMenuItem_activate(self, object, data=None):
        """
        Export the wallet's secret keys to a dialog with a button
        enabling users to copy the keys to the clipboard.
        :param object:
        :param data:
        :return:
        """
        try:
            # Capture the secret view key
            r = global_variables.wallet_connection.request("getViewKey")
            view_secret_key = r.get('viewSecretKey', 'N/A')

            # Capture the secret spend key for this specific address
            r = global_variables.wallet_connection.request("getSpendKeys", params={'address': self.addresses[0]})
            spend_secret_key = r.get('spendSecretKey', 'N/A')

            # Show a message box containing the secret keys
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO,
                                       Gtk.ButtonsType.OK, "Secret Keys")
            keys_text = "View secret: {}\nSpend secret: {}".format(view_secret_key, spend_secret_key)
            keys_text_markup = "<b>View secret:</b> {}\n\n<b>Spend secret:</b> {}".format(view_secret_key, spend_secret_key)
            dialog.format_secondary_markup(keys_text_markup)
            copy_image = Gtk.Image()
            copy_image.set_from_stock(Gtk.STOCK_COPY, Gtk.IconSize.BUTTON)
            copy_button = Gtk.Button(halign=Gtk.Align.CENTER)
            copy_button.set_image(copy_image)
            copy_button.set_always_show_image(True)
            copy_button.set_tooltip_text("Copy")
            copy_button.connect_object("clicked", copy_text, keys_text)
            dialog.get_message_area().add(copy_button)
            dialog.show_all()
            dialog.run()
            dialog.destroy()

        except ValueError:
            # The request will throw a value error if the RPC server sends us an error response
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.CANCEL, "Error exporting keys")
            dialog.format_secondary_text(
                "Failed to retrieve keys from the wallet!")
            dialog.run()
            dialog.destroy()

    def on_SaveMenuItem_activate(self, object, data=None):
        """
        Attempts to call the save action on the wallet API.
        On success, shows success mesage to user.
        On error, shows error message to user.
        :param object: unused
        :param data: unused
        :return:
        """
        try:
            global_variables.wallet_connection.request("save")
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO,Gtk.ButtonsType.OK, "Wallet Saved")
            dialog.format_secondary_text(global_variables.message_dict["SUCCESS_WALLET_SAVE"])
            main_logger.info(global_variables.message_dict["SUCCESS_WALLET_SAVE"])
            dialog.run()
            dialog.destroy()
        except ValueError as e:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR,Gtk.ButtonsType.CANCEL, "Error saving")
            dialog.format_secondary_text(global_variables.message_dict["FAILED_WALLET_SAVE"])
            main_logger.error(global_variables.message_dict["FAILED_WALLET_SAVE"])
            dialog.run()
            dialog.destroy()


    def on_SendButton_clicked(self, object, data=None):
        """
        Fired when the send button is clicked.
        Attempts to validate inputs and displays label text for erroneous entries.
        On success, populates label with transaction hash.
        :param object:
        :param data:
        :return:
        """
        # Capture target address and validating
        target_address = self.builder.get_object("RecipientAddressEntry").get_text()
        if not target_address.startswith('TRTL') or len(target_address) <= 50:
            self.builder.get_object("TransactionStatusLabel")\
                .set_label("The address doesn't look right, are you sure it's a TRTL address?")
            main_logger.warn("Incorrect TRTL address set on send")
            return
        source_address = self.builder.get_object("AddressTextBox").get_text()

        # More address validating
        if target_address == source_address:
            self.builder.get_object("TransactionStatusLabel") \
                .set_label("Are you trying to send yourself TRTL? Is that even possible?")
            main_logger.warn("Invalid TRTL address set on send")
            return

        # Capturing amount value and validating
        try:
            amount = int(float(self.builder.get_object("AmountEntry").get_text())*100)
            if amount <= 0:
                main_logger.warn(global_variables.message_dict["INVALID_AMOUNT"])
                raise ValueError(global_variables.message_dict["INVALID_AMOUNT"])
        except ValueError as e:
            print(global_variables.message_dict["INVALID_AMOUNT_EXCEPTION"] % e)
            main_logger.warn(global_variables.message_dict["INVALID_AMOUNT_EXCEPTION"] % e)
            self.builder.get_object("TransactionStatusLabel")\
                .set_label("Slow down TRTL bro! The amount needs to be a number greater than 0.")
            return

        #Determine Fee Settings
        #Get feeSuggest Checkbox widget
        feeSuggest = self.builder.get_object("FeeSuggestionCheck")
        #Check if it is not checked, if it is checked we use the static fee
        if not feeSuggest.get_active():
            #Unchecked, which means we parse and use the fee given in textbox
            try:
                fee = int(float(self.builder.get_object("FeeEntry").get_text())*100)
                if amount <= 0:
                    main_logger.warn(global_variables.message_dict["INVALID_FEE"])
                    raise ValueError(global_variables.message_dict["INVALID_FEE"])
            except ValueError as e:
                print(global_variables.message_dict["INVALID_FEE_EXCEPTION"] % e)
                main_logger.warn(global_variables.message_dict["INVALID_FEE_EXCEPTION"] % e)
                self.builder.get_object("TransactionStatusLabel")\
                    .set_label("Custom FEE amount is checked with a invalid FEE amount")
                return
        else:
            fee = global_variables.static_fee

        # Mixin
        mixin = int(self.builder.get_object("MixinSpinButton").get_text())
        body = {
            'anonymity': mixin,
            'fee': fee,
            'transfers': [{'amount': amount, 'address': target_address}],
        }
        payment_id = self.builder.get_object("PaymentIDEntry").get_text()
        if payment_id:
            body['paymentId'] = payment_id
        try:
            resp = global_variables.wallet_connection.request("sendTransaction", params=body)
            txHash = resp['transactionHash']
            self.builder.get_object("TransactionStatusLabel").set_markup("<b>TxID</b>: {}".format(txHash))
            self.clear_send_ui()
            main_logger.info("New Send Transaction - Amount: " + str(amount) + ", Mix: " + str(mixin) + ", To_Address: " + str(target_address))
        except ConnectionError as e:
            print("Failed to connect to daemon: {}".format(e))
            self.builder.get_object("TransactionStatusLabel") \
                .set_label(global_variables.message_dict["FAILED_SEND"])
            main_logger.error(global_variables.message_dict["FAILED_SEND"])
        except ValueError as e:
            print(global_variables.message_dict["FAILED_SEND_EXCEPTION"].format(e))
            self.builder.get_object("TransactionStatusLabel") \
                .set_label("Failed: {}".format(e))
            main_logger.error(global_variables.message_dict["FAILED_SEND_EXCEPTION"].format(e))


    def clear_send_ui(self):
        """
        Clear the inputs within the send transaction frame
        :return:
        """
        self.builder.get_object("RecipientAddressEntry").set_text('')
        self.builder.get_object("MixinSpinButton").set_value(3)
        self.builder.get_object("AmountEntry").set_text('')
        self.builder.get_object("PaymentIDEntry").set_text('')

    def request_wallet_data_loop(self):
        """
        This method loops indefinitely and requests the wallet data every 5 seconds.
        """
        while not self._stop_update_thread.isSet():
            try:
                # Request the balance from the wallet
                self.balances = global_variables.wallet_connection.request("getBalance")

                # Request the addresses from the wallet (looks like you can have multiple?)
                self.addresses = global_variables.wallet_connection.request("getAddresses")['addresses']

                # Request the current status from the wallet
                self.status = global_variables.wallet_connection.request("getStatus")

                # Request all transactions related to our addresses from the wallet
                # This returns a list of blocks with only our transactions populated in them
                self.blocks = global_variables.wallet_connection.request(
                    "getTransactions", params={
                        "blockCount": self.status['blockCount'],
                        "firstBlockIndex": 1,
                        "addresses": self.addresses})['items']

                self.currentTimeout = 0
                self.currentTry = 0

            except ConnectionError as e:
                main_logger.error(str(e))

                # Checks to see if the daemon failed to respond 3 or more times in a row
                if self.currentTimeout >= self.watchdogTimeout:
                    # Checks to see if we have restarted the daemon 3 or more times already
                    if self.currentTry <= self.watchdogMaxTry:
                        # Restart the daemon if conditions are met
                        self.restart_Daemon()
                    else:
                        # Here means the daemon failed 3 times in a row, and we restarted it 3 times with no successful connection. At this point we must give up.
                        dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, "Walletd daemon could not be recovered!")
                        dialog.format_secondary_text("Turtle Wallet has tried numerous times to relaunch the needed daemon and has failed. Please relaunch the wallet!")
                        dialog.run()
                        dialog.destroy()
                        Gtk.main_quit()
                else:
                    self.currentTimeout += 1

                main_logger.error(global_variables.message_dict["FAILED_DAEMON_COMM"])
                self.builder.get_object("MainStatusLabel").set_label(global_variables.message_dict["FAILED_DAEMON_COMM"])

            time.sleep(5) # Wait 5 seconds before doing it again

    def MainWindow_generic_dialog(self, title, message):
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

    def restart_Daemon(self):
        """
        This function gets called when during the wallet data request cycle, the daemon is found to be possibly dead or hanging.
        The function simply calls back to the 'start_wallet_daemon' in ConnectionManager, which will restart our
        daemon for us if needed.
        """
        global_variables.wallet_connection.start_wallet_daemon(global_variables.wallet_connection.wallet_file, global_variables.wallet_connection.password)


    def refresh_ui(self):
        """
        This method refreshes all the values in the UI to represent the current state of the wallet.
        """
        # Update the balance amounts, formatted as comma seperated with 2 decimal points
        if self.balances:
            self.builder.get_object("AvailableBalanceAmountLabel").set_label("{:,.2f}".format(self.balances['availableBalance']/100.))
            self.builder.get_object("LockedBalanceAmountLabel").set_label("{:,.2f}".format(self.balances['lockedAmount']/100.))

        # Load the first address in for now - TODO: Check if multiple addresses need accounting for
        if self.addresses:
            self.builder.get_object("AddressTextBox").set_text(self.addresses[0])

        # Iterate through the blocks and extract the relevant data
        tx_hash_list = [tx[0] for tx in self.transactions_list_store]
        for block in self.blocks:
            if block['transactions']: # Check the block contains any transactions
                for transaction in block['transactions']: # Loop through each transaction in the block
                    # To locate the address, we need to find the relevant transfer within the transaction
                    address = None
                    if transaction['amount'] < 0: # If the transaction was sent from this address
                        # Get the desired transfer amount, accounting for the fee and the transaction being
                        # negative as it was sent, not received
                        desired_transfer_amount = (transaction['amount'] + transaction['fee']) * -1
                    else:
                        desired_transfer_amount = transaction['amount']

                    # Now loop through the transfers and find the address with the correctly transferred amount
                    for transfer in transaction['transfers']:
                        if transfer['amount'] == desired_transfer_amount:
                            address = transfer['address']
                            break

                    # Append new transactions to the treeview's backing list store in the correct format
                    if transaction['transactionHash'] not in tx_hash_list:
                        self.transactions_list_store.prepend([
                            transaction['transactionHash'],
                            # Determine the direction of the transfer (In/Out)
                            "In" if transaction['amount'] > 0 else "Out",
                            # Determine if the transaction is confirmed or not - block rewards take 40 blocks to confirm,
                            # transactions between wallets are marked as confirmed automatically with unlock time 0
                            transaction['unlockTime'] is 0 or transaction['unlockTime'] <= self.status['blockCount'] - 40,
                            # Format the amount as comma seperated with 2 decimal points
                            "{:,.2f}".format(transaction['amount']/100.),
                            # Format the transaction time for the user's local timezone
                            datetime.fromtimestamp(transaction['timestamp'], tzlocal.get_localzone()).strftime("%Y/%m/%d %H:%M:%S%z (%Z)"),
                            # The address as located earlier
                            address
                        ])
                        tx_hash_list.append(transaction['transactionHash'])

        # Remove any transactions that are no longer valid
        # e.g. in case the daemon has accidentally forked and listed some transactions that are invalid
        valid_transactions = []
        for block in self.blocks:
            for transaction in block['transactions']:
                valid_transactions.append(transaction['transactionHash'])
        for transaction in self.transactions_list_store:
            if transaction[0] not in valid_transactions:
                self.transactions_list_store.remove(transaction.iter)

        # Update the status label in the bottom right with block height, peer count, and last refresh time
        if self.status:
            block_count = self.status['blockCount']
            known_block_count = self.status['knownBlockCount']
            peer_count = self.status['peerCount']
            days_behind = ((known_block_count - block_count) * 30) / (60 * 60 * 24)
            percent_synced = int((float(block_count) / float(known_block_count)) * 100)

            block_height_string = "<b>Current block height</b> {}".format(block_count)
            # Buffer the block count by 1 due to latency issues
            # Using a remote daemon for example will almost always be behind one block.
            if block_count+1 < known_block_count:
                block_height_string = "<b>Synchronizing...</b>{}% [{} / {}] ({} days behind)".format(percent_synced, block_count, known_block_count, days_behind)
            status_label = "{0} | <b>Peer count</b> {1} | <b>Last updated</b> {2}".format(block_height_string, peer_count, datetime.now(tzlocal.get_localzone()).strftime("%H:%M:%S"))
            self.builder.get_object("MainStatusLabel").set_markup(status_label)

            # Logging here for debug purposes. Sloppy Joe..
            main_logger.debug("REFRESH STATS:" + "\r\n" +
                              "AvailableBalanceAmountLabel: {:,.2f}".format(self.balances['availableBalance']/100.) + "\r\n" +
                              "LockedBalanceAmountLabel: {:,.2f}".format(self.balances['lockedAmount']/100.) + "\r\n" +
                              "Address: " + str(self.addresses[0]) + "\r\n" +
                              "Status: " + "{0} | Peer count {1} | Last updated {2}".format(block_height_string, peer_count, datetime.now(tzlocal.get_localzone()).strftime("%H:%M:%S")))

        # Return True so GLib continues to call this method
        return True

    def __init__(self):
        # Initialise the GTK builder and load the glade layout from the file
        self.builder = Gtk.Builder()
        self.builder.add_from_file("MainWindow.glade")

        # Init. counters needed for watchdog function
        self.watchdogTimeout = 3
        self.watchdogMaxTry = 3
        self.currentTimeout = 0
        self.currentTry = 0

        # Initialize wallet data
        self.balances = []
        self.addresses = []
        self.status = []
        self.blocks = []

        # Get the transaction treeview's backing list store
        self.transactions_list_store = self.builder.get_object("HomeTransactionsListStore")

        # Use the methods defined in this class as signal handlers
        self.builder.connect_signals(self)

        # Get the window from the builder
        self.window = self.builder.get_object("MainWindow")

        # Set the window title to reflect the current version
        self.window.set_title("TurtleWallet v{0}".format(__version__))

        # Setup the transaction spin button
        self.setup_spin_button()

        # Setup UILogHandler so the Log Textview gets the same
        # information as the log file, with less verbose (INFO).
        uiHandler = UILogHandler(self.builder.get_object("LogBuffer"))
        uiHandler.setLevel(logging.INFO)
        main_logger.addHandler(uiHandler)
        self.LogScroller = self.builder.get_object("LogScrolledWindow")

        #Setup UI RPC variables
        self.RPCCommands = {
            'reset': {
                'Description': "Resets and re-synchronizes your wallet.",
                'Arguments': Template("")},
            'save': {
                'Description': "Saves your wallet to file.",
                'Arguments': Template("")},
            'getViewKey': {
                'Description': "Returns your private view key.",
                'Arguments': Template("")},
            'getSpendKeys': {
                'Description': "Returns your private and public spend keys for a given address.",
                'Arguments': Template('{"address":"$address"}')},
            'getStatus': {
                'Description': "Returns information about the current wallet state.",
                'Arguments': Template("")},
            'getAddresses': {
                'Description': "Returns all of your wallet's addresses.",
                'Arguments': Template("")},
            'createAddress': {
                'Description': "Creates an address and adds it to your wallet.",
                'Arguments': Template("")},
            'deleteAddress': {
                'Description': "Deletes a specified address from your wallet.",
                'Arguments': Template('{"address":""}')},
            'getBalance': {
                'Description': "Returns the balance of a specified address. If address is not specified, returns a cumulative balance of all wallet's addresses.",
                'Arguments': Template('{"address":""}')},
            'getBlockHashes': {
                'Description': "Returns the hashes of all blocks within a specified range.",
                'Arguments': Template('{\n"firstBlockIndex":1,\n"blockCount":10\n}')},
            'getTransactionHashes': {
                'Description': "Returns the hashes of all blocks and transactions in those blocks within a specified range and optionally only for specified addresses and paymentId.",
                'Arguments': Template(
                    '{\n'
                    '"firstBlockIndex":1,\n'
                    '"blockCount":10,\n'
                    '"addresses":[\n'
                    '    "$address"\n'
                    '],\n'
                    '"paymentID":""\n'
                    '}'
                )},
            'getTransactions': {
                'Description': "Returns information about the transactions within a specified range and optionally only for specified addresses and paymentId.",
                'Arguments': Template(
                    '{\n'
                    '"firstBlockIndex":1,\n'
                    '"blockCount":10,\n'
                    '"addresses":[\n'
                    '    "$address"\n'
                    '],\n'
                    '"paymentID":""\n'
                    '}'
                )},
            'getUnconfirmedTransactionHashes': {
                'Description': "Returns information about the current unconfirmed transaction pool and optionally only for specified addresses.",
                'Arguments': Template(
                    '{\n'
                    '"addresses":[\n'
                    '    "$address"\n'
                    ']\n'
                    '}'
                )},
            'getTransaction': {
                'Description': "Returns information about the specified transaction.",
                'Arguments': Template('{"transactionHash":"$transactionHash"}')},
            'sendTransaction': {
                'Description': "Creates and sends a transaction to one or several addresses.",
                'Arguments': Template(
                    '{\n'
                    '"anonymity":3,\n'
                    '"fee":10,\n'
                    '"unlockTime":0,\n'
                    '"paymentID":"",\n'
                    '"addresses":[\n'
                    '   "$address"\n'
                    '],\n'
                    '"transfers":[\n'
                    '   {\n'
                    '     "amount":1000,\n'
                    '     "address":"$address"\n'
                    '   },\n'
                    '   {\n'
                    '     "amount":2000,\n'
                    '     "address":"$address"\n'
                    '   },\n'
                    '   {\n'
                    '     "amount":3000,\n'
                    '     "address":"$address"\n'
                    '   }\n'
                    '],\n'
                    '"changeAddress":"$address",\n'
                    '"extra":""\n'
                    '}'
                )
            },
            'createDelayedTransaction': {
                'Description': "Creates but does not send a transaction. The transaction is not sent to the network automatically and must be sent using the sendDelayedTransaction method.",
                'Arguments': Template(
                    '{\n'
                    '"anonymity":3,\n'
                    '"fee":10,\n'
                    '"unlockTime":0,\n'
                    '"paymentID":"",\n'
                    '"addresses":[\n'
                    '   "$address"\n'
                    '],\n'
                    '"transfers":[\n'
                    '   {\n'
                    '     "amount":1000,\n'
                    '     "address":"$address"\n'
                    '   },\n'
                    '   {\n'
                    '     "amount":2000,\n'
                    '     "address":"$address"\n'
                    '   },\n'
                    '   {\n'
                    '     "amount":3000,\n'
                    '     "address":"$address"\n'
                    '   }\n'
                    '],\n'
                    '"changeAddress":"$address",\n'
                    '"extra":""\n'
                    '}'
                )
            },
            'getDelayedTransactionHashes': {
                'Description': "Returns hashes of delayed transactions.",
                'Arguments': Template("")},
            'deleteDelayedTransaction': {
                'Description': "Deletes a specified delayed transaction.",
                'Arguments': Template('{"transactionHash":""}')},
            'sendDelayedTransaction': {
                'Description': "Sends a specified delayed transaction.",
                'Arguments': Template('{"transactionHash":""}')},
            'sendFusionTransaction': {
                'Description': "Creates and sends a fusion transaction, by taking funds from selected addresses and transferring them to the destination address.",
                'Arguments': Template(
                    '{\n'
                    '"anonymity": 3,\n'
                    '"threshold": 1000,\n'
                    '"addresses": [\n'
                    '    "$address"\n'
                    '],\n'
                    '"destinationAddress": "$address"\n'
                    '}'
                )
            },
            'estimateFusion': {
                'Description': "Allows to estimate a number of outputs that can be optimized with fusion transactions.",
                'Arguments': Template(
                    '{\n'
                    '"threshold": 1000,\n'
                    '"addresses": [\n'
                    '    "$address"\n'
                    ']\n'
                    '}'
                )
            }
        }
        self.RPCbuffer = self.builder.get_object("RPCTextView").get_buffer()
        self.RPCScroller = self.builder.get_object("RPCScrolledWindow")
        self.rpc_method_list_store = self.builder.get_object("RPCMethodListStore")
        for method in sorted(self.RPCCommands.keys()):
            self.rpc_method_list_store.append([method])
        self.builder.get_object("RPCMethodComboBox").set_active(0)

        #Set the default fee amount in the FeeEntry widget
        self.builder.get_object("FeeEntry").set_text(str(float(global_variables.static_fee) / float(100)))

        # Initialize the inputs within the send transaction frame
        self.clear_send_ui()

        # Show an initial status message
        self.builder.get_object("MainStatusLabel").set_markup("<b>Loading...</b>")

        #If wallet is different than cached config wallet, Prompt if user would like to set default wallet
        with open(global_variables.wallet_config_file,) as configFile:
            tmpconfig = json.loads(configFile.read())
        if global_variables.wallet_connection.wallet_file != tmpconfig['walletPath']:
            if self.MainWindow_generic_dialog("Would you like to default to this wallet on start of Turtle Wallet?", "Default Wallet"):
                global_variables.wallet_config["walletPath"] = global_variables.wallet_connection.wallet_file
        #cache that user has indeed been inside a wallet before
        global_variables.wallet_config["hasWallet"]  = True
        #save config file
        try:
            with open(global_variables.wallet_config_file,'w') as cFile:
                cFile.write(json.dumps(global_variables.wallet_config))
        except Exception as e:
            splash_logger.warn("Could not save config file: {}".format(e))

        # Start the wallet data request loop in a new thread
        self._stop_update_thread = threading.Event()
        self.update_thread = threading.Thread(target=self.request_wallet_data_loop)
        self.update_thread.daemon = True
        self.update_thread.start()

        # Register a function via Glib that gets called every 5 seconds to refresh the UI
        GLib.timeout_add_seconds(5, self.refresh_ui)

        #These tabs should not be shown, even on show all
        noteBook = self.builder.get_object("MainNotebook")
        #Remove Log tab
        noteBook.remove_page(2)
        #Remove RPC tab
        noteBook.remove_page(2)

        # Finally, show the window
        self.window.show_all()



    def setup_spin_button(self):
        """
        Setup spin button:
        initial value => 0,
        base value => 0,
        max value => 30,
        increment => 1,
        page_incr and  page_size set to 1, not sure how these properties are used though
        """
        adjustment = Gtk.Adjustment(0, 0, 31, 1, 1, 1)
        spin_button = self.builder.get_object("MixinSpinButton")
        spin_button.configure(adjustment, 1, 0)
