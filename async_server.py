__author__ = 'ziyan.yin'

import asyncio
import logging
from urllib import parse

TIMEOUT = 1000
HOST = '0.0.0.0'
PORT = 11212

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

    async def reply(data, wait=False):
        writer.write(data)
        if wait:
            await writer.drain()

    return await http_accept(method, path, args, lines, reply)


async def http_accept(method, path, args, lines, reply):
    url = parse.urlparse(path)
    if method == 'GET' and not url.hostname:
        raise ConnectionError(f'404 {method} {url.path}')
    elif method == 'CONNECT':
        address = get_addr(path)
        message = f"{args} 200 Connection Established\r\nConnection: close\r\n\r\n".encode()
        return address, lambda writer: reply(message)
    else:
        address = get_addr(url.hostname)
        message = f'{method} {url.geturl()} {args}\r\n{lines}\r\n\r\n'.encode()

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

    if 'host' in kwargs:
        HOST = kwargs['host']
    if 'port' in kwargs:
        PORT = kwargs['port']
    if 'timeout' in kwargs:
        TIMEOUT = kwargs['timeout']

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
