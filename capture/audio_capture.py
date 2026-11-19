import threading, time
import numpy as np
from PySide6.QtCore import QThread, Signal

class AudioWorker(QThread):
    audio_chunk = Signal(object)
    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            import soundcard as sc
            speaker = sc.default_speaker()
            mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            while not self._stop_event.is_set():
                data = mic.record(samplerate=16000, numframes=16000 * 5, channels=1)
                if data is not None and len(data):
                    audio = np.asarray(data, dtype=np.float32).reshape(-1)
                    self.audio_chunk.emit(audio)
        except Exception as exc:
            print("Audio loopback error:", exc)
            print("Verifica que Windows permita capturar el audio del dispositivo de salida.")
            while not self._stop_event.wait(1):
                pass
