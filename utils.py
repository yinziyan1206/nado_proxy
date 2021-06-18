#!/usr/bin/env python
__author__ = 'ziyan.yin'


def get_addr(package):
    data = package.split(b'\r\n')
    method = data[0]
    is_ssl = False
    if method.startswith(b'CONNECT'):
        addr = method.split(b' ')[1].decode()
        if ':' in addr:
            host = addr[:addr.find(':')]
            port = int(addr[addr.find(':') + 1:])
        else:
            host = addr
            port = 443
        is_ssl = True
    else:
        for header in data:
            if header.startswith(b'Host'):
                addr = header.split(b' ')[1].decode()
                break
        else:
            addr = method.split(b'/')[2].decode()

        if ':' in addr:
            host = addr[:addr.find(':')]
            port = int(addr[addr.find(':')+1:])
        else:
            host = addr
            port = 80
    protocol = method.split(b' ')[2].decode()
    return host, port, is_ssl, protocol
