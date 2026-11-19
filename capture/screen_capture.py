import threading, time
import numpy as np
from PySide6.QtCore import QThread, Signal

class ScreenWorker(QThread):
    frame = Signal(object)
    def __init__(self, monitor_index=0, interval=2, bus=None):
        super().__init__()
        self.monitor_index = monitor_index
        self.interval = interval
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            import mss
            import cv2
            with mss.mss() as sct:
                monitors = sct.monitors
                index = min(self.monitor_index + 1, len(monitors) - 1)
                while not self._stop_event.is_set():
                    shot = sct.grab(monitors[index])
                    frame = np.array(shot)[:, :, :3]
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame.emit(frame)
                    self._stop_event.wait(self.interval)
        except Exception as exc:
            print("Screen capture error:", exc)
