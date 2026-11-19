"""Lanzamiento de Chrome con CDP y listado de pestañas.

Desde Chrome 136 el puerto de depuración se ignora con el perfil por defecto,
así que se usa un perfil propio (chrome-profile/) donde el usuario inicia
sesión una sola vez en YouTube y PlayStation.
"""
import json
import os
import subprocess
import time
import urllib.request

CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chrome-profile")

_CHROME_CANDIDATES = [
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
]


def find_chrome():
    for path in _CHROME_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def cdp_available(timeout=1.0):
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=timeout):
            return True
    except Exception:
        return False


def launch_chrome(start_url="https://www.youtube.com/", wait=15.0):
    """Abre Chrome con CDP si no está ya disponible. Devuelve True si el puerto responde."""
    if cdp_available():
        return True
    chrome = find_chrome()
    if not chrome:
        raise FileNotFoundError("No se encontró Chrome en las rutas habituales.")
    os.makedirs(PROFILE_DIR, exist_ok=True)
    subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={PROFILE_DIR}",
            "--autoplay-policy=no-user-gesture-required",
            "--no-first-run",
            "--no-default-browser-check",
            start_url,
        ],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        close_fds=True,
    )
    deadline = time.time() + wait
    while time.time() < deadline:
        if cdp_available():
            return True
        time.sleep(0.3)
    return False


def list_tabs():
    """Pestañas abiertas: lista de dicts con id (targetId), title y url."""
    with urllib.request.urlopen(f"{CDP_URL}/json/list", timeout=2) as resp:
        targets = json.load(resp)
    tabs = []
    for t in targets:
        url = t.get("url", "")
        if t.get("type") != "page" or url.startswith(("devtools://", "chrome://", "chrome-extension://")):
            continue
        tabs.append({"id": t["id"], "title": t.get("title") or url, "url": url})
    return tabs
