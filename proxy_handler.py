import socket
import threading

class ProxyHandler:
    def __init__(self):
        self.config = ProxyConfig()

    def handle_client(self, connection):
        with connection:
            version, nmethods = connection.recv(2)
            methods = self.get_available_methods(nmethods, connection)

            if 2 not in set(methods):
                return

            connection.sendall(bytes([self.config.SOCKS_VERSION, 2]))

            if not self.verify_credentials(connection):
                return

            version, cmd, _, address_type = connection.recv(4)

            if address_type == 1:
                address = socket.inet_ntoa(connection.recv(4))
            elif address_type == 3:
                domain_length = connection.recv(1)[0]
                address = connection.recv(domain_length)
                address = socket.gethostbyname(address)

            port = int.from_bytes(connection.recv(2), 'big', signed=False)

            try:
                if cmd == 1:
                    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote.connect((address, port))
                    bind_address = remote.getsockname()
                    print(f"* Connected to {address} {port}")
                else:
                    connection.close()

                addr = int.from_bytes(socket.inet_aton(bind_address[0]), 'big', signed=False)
                port = bind_address[1]

                reply = b''.join([
                    self.config.SOCKS_VERSION.to_bytes(1, 'big'),
                    int(0).to_bytes(1, 'big'),
                    int(0).to_bytes(1, 'big'),
                    int(1).to_bytes(1, 'big'),
                    addr.to_bytes(4, 'big'),
                    port.to_bytes(2, 'big')
                ])
            except Exception as e:
                reply = self.generate_failed_reply(address_type, 5)

            connection.sendall(reply)

            if reply[1] == 0 and cmd == 1:
                self.exchange_loop(connection, remote)

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.config.HOST, self.config.PORT))
            s.listen()

            print(f"* Socks5 proxy server is running on {self.config.HOST}:{self.config.PORT}")

            while True:
                conn, addr = s.accept()
                print(f"* New connection from {addr}")
                t = threading.Thread(target=self.handle_client, args=(conn,))
                t.start()
