# -*- coding: utf-8 -*-
""" ConnectionManager.py

This file represents the logic required for the RPC
connections, currently just to Walletd.
"""

import json
import psutil
import requests
from HelperFunctions import get_wallet_daemon_path, get_rpc_password
import time
import os
import os.path
from subprocess import Popen
import global_variables
import logging
import hashlib

# Get Logger made in start.py
WC_logger = logging.getLogger('trtl_log.walletConnection')

class WalletConnection(object):
    """
    This class represents an RPC connection to Walletd
    """
    def request(self, method, params={}):
        """Makes an RPC request to Walletd"""
        if self.rpc_connection is not None: # Check to make sure that an RPC connection has been established
            response = self.rpc_connection.request(method, params) # Make the request
            WC_logger.debug("Request Response: \r\n" + str(response['result']) )
            return response['result'] # Return the response from the request
        else:
            WC_logger.error(global_variables.message_dict["NO_RPC"])
            raise Exception(global_variables.message_dict["NO_RPC"])
            
    def check_daemon_running(self):
        """
        checks if daemon is running by looping through every process and comparing
        their names to 'walletd' or 'walletd.exe'. If found, it returns the process object.
        :return: None or Process Object
        """
        for proc in psutil.process_iter():  # Search the running process list for walletd
            if proc.name() == "walletd" or proc.name() == "walletd.exe":
                try:
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        return None
                    else:
                        return proc
                except psutil.NoSuchProcess as e:
                    WC_logger.info(global_variables.message_dict["NO_DAEMON_PROC"])
                    return None
        return None
        
    def check_existing_daemon(self, existing_daemon, goodDaemonPath):
        """
        checks a existing daemon process, finds its path, and compares it against
        our known good daemon executable. This prevents us from connecting to
        other wallets daemons, and also protects our users information
        :return: True or False depending on if the daemon is ours
        """
        #gets the existing daemon executble path
        existing_daemon_path = existing_daemon.exe()
        #gets md5 of existing daemon executabe
        existing_daemon_hash =hashlib.md5(open(existing_daemon_path, 'rb').read()).hexdigest()
        #gets md5 of known good daemon executabe
        good_daemon_hash = hashlib.md5(open(goodDaemonPath, 'rb').read()).hexdigest()
        #compares hashes, if they do not match, this is not our daemon, and we return False
        if existing_daemon_hash != good_daemon_hash:
            return False
        else:
            return True
        

    def start_wallet_daemon(self, wallet_file, password, rpc_password):
        """
        Fires off the wallet daemon and releases control once the daemon
        has successfully been spun up.

        :param wallet_file: path to the wallet file
        :param password: password for the wallet
        :return: popen instance of the wallet daemon process
        """
        #gets process object to a existing daemon, if one exists
        existing_daemon = self.check_daemon_running()
        #gets known good daemon path
        good_daemon = get_wallet_daemon_path()
        # Determine walletd args
        walletd_args = [get_wallet_daemon_path(), '-w', wallet_file, '-p', password, '--rpc-password', rpc_password]
        remote_daemon_address = global_variables.wallet_config.get('remoteDaemonAddress', None)
        # Evaluate if a remote daemon is to be used, else we use the local argument
        if remote_daemon_address:
            walletd_args.extend(["--daemon-address", remote_daemon_address])
            remote_daemon_port = global_variables.wallet_config.get('remoteDaemonPort', None)
            if remote_daemon_port:
                walletd_args.extend(["--daemon-port", remote_daemon_port])
        else:
            walletd_args.append("--local")
        #checks if existing daemon has been found
        if existing_daemon:
            print(global_variables.message_dict["EXISTING_DAEMON"].format(existing_daemon.pid))
            WC_logger.info(global_variables.message_dict["EXISTING_DAEMON"].format(existing_daemon.pid))
            #checks if existing daemon is valid (Our daemon and not a different or modified one)
            if self.check_existing_daemon(existing_daemon,good_daemon) == False:
                print(global_variables.message_dict["INVALID_DAEMON"])
                WC_logger.info(global_variables.message_dict["INVALID_DAEMON"])
                #if a invlaid daemon is found, we terminate it and start a new one
                existing_daemon.terminate()
                existing_daemon.wait()
                walletd = Popen(walletd_args)
            else:
                #existing daemon found to be valid, simply return the existing process object
                return existing_daemon
        else:
            #No existing daemon found, start new instance
            walletd = Popen(walletd_args)

        # Poll the daemon, if poll returns None the daemon is active.
        while walletd.poll():
            time.sleep(1)
        # So now that the daemon is active, the password maybe invalid or
        # the user is still running Turtled and the daemon might die.
        # This is an attempt to wait for that to process.
        # When the main window appears the request status will naturally fail if the daemon is not running.
        if not walletd.poll():
            return walletd
        else:
            WC_logger.error(global_variables.message_dict["INACCESS_DAEMON"])
            raise ValueError(global_variables.message_dict["INACCESS_DAEMON"])

    def stop_wallet_daemon(self):
        """
        Attempts to terminate (SIGTERM) the wallet daemon.
        Using Popen.wait() this will hold until the daemon is successfully terminated.
        :return:
        """
        if self.walletd and self.check_daemon_running():
            r = self.request("save")
            self.walletd.terminate()
            self.walletd.wait()

    def __init__(self, wallet_file, password):
        self.wallet_file = wallet_file
        self.password = password
        if not os.path.isfile(wallet_file):
            WC_logger.error(global_variables.message_dict["NO_WALLET_FILE"].format(wallet_file))
            raise ValueError(global_variables.message_dict["NO_WALLET_FILE"].format(wallet_file))
        self.rpc_password = get_rpc_password()
        self.walletd = self.start_wallet_daemon(wallet_file, password, self.rpc_password)
        # If a user is running their own daemon, they can configure the host/port
        host = os.getenv('DAEMON_HOST', "http://127.0.0.1")
        port = os.getenv('DAEMON_PORT', 8070)
        self.rpc_connection = RPCConnection("{}:{}/json_rpc".format(host, port), self.rpc_password)


class RPCConnection(object):
    """
    This class makes requests to a JSON RPC 2.0 endpoint
    """
    def __init__(self, url, rpc_password):
        self.url = url # Just take the URL at face value, assume user has validated
        self.rpc_password = rpc_password
        self.headers = {'content-type':'application/json'} # Set the headers
        self.id = 0 # Set the ID, which will increase with each call

    def request(self, method, params={}):
        """Makes an RPC request to the endpoint the class was initialised with"""

        # Initialise the payload that is to be sent to the remote endpoint
        payload = {
            "jsonrpc" : "2.0", # Using JSON RPC 2.0
            "method" : method, # The user specified method
            "params" : params, # The user specified, or default params
            "password": self.rpc_password,
            "id" : self.id # The next ID in sequence
        }

        self.id += 1 # Increment the ID by one ready for the next call

        # Make the request to the endpoint with specified data
        response = requests.post(self.url, data=json.dumps(payload), headers=self.headers).json()

        # Check if the response returned an error, and extract and wrap it in an exception if it has
        if 'error' in response:
            WC_logger.error(global_variables.message_dict["NO_SERVER_COMM"] % (response,))
            print(global_variables.message_dict["NO_SERVER_COMM"] % (response,))
            raise ValueError("Walletd RPC failed with error: {0} {1}".format(response['error']['code'], response['error']['message']))
        return response
