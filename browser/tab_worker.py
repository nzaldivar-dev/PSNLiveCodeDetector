import base64
import os
import threading
import time

import numpy as np
from PySide6.QtCore import QThread, Signal

from browser.chrome import CDP_URL

_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tab_audio.js")
TARGET_RATE = 16000


def find_page(browser, target_id):
    """Localiza el Page de Playwright cuyo targetId coincide con el elegido en la UI."""
    for context in browser.contexts:
        for page in context.pages:
            session = context.new_cdp_session(page)
            try:
                info = session.send("Target.getTargetInfo")["targetInfo"]
            finally:
                session.detach()
            if info["targetId"] == target_id:
                return page
    return None


class TabWorker(QThread):
    """Se conecta a Chrome por CDP y, solo para la pestaña elegida, emite capturas
    de pantalla (frame) y, opcionalmente, su audio (audio_chunk, float32 mono 16 kHz).

    Todo el uso de Playwright ocurre en este hilo: la API sync no es thread-safe.
    """
    frame = Signal(object)
    audio_chunk = Signal(object)
    status = Signal(str)

    def __init__(self, target_id, interval=2, capture_audio=True, capture_frames=True):
        super().__init__()
        self.target_id = target_id
        self.interval = interval
        self.capture_audio = capture_audio
        self.capture_frames = capture_frames
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def _on_audio(self, rate, b64):
        pcm = np.frombuffer(base64.b64decode(b64), dtype=np.int16).astype(np.float32) / 32768.0
        if rate != TARGET_RATE:
            n = int(len(pcm) * TARGET_RATE / rate)
            pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
        self.audio_chunk.emit(pcm)

    def run(self):
        try:
            import cv2
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            print("Browser import error:", exc)
            return
        pw = None
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.connect_over_cdp(CDP_URL)
            page = find_page(browser, self.target_id)
            if page is None:
                self.status.emit("la pestaña elegida ya no existe; actualiza la lista")
                return
            if self.capture_audio:
                with open(_JS, encoding="utf-8") as fh:
                    script = fh.read()
                page.expose_function("__psnAudioSend", self._on_audio)
                page.expose_function("__psnAudioLog", lambda msg: print("Tab audio:", msg))
                page.add_init_script(script)  # sobrevive a recargas/navegación
                page.evaluate(script)
            next_shot = 0.0
            failures = 0
            while not self._stop_event.is_set():
                page.wait_for_timeout(100)  # atiende los callbacks de audio
                if page.is_closed():
                    self.status.emit("la pestaña se cerró")
                    return
                if not self.capture_frames or time.monotonic() < next_shot:
                    continue
                next_shot = time.monotonic() + self.interval
                try:
                    png = page.screenshot(type="png", timeout=10000)
                    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
                    self.frame.emit(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                    failures = 0
                except Exception as exc:
                    failures += 1
                    print("Tab screenshot error:", exc)
                    if failures == 3:
                        self.status.emit("no se puede capturar la pestaña (¿minimizada?)")
        except Exception as exc:
            print("Tab worker error:", exc)
            self.status.emit("error de conexión con Chrome; ¿está abierto con el botón «Abrir Chrome»?")
        finally:
            if pw is not None:
                try:
                    pw.stop()
                except Exception:
                    pass
