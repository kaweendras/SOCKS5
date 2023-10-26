import socket
import threading
import select

SOCKS_VERSION = 5

class Proxy:
    def __init__(self):
        self.username = "root"
        self.password = "12345"

    def handle_client(self, connection):
        print("* New client connection")

        try:
            version, nmethods = connection.recv(2)

            if version != SOCKS_VERSION:
                print("* Invalid SOCKS version")
                return

            methods = self.get_available_methods(nmethods, connection)

            if 2 not in set(methods):
                # Close connection
                connection.close()
                print("* Connection closed: Unsupported authentication methods")
                return

            connection.sendall(bytes([SOCKS_VERSION, 2]))

            if not self.verify_credentials(connection):
                return

            version, cmd, _, address_type = connection.recv(4)

            if address_type == 1:  # IPv4
                address = socket.inet_ntoa(connection.recv(4))
            elif address_type == 3:  # Domain name
                domain_length = connection.recv(1)[0]
                address = connection.recv(domain_length)
                address = socket.gethostbyname(address)

            port = int.from_bytes(connection.recv(2), 'big', signed=False)

            try:
                if cmd == 1:  # CONNECT
                    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote.connect((address, port))
                    bind_address = remote.getsockname()
                    print(f"* Connected to {address} {port}")
                else:
                    connection.close()
                    print("* Connection closed: Unsupported command")
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
                # Return connection refused error
                reply = self.generate_failed_reply(address_type, 5)
                print("* Connection closed: Exception -", e)

            connection.sendall(reply)
            print("* SOCKS response sent")

            # Establish data exchange
            if reply[1] == 0 and cmd == 1:
                self.exchange_loop(connection, remote)

            print("* Connection closed")
        finally:
            connection.close()

    def exchange_loop(self, client, remote):
        while True:
            # wait until client or remote is available for read
            r, w, e = select.select([client, remote], [], [])

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
            int(0).to_bytes(4, 'big')
        ])

    def verify_credentials(self, connection):
        version = ord(connection.recv(1) if isinstance(connection.recv(1), bytes) else connection.recv(1))  # should be 1

        username_len = ord(connection.recv(1))
        username = connection.recv(username_len).decode('utf-8')

        password_len = ord(connection.recv(1))
        password = connection.recv(password_len).decode('utf-8')

        if username == self.username and password == self.password:
            # success, status = 0
            response = bytes([version, 0])
            connection.sendall(response)
            print("* Authentication successful")
            return True

        # failure, status != 0
        response = bytes([version, 0xFF])
        connection.sendall(response)
        connection.close()
        print("* Authentication failed")
        return False

    def get_available_methods(self, nmethods, connection):
        methods = []
        for i in range(nmethods):
            methods.append(ord(connection.recv(1))
                          if isinstance(connection.recv(1), bytes)
                          else connection.recv(1))
        return methods

    def run(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, port))
        s.listen()

        print("* Socks5 proxy server is running on {}:{}".format(host, port))

        while True:
            conn, addr = s.accept()
            print("* New connection from {}".format(addr))
            t = threading.Thread(target=self.handle_client, args=(conn,))
            t.start()

if __name__ == "__main__":
    proxy = Proxy()
    proxy.run("127.0.0.1", 3000)
