__author__ = 'ziyan.yin'

import asyncio
import logging
from urllib import parse

TIMEOUT = 1000
HOST = '0.0.0.0'
PORT = 11212
WHITE_LIST = None
AUTH = None

logger = logging.getLogger('proxy')


def get_addr(uri):
    if ':' in uri:
        host = uri[:uri.rfind(':')]
        port = int(uri[uri.rfind(':') + 1:])
    else:
        host = uri
        port = 80
    return host, port


async def accept(reader, writer):
    lines = await reader.readuntil(b'\r\n\r\n')
    headers = lines[:-4].decode().split('\r\n')
    method, path, args = headers[0].split(' ')
    lines = '\r\n'.join(i for i in headers if not i.startswith('Proxy-'))
    headers = dict(i.split(': ', 1) for i in headers if ': ' in i)
    print(headers)

    async def reply(data, wait=False):
        writer.write(data)
        if wait:
            await writer.drain()

    return await http_accept(method, path, args, lines, reply, headers.get('Proxy-Authorization'))


async def http_accept(method, path, args, lines, reply, auth):
    url = parse.urlparse(path)
    if method == 'GET' and not url.hostname:
        raise ConnectionError(f'404 {method} {url.path}')
    if AUTH:
        if auth not in AUTH:
            await reply(
                f'{args} 407 Proxy Authentication Required\r\n'
                f'Connection: close\r\nProxy-Authenticate: Basic realm="simple"\r\n\r\n'.encode(),
                wait=True
            )
            raise ConnectionError('Unauthorized')
    elif method == 'CONNECT':
        address = get_addr(path)
        message = f"{args} 200 Connection Established\r\nConnection: close\r\n\r\n".encode()
        return address, lambda writer: reply(message)
    else:
        address = url.hostname, url.port if url.port else 80
        new_path = url._replace(netloc='', scheme='').geturl()
        message = f'{method} {new_path} {args}\r\n{lines}\r\n\r\n'.encode()

        async def connected(writer):
            writer.write(message)
            return True

        return address, connected


async def pipe(reader, writer):
    try:
        while not reader.at_eof() and not writer.is_closing():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception as ex:
        logger.error(ex)
    finally:
        writer.close()


async def handle(reader, writer):
    try:
        client_ip, client_port = writer.get_extra_info('peername')
        if WHITE_LIST and client_ip not in WHITE_LIST:
            raise ConnectionRefusedError()
        address, connected = await accept(reader, writer)
        logger.info(f"redirect: {address}")
        reader_remote, writer_remote = await asyncio.wait_for(asyncio.open_connection(*address), timeout=TIMEOUT)
        await connected(writer_remote)
        asyncio.ensure_future(pipe(reader_remote, writer))
        asyncio.ensure_future(pipe(reader, writer_remote))
    except Exception as ex:
        logger.error(ex)
        raise


def main(**kwargs):
    global HOST
    global PORT
    global TIMEOUT
    global WHITE_LIST
    global AUTH

    if 'host' in kwargs:
        HOST = kwargs['host']
    if 'port' in kwargs:
        PORT = kwargs['port']
    if 'timeout' in kwargs:
        TIMEOUT = kwargs['timeout']
    if 'white_list' in kwargs:
        WHITE_LIST = kwargs['white_list']
    if 'auth' in kwargs:
        AUTH = kwargs['auth']

    loop = asyncio.get_event_loop()
    process = asyncio.start_server(handle, HOST, PORT)
    server = loop.run_until_complete(process)

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        # Close the server
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()
        raise


if __name__ == '__main__':
    logging.basicConfig(
        level='DEBUG',
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
