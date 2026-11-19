import queue, threading
from PySide6.QtCore import QThread, Signal

class OCRWorker(QThread):
    text_found = Signal(str, str)
    def __init__(self, bus=None):
        super().__init__()
        self.queue = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()

    def submit_frame(self, frame):
        try:
            if self.queue.full():
                self.queue.get_nowait()
            self.queue.put_nowait(frame)
        except queue.Empty:
            pass

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            from rapidocr import RapidOCR
            engine = RapidOCR()
            while not self._stop_event.is_set():
                try:
                    frame = self.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                result = engine(frame)
                if result.txts:
                    text = " ".join(str(t) for t in result.txts)
                    if text.strip():
                        self.text_found.emit(text, "Pantalla (OCR)")
        except Exception as exc:
            print("OCR error:", exc)
            print("Comprueba la instalación de rapidocr y onnxruntime.")
