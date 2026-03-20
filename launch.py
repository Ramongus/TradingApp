"""
Launcher: starts the Flask server and opens localhost:5000 once it's ready.
"""
import subprocess
import sys
import time
import webbrowser
import urllib.request
from pathlib import Path

HOST    = "http://localhost:5000"
APP_DIR = Path(__file__).parent / "TradingAppWeb"

def server_ready(url: str, timeout: int = 30) -> bool:
    """Poll until the server responds or timeout (seconds)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("Iniciando servidor Flask...")
    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=APP_DIR,
    )

    print(f"Esperando a que el servidor esté listo en {HOST} ...")
    if server_ready(HOST):
        print("Servidor listo. Abriendo navegador...")
        webbrowser.open(HOST)
    else:
        print("El servidor tardó demasiado en arrancar. Abrelo manualmente en:", HOST)

    print("\nPresiona Ctrl+C para detener el servidor.\n")
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        proc.terminate()
        proc.wait()
        print("Servidor detenido.")

if __name__ == "__main__":
    main()
