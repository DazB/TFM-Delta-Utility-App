"""
7th Sense Delta Media Server Command Utility App

This application translates the incoming RSS commands (for the old Mediasonic Servers)
into commands compatible with the 7th Sense Server.

How it works:
We have a server that accepts connections from the Medialon. We use selectors and wait for a
read event, indicating a connection and message.

We simultaneously have a client thread that attempts to make a connection to the Delta Server
App.

When the server sends the specific play command, we set a global flag. The client thread polls 
this flag, and if true, will send the Delta Play command. 

It does this forever and then we die.

Using Gooey to provide a basic interface

Company: Absolute FX Pte Ltd
Author: Dariush Bahri
Application Version: 1
Python Version: 3.11.4 64-bit
"""

import socket
import selectors
import types
import threading
import time
from datetime import datetime
from gooey import Gooey, local_resource_path
from gooey import GooeyParser
import configparser
import os
import psutil
import signal

PROGRAM_NAME = 'Delta Command Utility App v1'

# Network details
MEDIASONIC_PORT = 4000
DELTA_PORT = 23

# Ini config
INI_CONFIG_PATH = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop') + '\DeltaCommandApp.ini'
INI_SECTION_NETWORK = 'Network'
INI_CONTROL_INTERFACE = 'control_network_interface'

# Send play flag. If true, will send command to play Delta
send_play = False
# Send stop flag. If true, will send command to stop Delta
send_stop = False
# Display grid flag. If true, will send command to display grid
display_grid = False
# Cue show flag. If true, will send command to cue show
cue_show = False

# IP address of Delta Server
delta_ip = ''


# Main program
@Gooey(program_name=PROGRAM_NAME, 
       auto_start=True,
       shutdown_signal=signal.SIGTERM,
       disable_stop_button=True, 
       show_failure_modal=False,
       show_stop_warning=False,
       language='delta',
       language_dir=local_resource_path('languages/')
       )
def main():
    desc = ("This app translates the incoming RSS commands \n" +
        "into commands compatible with the 7th Sense Server.")
    parser = GooeyParser(description=desc)

    # Check if have config file and saved interface
    config = configparser.ConfigParser()
    config.sections()

    global delta_ip

    # If the INI config file exists, then use that interface
    if os.path.exists(INI_CONFIG_PATH):
        try:
            # All network interfaces
            dict_interfaces = psutil.net_if_addrs()
            config.read(INI_CONFIG_PATH)
            saved_interface = config[INI_SECTION_NETWORK][INI_CONTROL_INTERFACE]
            delta_ip = dict_interfaces[saved_interface][1].address
        except:
            pass
    
    # If we don't have a selected interface, then run config GUI
    if delta_ip == '':
        # Check if have config file and saved interface
        config = configparser.ConfigParser()
        config.sections()
        # All network interfaces
        dict_interfaces = psutil.net_if_addrs()

        # Adds network interfaces and IP's to a list
        network_choices = []
        for interface in dict_interfaces:
            network_choices.append(interface + " - IP Address: " + dict_interfaces[interface][1].address)
        # Add dropdown listbox argument
        parser.add_argument(
            'interface',
            metavar='Control Network Interface',
            help='Choose the network interface on this machine that connects to the Control Network',
            type=str,
            choices=network_choices,
            gooey_options={'full_width': True})
        # This will run the GUI. Once arguments selected, will continue
        args = parser.parse_args()
        # Write Interface choice to INI file
        interface_index = args.interface.find('-')
        interface_name = args.interface[:interface_index - 1]
        config[INI_SECTION_NETWORK] = {}
        config[INI_SECTION_NETWORK][INI_CONTROL_INTERFACE] = interface_name
        with open(INI_CONFIG_PATH, 'w') as configfile:
            config.write(configfile)

        # Get IP address 
        ip_index = args.interface.find(':')  # Find the index of the character
        delta_ip = args.interface[ip_index + 2:] # Get the IP after the character
    
    # Else we already have an IP address. Autostart
    else:
        parser.parse_args()

    log("App started. This app translates the incoming RSS play command (previously for Mediasonic Players) " +
        "into 7th Sense commands")

    # Main logic for handling the connections and data
    # Handles server multiplexing
    sel = selectors.DefaultSelector()

    # Setup server socket to Medialon can connect
    # Create an INET, STREAMing socket
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind the server socket to Delta IP, and the Mediasonic port
    serversocket.bind((delta_ip, MEDIASONIC_PORT))
    # Open server socket. Listen up to a max of 2 connections (one for RSS, one for debugging)
    serversocket.listen(2)
    serversocket.setblocking(False)
    log(f"Listening on {(delta_ip, MEDIASONIC_PORT)}")
    # Register the server to be monitored for read events
    sel.register(serversocket, selectors.EVENT_READ, data=None)

    # Start client thread so can send data to Delta Server
    log("Starting client thread. Attempting connection to Delta Server App")
    client_thread = threading.Thread(target=client_thread_function, daemon=True)
    client_thread.start()

    while True:
        # Returns list if server socket is ready for I/O
        events = sel.select(timeout=None)
        # Server ready for I/O. Service that boi
        for key, mask in events:
            service_connection(key, mask, sel)
        
# Handles incoming server messages
def service_connection(key, mask, sel: selectors.DefaultSelector):
    global send_play
    global send_stop
    global display_grid
    global cue_show

    sock: socket.socket = key.fileobj
    data = key.data
    # If socket can read 
    if mask & selectors.EVENT_READ:
        try:
            if data == None:
                # When a new client has connected
                conn, addr = sock.accept()  # Should be ready to read
                log(f"Accepted connection from {addr}")
                conn.setblocking(False)
                serverdata = types.SimpleNamespace(addr=addr)
                # Register for only read because just reading from Medialon
                events = selectors.EVENT_READ
                sel.register(conn, events, data=serverdata)
            else:
                # We've received data
                recv_data = sock.recv(1024).decode().lower()  # Should be ready to read
                # log(f'data: {recv_data}')
                # If no data, then connection is closed
                if not recv_data:
                    log(f"Closing connection to {data.addr}")
                    sel.unregister(sock)
                    sock.close()

                # Else if received Medialon play command
                elif 'tcstart 1' in recv_data:
                    log("Received timecode start command")
                    send_play = True

                elif 'play 1' in recv_data:
                    log("Received play command")
                    send_play = True

                elif 'pause 1' in recv_data:
                    log("Received pause command")
                    send_stop = True

                elif 'stop 1' in recv_data:
                    log("Received stop command")
                    send_stop = True

                elif 'loadplaylist 1 grid' in recv_data:
                    log("Received display grid command")
                    display_grid = True

                elif 'loadplaylist 1 1' in recv_data:
                    log("Received cue show command")
                    cue_show = True

        except:
            log("Connection from client error. Closing socket")
            sel.unregister(sock)
            sock.close()

    
# Handles client connection to the Delta app
def client_thread_function():
    global send_play
    global send_stop
    global display_grid
    global cue_show
    global delta_ip

    while True:
        try: 
            # Setup client socket so can send data to Delta Server.
            clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clientsocket.connect((delta_ip, DELTA_PORT))
            log("Connected to Delta Server App")
            while True:
                if send_play:
                    send_play = False
                    try:
                        log("Sending Play command to Delta")
                        # Send Delta Play command
                        clientsocket.send(b'PLAY\r')  
                    except:
                        log("Error sending Play command.")
                        break

                if send_stop:
                    send_stop = False
                    try:
                        log("Sending Stop command to Delta")
                        # Send Delta Stop command
                        clientsocket.send(b'STOP\r')  
                    except:
                        log("Error sending Stop command.")
                        break
                
                if display_grid:
                    display_grid = False
                    try:
                        log("Sending display grid command to Delta")
                        # Send Delta command
                        clientsocket.send(b"GOTOMARKER 'Grid'\r")  
                    except:
                        log("Error sending display grid command.")
                        break

                if cue_show:
                    cue_show = False
                    try:
                        log("Sending cue show command to Delta")
                        # Send Delta command
                        clientsocket.send(b'GOTOFRAME 1\r')  
                        time.sleep(0.5)
                        clientsocket.send(b'CUE\r')
                    except:
                        log("Error sending cue show command.")
                        break

                time.sleep(0.01)
        except:
            # Connection was refused, wait for some time before retrying
            time.sleep(5)

# Log utility function
def log(message: str):
    # Get the current date and time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Print the output with the current time and date
    print(f"[{current_time}] {message}")

if __name__ == "__main__":
    main()
    log("Delta Command Utility App closing. COMMANDS FROM RSS WILL NO LONGER BE ABLE TO CONTROL THE DELTA SERVER. \n" + 
        "If unintentional, re-run the app or restart the server. \n" + 
        "BYE")