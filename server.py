__author__ = 'ziyan.yin'

import logging
import socket
import threading

import utils

TIMEOUT = 1000
BUF_SIZE = 4096
HOST = '0.0.0.0'
PORT = 11212

_logger = logging.getLogger('proxy')


def communicate(client, server):
    try:
        while data := client.recv(BUF_SIZE):
            server.sendall(data)
    except ConnectionError:
        pass
    finally:
        server.close()


def handle(client):
    client.settimeout(TIMEOUT)
    message = b''
    try:
        while data := client.recv(BUF_SIZE):
            message = b"%s%s" % (message, data)
            if data.endswith(b'\r\n\r\n'):
                break
    except ConnectionError:
        return

    if not message:
        client.close()
        return
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host, port, is_ssl, protocol = utils.get_addr(message)
    _logger.info((host, port))
    try:
        server.connect((host, port))
        server.settimeout(TIMEOUT)
        if is_ssl:
            data = b"HTTP/1.0 200 Connection Established\r\n\r\n"
            client.sendall(data)
            threading.Thread(target=communicate, args=(client, server)).start()
            threading.Thread(target=communicate, args=(server, client)).start()
        else:
            server.sendall(message)
            threading.Thread(target=communicate, args=(client, server)).start()
            threading.Thread(target=communicate, args=(server, client)).start()
    except ConnectionError:
        server.close()
        client.close()


def main(ip, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ip, port))
    server.listen(10)
    _logger.info(f'proxy start on {port}')
    while True:
        conn, addr = server.accept()
        _logger.debug(addr)
        threading.Thread(target=handle, args=(conn,)).start()
