"""
7th Sense Delta Media Server Command Utility App

This application translates the incoming RSS commands (for the old Mediasonic Servers)
into commands compatible with the 7th Sense Server.

How it works:
We have a server that accepts connections from the Medialon. We use selectors and wait for a
read event, indicating a connection and message.

We simultaneously have a client thread that attempts to make a connection to the Delta Server
App. (Small aside: selectors in Windows for clients seem to always have a read event, even
when not connected. Hence using thread for client, which work well anyway)

When the server sends the specific play command, we set a global flag. The client thread polls 
this flag, and if true, will send the Delta Play command. 

It does this forever and then we die.

Company: Absolute FX Pte Ltd
Author: Dariush Bahri
Application Version: 1
Date: 13th July 2023
Python Version: 3.11.4 64-bit
"""

import socket
import selectors
import types
import threading
import time
import re
import subprocess
from datetime import datetime

# Get IP of the local machine
DELTA_IP = socket.gethostbyname(socket.gethostname())
MEDIASONIC_PORT = 4000
DELTA_PORT = 23

# Send play flag. If true, will send command to play to Delta
send_play = False

def main():
    """Main app function"""

    # Run the ipconfig command and capture the output
    output = subprocess.check_output(['ipconfig']).decode('utf-8')
    # Extract the IPv4 address for the Ethernet adapter
    ip_pattern = r'Ethernet adapter Ethernet:\s+.*?IPv4 Address\. . . . . . . . . . . : (\d+\.\d+\.\d+\.\d+)'
    match = re.search(ip_pattern, output, re.IGNORECASE | re.DOTALL)
    if match:
        DELTA_IP = match.group(1)

    # Handles server multiplexing
    sel = selectors.DefaultSelector()

    # Setup server socket to Medialon can connect
    # Create an INET, STREAMing socket
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind the server socket to Delta IP, and the Mediasonic port
    serversocket.bind((DELTA_IP, MEDIASONIC_PORT))
    # Open server socket. Listen up to a max of 2 connections (one for RSS, one for debugging)
    serversocket.listen(2)
    serversocket.setblocking(False)
    log(f"Listening on {(DELTA_IP, MEDIASONIC_PORT)}")
    # Register the server to be monitored for read events
    sel.register(serversocket, selectors.EVENT_READ, data=None)

    # Start client thread so can send data to Delta Server
    log("Starting client thread. Attempting connection to Delta Server App")
    client_thread = threading.Thread(target=client_thread_function, daemon=True)
    client_thread.start()

    try:
        while True:
            # Returns list if server socket is ready for I/O
            events = sel.select(timeout=1)
            # Server ready for I/O. Service that boi
            for key, mask in events:
                service_connection(key, mask, sel)
    except KeyboardInterrupt:
        log("Caught keyboard interrupt, exiting")
    finally:
        sel.close()
        

def service_connection(key, mask, sel: selectors.DefaultSelector):
    """ Handles incoming server messages """
    global send_play
    sock: socket.socket = key.fileobj
    data = key.data
    # If socket can read 
    if mask & selectors.EVENT_READ:
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
            recv_data = sock.recv(1024).decode()  # Should be ready to read
            # If no data, then connection is closed
            if not recv_data:
                log(f"Closing connection to {data.addr}")
                sel.unregister(sock)
                sock.close()

            # Else if received Medialon play command
            elif 'TCSTART 1!' in recv_data:
                log("Received timecode start command")
                send_play = True
            
def client_thread_function():
    """ Handles client connection to the Delta app """
    global send_play
    while True:
        try: 
            # Setup client socket so can send data to Delta Server.
            clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clientsocket.connect(('localhost', DELTA_PORT))
            log("Connected to Delta Server App")
            while True:
                if send_play:
                    send_play = False
                    log("Sending play command to Delta")
                    try:
                        # Send Delta Play command
                        clientsocket.send(b'Play')  
                    except:
                        log("Error sending play command. Delta Server not running? Will attempt reconnect")
                        break
                time.sleep(0.01)
        except:
            # Connection was refused, wait for some time before retrying
            time.sleep(5)


def log(message: str):
    # Log utility function
    # Get the current date and time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Print the output with the current time and date
    print(f"[{current_time}] {message}")


if __name__ == "__main__":
    print("---------------------Delta Command Utility App---------------------\n" +
        "This app acts translates the incoming RSS commands \n" +
        "into commands compatible with the 7th Sense Server. \n\n" +
        "IT MUST REMAIN RUNNING WHILE THE RIDE IS IN OPERATION.\n" +
        "IF IT IS CLOSED, THE RSS CANNOT PLAY THE VIDEO \n\n" +
        "To exit the app, use CTRL + C, or close the terminal")
    main()
    log("Delta Command Utility App closing. COMMANDS FROM RSS WILL NO LONGER BE ABLE TO CONTROL THE DELTA SERVER. \n" + 
        "If unintentional, re-run the app (python app.py in command line), or restart the server. \n" + 
        "BYE")
    