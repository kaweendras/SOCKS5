import socket
import threading
import select
from concurrent.futures import ThreadPoolExecutor
import logging

SOCKS_VERSION = 5

class Proxy:
    def __init__(self):
        self.username = "root"
        self.password = "12345"
        logging.basicConfig(level=logging.INFO)

    def handle_client(self, connection):
        logging.info("* New client connection")

        try:
            version, nmethods = connection.recv(2)

            if version != SOCKS_VERSION:
                raise ValueError("* Invalid SOCKS version")

            methods = self.get_available_methods(nmethods, connection)

            if 2 not in set(methods):
                connection.close()
                logging.error("* Connection closed: Unsupported authentication methods")
                return

            connection.sendall(bytes([SOCKS_VERSION, 2]))

            if not self.verify_credentials(connection):
                return

            version, cmd, _, address_type = connection.recv(4)

            if address_type == 1:  # IPv4
                address = socket.inet_ntoa(connection.recv(4))
            elif address_type == 3:  # Domain name
                domain_length = connection.recv(1)[0]
                address = connection.recv(domain_length).decode('utf-8')
                address = socket.gethostbyname(address)

            port = int.from_bytes(connection.recv(2), 'big', signed=False)

            try:
                if cmd == 1:  # CONNECT
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as remote:
                        remote.connect((address, port))
                        bind_address = remote.getsockname()
                        logging.info(f"* Connected to {address} {port}")
                else:
                    connection.close()
                    logging.error("* Connection closed: Unsupported command")
                    return

                addr = int.from_bytes(socket.inet_aton(bind_address[0]), 'big', signed=False)
                port = bind_address[1]

                reply = b''.join([
                    SOCKS_VERSION.to_bytes(1, 'big'),
                    int(0).to_bytes(1, 'big'),
                    int(0).to_bytes(1, 'big'),
                    int(1).to_bytes(1, 'big'),
                    addr.to_bytes(4, 'big'),
                    port.to_bytes(2, 'big')
                ])
            except Exception as e:
                reply = self.generate_failed_reply(address_type, 5)
                logging.error(f"* Connection closed: Exception - {e}")

            connection.sendall(reply)
            logging.info("* SOCKS response sent")

            if reply[1] == 0 and cmd == 1:
                self.exchange_loop(connection, remote)

            logging.info("* Connection closed")
        except Exception as e:
            logging.error(f"Error handling client: {e}")
        finally:
            connection.close()

    def exchange_loop(self, client, remote):
        timeout = 60  # 60 seconds timeout
        while True:
            r, _, _ = select.select([client, remote], [], [], timeout)
            if not r:  # Timeout condition
                break

            if client in r:
                data = client.recv(4096)
                if not data:
                    break
                if remote.send(data) <= 0:
                    break

            if remote in r:
                data = remote.recv(4096)
                if not data:
                    break
                if client.send(data) <= 0:
                    break

    def generate_failed_reply(self, address_type, error_number):
        return b''.join([
            SOCKS_VERSION.to_bytes(1, 'big'),
            error_number.to_bytes(1, 'big'),
            int(0).to_bytes(1, 'big'),
            address_type.to_bytes(1, 'big'),
            int(0).to_bytes(4, 'big'),
            int(0).to_bytes(2, 'big')
        ])

    def verify_credentials(self, connection):
        creds = connection.recv(513)  # Max length based on SOCKS authentication (1 byte version, 255 bytes for username/password)
        version = creds[0]
        username_len = creds[1]
        username = creds[2:2 + username_len].decode('utf-8')
        password_len = creds[2 + username_len]
        password = creds[3 + username_len:3 + username_len + password_len].decode('utf-8')

        if username == self.username and password == self.password:
            connection.sendall(bytes([version, 0]))
            logging.info("* Authentication successful")
            return True

        connection.sendall(bytes([version, 0xFF]))
        connection.close()
        logging.error("* Authentication failed")
        return False

    def get_available_methods(self, nmethods, connection):
        methods = connection.recv(nmethods)  # Receive all methods at once
        return [ord(method) for method in methods]

    def run(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            logging.info(f"* SOCKS5 proxy server is running on {host}:{port}")

            with ThreadPoolExecutor(max_workers=10) as executor:
                while True:
                    conn, addr = s.accept()
                    logging.info(f"* New connection from {addr}")
                    executor.submit(self.handle_client, conn)

if __name__ == "__main__":
    proxy = Proxy()
    proxy.run("127.0.0.1", 3000)
