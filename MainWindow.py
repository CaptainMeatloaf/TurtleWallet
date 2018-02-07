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

    def on_CopyButton_clicked(self, object, data=None):
        """Called by GTK when the copy button is clicked"""
        self.builder.get_object("AddressTextBox")
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self.builder.get_object("AddressTextBox").get_text(), -1)
        
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
            
    def on_rpcSendButton_clicked(self, object, data=None):
        """ Called by GTK when the RPCSend button has been clicked """
        method = self.builder.get_object("RPCMethodEntry").get_text()
        args = self.builder.get_object("RPCArgumentsEntry").get_text()
        
        #Check the method and arg are somewhat valid
        if method == "":
            end_iter = self.RPCbuffer.get_end_iter()
            self.RPCbuffer.insert(end_iter, "\n\n" + "ERROR: Invalid Method given.")
            return
        try:
            args_dict = json.loads(args)
        except:
            end_iter = self.RPCbuffer.get_end_iter()
            self.RPCbuffer.insert(end_iter, "\n\n" + 'ERROR: Invalid JSON in arguments given. Ex. \n {"blockCount":1000, "firstBlockIndex":1,"addresses":[ "22p4wUHAMndSscvtYErtqUaYrcUTvrZ9zhWwxc3JtkBHAnw4FJqenZyaePSApKWwJ5BjCJz1fKJoA6QHn5j6bVHg8A8dyhp"]}')
            return
        
        #Send the request to RPC server and print results on textview
        try:
            r = global_variables.wallet_connection.request(method,args_dict)
            end_iter = self.RPCbuffer.get_end_iter()
            self.RPCbuffer.insert(end_iter, "\n\n" + "SUCCESS:\n" + json.dumps(r))
        except Exception as e:
            end_iter = self.RPCbuffer.get_end_iter()
            self.RPCbuffer.insert(end_iter, "\n\n" + "ERROR:\n" + str(e))
            
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
        r = global_variables.wallet_connection.request("reset")
        if not r:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, "Wallet Reset")
            dialog.format_secondary_text(global_variables.message_dict["WALLET_RESET"])
            main_logger.info(global_variables.message_dict["WALLET_RESET"])
            dialog.run()
            dialog.destroy()
        else:
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.CANCEL, "Error resetting")
            dialog.format_secondary_text(global_variables.message_dict["FAILED_WALLET_RESET"])
            main_logger.error(global_variables.message_dict["FAILED_WALLET_RESET"])
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
            dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.INFO,Gtk.ButtonsType.OK, "Wallet Saved")
            dialog.format_secondary_text(global_variables.message_dict["SUCCESS_WALLET_SAVE"])
            main_logger.info(global_variables.message_dict["SUCCESS_WALLET_SAVE"])
            dialog.run()
            dialog.destroy()
        else:
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
        main_logger.error(global_variables.message_dict["FAILED_DAEMON_COMM"])
        self.builder.get_object("MainStatusLabel").set_label(global_variables.message_dict["FAILED_DAEMON_COMM"])
        
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
        This function gets called when during the refresh cycle, the daemon is found to be possibly dead or hanging.
        The function simply calls back to the 'start_wallet_daemon' in ConnectionManager, which will restart our
        daemon for us if needed.
        """
        global_variables.wallet_connection.start_wallet_daemon(global_variables.wallet_connection.wallet_file,global_variables.wallet_connection.password)
            

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
            self.currentTimeout = 0
            self.currentTry = 0
            
        except ConnectionError as e:
            main_logger.error(str(e))
            
            #Checks to see if the daemon failed to respond 3 or more times in a row
            if self.currentTimeout >= self.watchdogTimeout:
                #Checks to see if we have restarted the daemon 3 or more times already
                if self.currentTry <= self.watchdogMaxTry:
                    #restart the daemon if conditions are meant
                    self.restart_Daemon()
                else:
                    #Here means the daemon failed 3 times in a row, and we restarted it 3 times with no successful connection. At this point we must give up.
                    dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, "Walletd daemon could not be recovered!")
                    dialog.format_secondary_text("Turtle Wallet has tried numerous times to relaunch the needed daemon and has failed. Please relaunch the wallet!")
                    dialog.run()
                    dialog.destroy()
                    Gtk.main_quit()
            else:
                self.currentTimeout += 1
                
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
        # Buffer the block count by 1 due to latency issues
        # Using a remote daemon for example will almost always be behind one block.
        if status['blockCount']+1 < status['knownBlockCount']:
            block_height_string = "<b>Synchronizing with network...</b> [{} / {}]".format(status['blockCount'], status['knownBlockCount'])
        status_label = "{0} | <b>Peer count</b> {1} | <b>Last Updated</b> {2}".format(block_height_string, status['peerCount'], datetime.now(tzlocal.get_localzone()).strftime("%H:%M:%S"))
        self.builder.get_object("MainStatusLabel").set_markup(status_label)
        
        #Logging here for debug purposes. Sloppy Joe..
        main_logger.debug("REFRESH STATS:" + "\r\n" + "AvailableBalanceAmountLabel: {:,.2f}".format(balances['availableBalance']/100.) + "\r\n" + "LockedBalanceAmountLabel: {:,.2f}".format(balances['lockedAmount']/100.) + "\r\n" + "Address: " + str(addresses[0])  + "\r\n" +  "Status: " + "{0} | Peer count {1} | Last Updated {2}".format(block_height_string, status['peerCount'], datetime.now(tzlocal.get_localzone()).strftime("%H:%M:%S")))

    def __init__(self):
        # Initialise the GTK builder and load the glade layout from the file
        self.builder = Gtk.Builder()
        self.builder.add_from_file("MainWindow.glade")
        
        # Init. counters needed for watchdog function
        self.watchdogTimeout = 3
        self.watchdogMaxTry = 3
        self.currentTimeout = 0
        self.currentTry = 0

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
        self.RPCbuffer = self.builder.get_object("RPCTextView").get_buffer()
        self.RPCScroller = self.builder.get_object("RPCScrolledWindow")
        
        #Set the default fee amount in the FeeEntry widget
        self.builder.get_object("FeeEntry").set_text(str(float(global_variables.static_fee) / float(100)))
        
        
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

        # Start the UI update loop in a new thread
        self.update_thread = threading.Thread(target=self.update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
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

