# proxy_server.py
from Handler.proxy_handler import ProxyHandler

if __name__ == "__main__":
    proxy_handler = ProxyHandler()
    proxy_handler.run()
