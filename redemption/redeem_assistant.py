import threading
import time

from PySide6.QtCore import QThread, Signal

from browser.chrome import CDP_URL, launch_chrome

# Redirige a la tienda de la región del usuario y abre el diálogo de canje.
# El código NO va en la URL: se escribe en el campo con Playwright.
REDEEM_URL = "https://store.playstation.com/redeem"
WAIT_FIELD_SECONDS = 300

_FIELD_SELECTORS = [
    'input[placeholder*="code" i]', 'input[placeholder*="código" i]', 'input[placeholder*="codigo" i]',
    'input[aria-label*="code" i]', 'input[aria-label*="código" i]', 'input[aria-label*="codigo" i]',
    'input[name*="code" i]', 'input[id*="code" i]', 'input[data-qa*="code" i]',
]


def _find_field(page):
    for frame in page.frames:
        for selector in _FIELD_SELECTORS:
            try:
                field = frame.locator(selector).first
                if field.is_visible() and field.is_editable():
                    return field
            except Exception:
                continue
    return None


class RedeemWorker(QThread):
    """Abre la tienda de PlayStation en el Chrome con CDP y rellena el campo del código.

    Por diseño NUNCA pulsa ningún botón: el canje lo confirma siempre la persona.
    La pestaña queda abierta en Chrome al terminar.
    """
    status = Signal(str)

    def __init__(self, code):
        super().__init__()
        self.code = code
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        pw = None
        try:
            from playwright.sync_api import sync_playwright
            self.status.emit("canje: abriendo Chrome…")
            if not launch_chrome():
                self.status.emit("canje: no se pudo abrir Chrome con CDP")
                return
            pw = sync_playwright().start()
            browser = pw.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            page = context.new_page()
            page.goto(REDEEM_URL, wait_until="domcontentloaded")
            page.bring_to_front()
            self.status.emit("canje: esperando el campo del código (inicia sesión si hace falta)…")
            deadline = time.monotonic() + WAIT_FIELD_SECONDS
            while time.monotonic() < deadline and not self._stop_event.is_set():
                field = _find_field(page)
                if field is not None:
                    field.fill(self.code.replace("-", ""))
                    self.status.emit("canje: código escrito. Revisa región/cuenta y pulsa canjear tú mismo")
                    return
                page.wait_for_timeout(1000)
            if not self._stop_event.is_set():
                self.status.emit("canje: no apareció el campo del código (tiempo agotado)")
        except Exception as exc:
            print("Redeem error:", exc)
            self.status.emit("canje: error, mira la consola")
        finally:
            if pw is not None:
                try:
                    pw.stop()
                except Exception:
                    pass
