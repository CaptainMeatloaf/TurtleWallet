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


class MainWindow(object):
    """
    This class is used to interact with the MainWindow glade file
    """
    def on_MainWindow_destroy(self, object, data=None):
        """Called by GTK when the main window is destroyed"""
        Gtk.main_quit() # Quit the GTK main loop

    def on_CopyButton_clicked(self, object, data=None):
        """Called by GTK when the copy button is clicked"""
        self.builder.get_object("AddressTextBox")
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self.builder.get_object("AddressTextBox").get_text(), -1)

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
        r = global_variables.wallet_connection.request("reset")
        if not r:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO,
                                       Gtk.ButtonsType.OK, "Wallet Reset")
            dialog.format_secondary_text(
                "Wallet has been reset successfully.")
            dialog.run()
            dialog.destroy()
        else:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.CANCEL, "Error resetting")
            dialog.format_secondary_text(
                "The wallet failed to reset!")
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
        r = global_variables.wallet_connection.request("save")
        if not r:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO,
                                       Gtk.ButtonsType.OK, "Wallet Saved")
            dialog.format_secondary_text(
                "Wallet has been saved successfully.")
            dialog.run()
            dialog.destroy()
        else:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.CANCEL, "Error saving")
            dialog.format_secondary_text(
                "The wallet failed to save!")
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
            return
        source_address = self.builder.get_object("AddressTextBox").get_text()

        # More address validating
        if target_address == source_address:
            self.builder.get_object("TransactionStatusLabel") \
                .set_label("Are you trying to send yourself TRTL? Is that even possible?")
            return

        # Capturing amount value and validating
        try:
            amount = int(float(self.builder.get_object("AmountEntry").get_text())*100)
            if amount <= 0:
                raise ValueError("Amount is an invalid number")
        except ValueError as e:
            print("Invalid amount: %s" % e)
            self.builder.get_object("TransactionStatusLabel")\
                .set_label("Slow down TRTL bro! The amount needs to be a number greater than 0.")
            return
        # Mixin
        mixin = int(self.builder.get_object("MixinSpinButton").get_text())
        body = {
            'anonymity': mixin,
            'fee': 10, # 0.1
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
        except ConnectionError as e:
            print("Failed to connect to daemon: {}".format(e))
            self.builder.get_object("TransactionStatusLabel") \
                .set_label("Failed to send: cannot connect to server.")
        except ValueError as e:
            print("Server request error: {}".format(e))
            self.builder.get_object("TransactionStatusLabel") \
                .set_label("Failed: {}".format(e))


    def clear_send_ui(self):
        """
        Clear the inputs within the send transaction frame
        :return:
        """
        self.builder.get_object("RecipientAddressEntry").set_text('')
        self.builder.get_object("MixinSpinButton").set_value(0)
        self.builder.get_object("AmountEntry").set_text('')

    def update_loop(self):
        """
        This method loops infinitely and refreshes the UI every 5 seconds.

        Note:
            More optimal differential method of reloading transactions
            is required, as currently you can't really scroll through them
            without it jumping back to the top when it clears the list.
            Likely solution would be a hidden (or not) column with the
            transaction hash."""
        while True:
            GLib.idle_add(self.refresh_values) # Refresh the values, calling the method via GLib
            time.sleep(5) # Wait 5 seconds before doing it again

    def set_error_status(self):
        self.builder.get_object("MainStatusLabel").set_label("Cannot communicate to wallet daemon! Is it running?")

    def refresh_values(self):
        """
        This method refreshes all the values in the UI to represent the current
        state of the wallet.
        """
        try:
            # Request the balance from the wallet
            balances = global_variables.wallet_connection.request("getBalance")
            # Update the balance amounts, formatted as comma seperated with 2 decimal points
            self.builder.get_object("AvailableBalanceAmountLabel").set_label("{:,.2f}".format(balances['availableBalance']/100.))
            self.builder.get_object("LockedBalanceAmountLabel").set_label("{:,.2f}".format(balances['lockedAmount']/100.))

            # Request the addresses from the wallet (looks like you can have multiple?)
            addresses = global_variables.wallet_connection.request("getAddresses")['addresses']
            # Load the first address in for now - TODO: Check if multiple addresses need accounting for
            self.builder.get_object("AddressTextBox").set_text(addresses[0])

            # Request the current status from the wallet
            status = global_variables.wallet_connection.request("getStatus")

            # Request all transactions related to our addresses from the wallet
            # This returns a list of blocks with only our transactions populated in them
            blocks = global_variables.wallet_connection.request("getTransactions", params={"blockCount" : status['blockCount'], "firstBlockIndex" : 1, "addresses": addresses})['items']
        except ConnectionError as e:
            self.set_error_status()
            return

        # Clear the transaction list store ready to (re)populate
        self.transactions_list_store.clear()

        # Iterate through the blocks and extract the relevant data
        # This is reversed to show most recent transactions first
        for block in reversed(blocks):
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

                    # Append the transaction to the treeview's backing list store in the correct format
                    self.transactions_list_store.append([
                        # Determine the direction of the transfer (In/Out)
                        "In" if transaction['amount'] > 0 else "Out",
                        # Determine if the transaction is confirmed or not - block rewards take 40 blocks to confirm,
                        # transactions between wallets are marked as confirmed automatically with unlock time 0
                        transaction['unlockTime'] is 0 or transaction['unlockTime'] <= status['blockCount'] - 40,
                        # Format the amount as comma seperated with 2 decimal points
                        "{:,.2f}".format(transaction['amount']/100.),
                        # Format the transaction time for the user's local timezone
                        datetime.fromtimestamp(transaction['timestamp'], tzlocal.get_localzone()).strftime("%Y/%m/%d %H:%M:%S%z (%Z)"),
                        # The address as located earlier
                        address
                    ])

        # Update the status label in the bottom right with block height, peer count, and last refresh time
        block_height_string = "<b>Current block height</b> {}".format(status['blockCount'])
        if status['blockCount'] < status['knownBlockCount']:
            block_height_string = "<b>Synchronizing with network...</b> [{} / {}]".format(status['blockCount'], status['knownBlockCount'])
        status_label = "{0} | <b>Peer count</b> {1} | <b>Last Updated</b> {2}".format(block_height_string, status['peerCount'], datetime.now(tzlocal.get_localzone()).strftime("%H:%M:%S"))
        self.builder.get_object("MainStatusLabel").set_markup(status_label)

    def __init__(self):
        # Initialise the GTK builder and load the glade layout from the file
        self.builder = Gtk.Builder()
        self.builder.add_from_file("MainWindow.glade")

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

        # Start the UI update loop in a new thread
        self.update_thread = threading.Thread(target=self.update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()

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

