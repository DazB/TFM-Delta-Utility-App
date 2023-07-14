"""
7th Sense Delta Media Server Command Utility App

This application translates the incoming RSS commands (for the old Mediasonic Servers)
into commands compatible with the 7th Sense Server.

Company: AbsoluteFX Pte Ltd
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

# DELTA_IP = socket.gethostname()
DELTA_IP = 'localhost'
MEDIASONIC_PORT = 4000
DELTA_PORT = 4001

# Send play flag. If true, will send command to play to Delta
send_play = False

def service_connection(key, mask, sel: selectors.DefaultSelector):
    global send_play
    sock = key.fileobj
    data = key.data
    # If socket can read 
    if mask & selectors.EVENT_READ:
        if data == None:
            # When a new client has connected
            conn, addr = sock.accept()  # Should be ready to read
            print(f"Accepted connection from {addr}")
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
                print(f"Closing connection to {data.addr}")
                sel.unregister(sock)
                sock.close()

            # Else if received Medialon play command
            elif 'TCSTART 1!' in recv_data:
                print("Received timecode start command")
                send_play = True
            
def client_thread_function():
    global send_play
    while True:
        try: 
            # Setup client socket so can send data to Delta Server. Can block because seperate thread
            clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clientsocket.connect(('localhost', DELTA_PORT))
            while True:
                if send_play:
                    send_play = False
                    print("Sending play command to Delta")
                    try:
                        clientsocket.send(b'Play')  # Should be ready to write
                    except:
                        print("Error sending play command. Delta Server not running?")
                        break
                time.sleep(0.01)
        except:
            # Connection was refused, wait for some time before retrying
            print("Unable to make connection. Trying again...")
            time.sleep(5)

def main():
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
    print(f"Listening on {(DELTA_IP, MEDIASONIC_PORT)}")
    # Register the server to be monitored for read events
    sel.register(serversocket, selectors.EVENT_READ, data=None)

    # Start client thread so can send data to Delta Server
    client_thread = threading.Thread(target=client_thread_function)
    client_thread.start()

    try:
        while True:
            # Will block until a socket is ready for I/O
            events = sel.select(timeout=None)
            for key, mask in events:
                service_connection(key, mask, sel)
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    finally:
        sel.close()


if __name__ == "__main__":
    main()