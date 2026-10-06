"""Standalone web server for the homunculus app: python -m homunculus.web  ->  http://127.0.0.1:8765/"""
import time
from . import server

if __name__ == "__main__":
    server.start(); print("serving the homunculus app on", f"http://127.0.0.1:{server.PORT}/", flush=True)
    while True: time.sleep(3600)
