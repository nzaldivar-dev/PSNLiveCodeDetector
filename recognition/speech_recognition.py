import glob, os, queue, site, threading
from PySide6.QtCore import QThread, Signal


def _register_nvidia_dlls():
    """Hace visibles cuBLAS/cuDNN instalados por pip (paquetes nvidia-*-cu12) para ctranslate2.

    ctranslate2 las carga con LoadLibrary en tiempo de ejecución, así que van en PATH.
    """
    for base in site.getsitepackages():
        for bin_dir in glob.glob(os.path.join(base, "nvidia", "*", "bin")):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(bin_dir)
            except (AttributeError, OSError):
                pass

class SpeechWorker(QThread):
    transcript = Signal(str, str)
    def __init__(self, use_gpu=True, bus=None):
        super().__init__()
        self.use_gpu = use_gpu
        self.queue = queue.Queue(maxsize=8)
        self._stop_event = threading.Event()

    def submit_audio(self, audio):
        try:
            self.queue.put_nowait(audio)
        except queue.Full:
            pass

    def stop(self):
        self._stop_event.set()

    @staticmethod
    def _transcribe(model, audio):
        # El generador de segmentos es perezoso: hay que consumirlo aquí para que
        # cualquier error de CUDA se lance dentro del try del llamador.
        segments, _ = model.transcribe(
            audio, language=None, beam_size=1, vad_filter=True,
            condition_on_previous_text=False
        )
        return " ".join(s.text.strip() for s in segments).strip()

    def run(self):
        try:
            _register_nvidia_dlls()
            from faster_whisper import WhisperModel
            device = "cuda" if self.use_gpu else "cpu"
            compute = "float16" if device == "cuda" else "int8"
            try:
                model = WhisperModel("small", device=device, compute_type=compute)
            except Exception as gpu_error:
                print("No se pudo iniciar Whisper en GPU:", gpu_error)
                print("Usando CPU como alternativa.")
                model = WhisperModel("small", device="cpu", compute_type="int8")
            while not self._stop_event.is_set():
                try:
                    audio = self.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                try:
                    text = self._transcribe(model, audio)
                except Exception as err:
                    if device == "cpu":
                        raise
                    # CUDA suele fallar aquí (DLL ausente), no al crear el modelo.
                    print("Fallo de Whisper en GPU al transcribir:", err)
                    print("Cambiando a CPU.")
                    device = "cpu"
                    model = WhisperModel("small", device="cpu", compute_type="int8")
                    text = self._transcribe(model, audio)
                if text:
                    self.transcript.emit(text, "Audio")
        except Exception as exc:
            print("Speech recognition error:", exc)
