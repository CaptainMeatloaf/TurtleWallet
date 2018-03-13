# -*- coding: utf-8 -*-
""" global_variables.py

This file stores the global variables for the wallet.
"""

# The main wallet connection object that handles communicating
# to the wallet daemon process and talking to the RPC server.
wallet_connection = None
wallet_config_file = 'trtlconfig.json'
wallet_config = {}
static_fee = 10 #ATOMIC UNITS
message_dict = {
                    "NO_RPC": "No RPC connection has been established!",
                    "NO_DAEMON_FILE" : "Cannot find wallet daemon at location: {}",
                    "NO_DAEMON_PROC": "Walletd process not found",
                    "EXISTING_DAEMON" : "Daemon is already running: pid {}",
                    "INVALID_DAEMON" : "Invalid Daemon running, terminating",
                    "INACCESS_DAEMON" : "Unable to open wallet daemon.",
                    "FAILED_DAEMON_COMM" : "Cannot communicate to wallet daemon! Is it running?",
                    "EXITED_DAEMON" : "Wallet daemon exited.",
                    "CONNECTING_DAEMON" : "Connecting to walletd",
                    "CONNECTION_ERROR_DAEMON" : "ConnectionError while waiting for daemon to start: {}",
                    "NO_COMM_DAEMON" : "Can't communicate to daemon",
                    "FAILED_CONNECT_DAEMON" : "Failed to connect to walletd: {}",
                    "NO_WALLET_FILE" : "Cannot find wallet at location: {}",
                    "NO_SERVER_COMM" : "Failed to talk to server: %s",
                    "SUCCESS_WALLET_RESET" : "Wallet has been reset successfully",
                    "FAILED_WALLET_RESET" : "The wallet failed to reset!",
                    "SUCCESS_WALLET_SAVE" : "Wallet has been saved successfully",
                    "FAILED_WALLET_SAVE" : "The wallet failed to save!",
                    "INVALID_AMOUNT" : "Amount is an invalid number",
                    "INVALID_AMOUNT_EXCEPTION" : "Invalid amount: %s",
                    "INVALID_FEE" : "Fee amount is an invalid number",
                    "INVALID_FEE_EXCEPTION" : "Invalid fee amount: %s",
                    "FAILED_SEND": "Failed to send: cannot connect to server.",
                    "FAILED_SEND_EXCEPTION": "Server request error: {}",
                    "NO_INFO" : "No wallet found, given, or created"
                }