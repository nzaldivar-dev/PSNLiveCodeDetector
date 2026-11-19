from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QPlainTextEdit, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox, QFormLayout, QSpinBox
)
from capture.audio_capture import AudioWorker  # respaldo: audio del sistema
from browser.chrome import cdp_available, launch_chrome, list_tabs
from browser.tab_worker import TabWorker
from recognition.speech_recognition import SpeechWorker
from recognition.ocr_recognition import OCRWorker
from processing.code_extractor import extract_codes
from processing.deduplication import CodeRegistry
from redemption.redeem_assistant import RedeemWorker

class Bus(QObject):
    status = Signal(str)
    text = Signal(str, str)
    code = Signal(str, str, float)

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PSN Live Code Detector")
        self.resize(900, 850)
        self.bus = Bus()
        self.bus.status.connect(self.set_status)
        self.bus.text.connect(self.add_transcript)
        self.bus.code.connect(self.add_code)
        self.registry = CodeRegistry()
        self.workers = []
        self.redeemer = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("PSN Live Code Detector")
        title.setStyleSheet("font-size:24px;font-weight:700")
        subtitle = QLabel("Detector local de códigos hablados y mostrados en YouTube LIVE")
        subtitle.setStyleSheet("color:#94a3b8")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        config = QGroupBox("Configuración de monitoreo")
        form = QFormLayout(config)
        self.tab = QComboBox()
        self.tab.setMinimumWidth(420)
        self.refresh_btn = QPushButton("Actualizar")
        self.chrome_btn = QPushButton("Abrir Chrome")
        self.refresh_btn.clicked.connect(self.refresh_tabs)
        self.chrome_btn.clicked.connect(self.open_chrome)
        tab_row = QHBoxLayout()
        tab_row.addWidget(self.tab, 1)
        tab_row.addWidget(self.refresh_btn)
        tab_row.addWidget(self.chrome_btn)
        self.mode = QComboBox()
        self.mode.addItems(["Audio + OCR (pantalla)", "Solo audio (transcripción)", "Solo OCR (pantalla)"])
        self.tab_audio = QCheckBox("Audio solo de la pestaña (si falla, desmarcar para usar el audio del sistema)")
        self.tab_audio.setChecked(True)
        self.interval = QSpinBox()
        self.interval.setRange(1, 10)
        self.interval.setValue(2)
        self.gpu = QCheckBox("Usar GPU NVIDIA (CUDA)")
        self.gpu.setChecked(True)
        self.gpu.setToolTip("Requiere PyTorch/CUDA compatible y drivers NVIDIA.")
        form.addRow("Pestaña de Chrome:", tab_row)
        form.addRow("Detectar con:", self.mode)
        form.addRow("Audio:", self.tab_audio)
        form.addRow("Intervalo OCR (segundos):", self.interval)
        form.addRow("Reconocimiento:", self.gpu)
        layout.addWidget(config)

        controls = QHBoxLayout()
        self.start_btn = QPushButton("▶ Iniciar monitoreo")
        self.stop_btn = QPushButton("■ Detener")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_monitoring)
        self.stop_btn.clicked.connect(self.stop_monitoring)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        self.status = QLabel("Estado: detenido")
        self.status.setStyleSheet("font-weight:600;color:#f59e0b")
        controls.addWidget(self.status, 1)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Hora", "Código detectado", "Origen", "Confianza"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 160)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.clear_codes_btn = QPushButton("Limpiar códigos")
        self.clear_codes_btn.clicked.connect(self.clear_codes)
        layout.addLayout(self._section_header("Códigos encontrados", self.clear_codes_btn))
        layout.addWidget(self.table, 2)

        actions = QHBoxLayout()
        self.copy_btn = QPushButton("Copiar seleccionado")
        self.redeem_btn = QPushButton("Abrir canje oficial")
        self.copy_btn.clicked.connect(self.copy_selected)
        self.redeem_btn.clicked.connect(self.open_redeem)
        actions.addWidget(self.copy_btn)
        actions.addWidget(self.redeem_btn)
        layout.addLayout(actions)

        self.feed = QPlainTextEdit()
        self.feed.setReadOnly(True)
        self.feed.setMaximumBlockCount(500)
        self.feed.setPlaceholderText("Aquí aparece todo lo que se transcribe del audio y se lee de la pantalla…")
        self._last_feed = {}
        self.clear_feed_btn = QPushButton("Limpiar feed")
        self.clear_feed_btn.clicked.connect(self.clear_feed)
        layout.addLayout(self._section_header("Feed de captura (audio y pantalla)", self.clear_feed_btn))
        layout.addWidget(self.feed, 2)

        self.log = QLabel("Pulsa «Abrir Chrome», abre el LIVE en esa ventana, pulsa «Actualizar» y elige la pestaña. "
                          "La pestaña debe estar visible (no minimizada) para poder capturarla.")
        self.log.setWordWrap(True)
        self.log.setStyleSheet("color:#94a3b8;padding:8px")
        layout.addWidget(self.log)
        self.setCentralWidget(root)
        self.refresh_tabs()
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#0f172a; color:#e2e8f0; }
            QGroupBox { border:1px solid #334155; border-radius:8px; margin-top:10px; padding:10px; }
            QLineEdit, QComboBox, QSpinBox, QTableWidget { background:#1e293b; color:#f8fafc; border:1px solid #475569; padding:6px; }
            QPushButton { background:#2563eb; color:white; border:0; border-radius:6px; padding:10px 14px; font-weight:600; }
            QPushButton:disabled { background:#475569; color:#94a3b8; }
            QHeaderView::section { background:#1e293b; color:#e2e8f0; padding:6px; }
            QTableWidget::item:selected, QTableWidget::item:selected:!active { background:#16a34a; color:white; }
            QPlainTextEdit { background:#1e293b; color:#cbd5e1; border:1px solid #475569; padding:6px; }
        """)

    @staticmethod
    def _section_header(title, button):
        button.setStyleSheet("padding:4px 10px;background:#475569")
        row = QHBoxLayout()
        row.addWidget(QLabel(title))
        row.addStretch(1)
        row.addWidget(button)
        return row

    def clear_codes(self):
        # El registro de duplicados se conserva a propósito: el OCR sigue viendo el mismo código en
        # pantalla y, si se olvidara, reaparecería en la tabla a los pocos segundos.
        self.table.setRowCount(0)
        self.set_status("códigos limpiados")

    def clear_feed(self):
        self.feed.clear()
        self._last_feed = {}  # para que el texto que siga en pantalla vuelva a mostrarse

    def set_status(self, value):
        self.status.setText("Estado: " + value)

    def refresh_tabs(self):
        previous = self.tab.currentData()
        self.tab.clear()
        if not cdp_available():
            self.tab.addItem("(Chrome no está abierto con CDP: pulsa «Abrir Chrome»)", None)
            return
        try:
            tabs = list_tabs()
        except Exception:
            tabs = []
        for t in tabs:
            self.tab.addItem(f"{t['title'][:70]} — {t['url'][:60]}", t["id"])
        if not tabs:
            self.tab.addItem("(no hay pestañas)", None)
        index = self.tab.findData(previous) if previous else -1
        if index < 0:
            # Por comodidad, preselecciona la primera pestaña de YouTube.
            index = next((i for i in range(self.tab.count())
                          if "youtube.com" in self.tab.itemText(i)), 0)
        self.tab.setCurrentIndex(index)

    def open_chrome(self):
        try:
            ok = launch_chrome()
        except Exception as exc:
            QMessageBox.warning(self, "Chrome", str(exc))
            return
        if not ok:
            QMessageBox.warning(self, "Chrome", "Chrome no respondió en el puerto de depuración.")
        self.refresh_tabs()

    def start_monitoring(self):
        if self.workers:
            return
        mode = self.mode.currentIndex()  # 0 = audio + OCR, 1 = solo audio, 2 = solo OCR
        use_audio = mode in (0, 1)
        use_ocr = mode in (0, 2)
        tab_audio = use_audio and self.tab_audio.isChecked()
        # Solo hace falta conectar con la pestaña para leer pantalla o para su audio.
        need_tab = use_ocr or tab_audio
        target_id = self.tab.currentData()
        if need_tab and not target_id:
            QMessageBox.warning(self, "Pestaña", "Abre Chrome, pulsa «Actualizar» y elige la pestaña del LIVE.")
            return
        self.registry = CodeRegistry()
        self._last_feed = {}
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.bus.status.emit("iniciando motores…")
        self.workers = []
        if need_tab:
            self.browser = TabWorker(target_id, self.interval.value(), capture_audio=tab_audio, capture_frames=use_ocr)
            self.browser.status.connect(self.set_status)
            self.workers.append(self.browser)
        if use_audio:
            self.speech = SpeechWorker(self.gpu.isChecked(), self.bus)
            self.speech.transcript.connect(self.handle_text)
            self.workers.append(self.speech)
            if tab_audio:
                self.browser.audio_chunk.connect(self.speech.submit_audio)
            else:
                self.audio = AudioWorker()
                self.audio.audio_chunk.connect(self.speech.submit_audio)
                self.workers.append(self.audio)
        if use_ocr:
            self.ocr = OCRWorker(self.bus)
            self.ocr.text_found.connect(self.handle_text)
            self.browser.frame.connect(self.ocr.submit_frame)
            self.workers.append(self.ocr)
        for worker in self.workers:
            worker.start()
        self.bus.status.emit("monitoreando")

    def stop_monitoring(self):
        for worker in self.workers:
            worker.stop()
        for worker in self.workers:
            worker.wait(3000)
        self.workers = []
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bus.status.emit("detenido")

    def handle_text(self, text, source):
        self.bus.text.emit(source, text)
        for code, confidence in extract_codes(text, source):
            if self.registry.add(code):
                self.bus.code.emit(code, source, confidence)

    def add_transcript(self, source, text):
        # El OCR repite el mismo texto en cada captura: solo se muestra cuando cambia.
        if self._last_feed.get(source) == text:
            return
        self._last_feed[source] = text
        self.feed.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {source}: {text}")

    def add_code(self, code, source, confidence):
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [datetime.now().strftime("%H:%M:%S"), code, source, f"{confidence:.0%}"]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))
        # Deja el código nuevo seleccionado (y como fila actual) para pulsar «Copiar» directamente.
        self.table.setCurrentCell(row, 1)
        self.table.selectRow(row)
        self.table.scrollToBottom()
        self.status.setText("Estado: ¡código detectado!")
        self.status.setStyleSheet("font-weight:700;color:#22c55e")
        try:
            QApplication.beep()
        except Exception:
            pass
        self.log.setText("Código detectado y seleccionado. Pulsa «Copiar seleccionado» o «Abrir canje oficial».")

    def selected_code(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.text() if item else None

    def copy_selected(self):
        code = self.selected_code()
        if not code:
            QMessageBox.information(self, "Código", "Selecciona un código de la lista.")
            return
        QApplication.clipboard().setText(code)
        self.set_status(f"código copiado al portapapeles ({code})")

    def open_redeem(self):
        code = self.selected_code()
        if not code:
            QMessageBox.information(self, "Canje", "Selecciona primero un código.")
            return
        QApplication.clipboard().setText(code)
        if self.redeemer is not None and self.redeemer.isRunning():
            self.redeemer.stop()
            self.redeemer.wait(3000)
        # Playwright abre la tienda en Chrome y escribe el código; nunca pulsa «Canjear».
        self.redeemer = RedeemWorker(code)
        self.redeemer.status.connect(self.set_status)
        self.redeemer.start()
        self.log.setText("Canje en curso: el código también está en el portapapeles. "
                         "Cuando se escriba en el campo, revisa región/cuenta y confirma tú el canje.")

    def closeEvent(self, event):
        if self.workers:
            self.stop_monitoring()
        if self.redeemer is not None and self.redeemer.isRunning():
            self.redeemer.stop()
            self.redeemer.wait(3000)
        event.accept()
