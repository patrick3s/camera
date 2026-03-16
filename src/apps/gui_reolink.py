"""
gui_reolink.py — Interface gráfica completa para câmera Reolink E1 Pro

Funcionalidades:
  - Vídeo ao vivo (RTSP sub-stream)
  - Controle PTZ (8 direções + zoom)
  - IR (infravermelho) on/off
  - Spotlight (WhiteLED) on/off com slider de brilho
  - Alarme de áudio on/off
  - Auto Track on/off
  - Snapshot (salva JPG)
  - Áudio da câmera (via ffplay)
  - Talkback (enviar áudio via microfone)
  - Seletor de microfone (lista dispositivos de entrada)
  - Indicadores de status em tempo real
  - Atalhos de teclado (WASD, +/-, espaço, etc.)

Uso:
    python gui_reolink.py
"""

import sys
import os
import cv2
import time
import asyncio
import subprocess
import threading
import logging
import socket
import sounddevice as sd
from datetime import datetime
from functools import partial

from dotenv import load_dotenv
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGridLayout, QSlider, QGroupBox, QFrame,
    QSizePolicy, QToolTip, QComboBox,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QSize
from PyQt6.QtGui import QImage, QPixmap, QFont, QKeyEvent, QShortcut, QKeySequence

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gui_reolink")

# ── Configurações ──
REOLINK_IP = os.getenv("REOLINK_IP", "192.168.1.84")
REOLINK_USER = os.getenv("REOLINK_USER", "admin")
REOLINK_PASS = os.getenv("REOLINK_PASS", "")
REOLINK_PORT = int(os.getenv("REOLINK_PORT", "80"))
CHANNEL = 0

RTSP_URL_SUB = f"rtsp://{REOLINK_USER}:{REOLINK_PASS}@{REOLINK_IP}:554//h264Preview_01_sub"
RTSP_URL_MAIN = f"rtsp://{REOLINK_USER}:{REOLINK_PASS}@{REOLINK_IP}:554//h264Preview_01_main"

# ── Estilo Global ──
DARK_BG = "#0d1117"
PANEL_BG = "#161b22"
CARD_BG = "#21262d"
ACCENT = "#58a6ff"
ACCENT_HOVER = "#79c0ff"
GREEN = "#3fb950"
RED = "#f85149"
ORANGE = "#d29922"
TEXT = "#e6edf3"
TEXT_DIM = "#8b949e"
BORDER = "#30363d"


# ============================================================
#  Thread de Vídeo
# ============================================================
class VideoThread(QThread):
    frame_signal = pyqtSignal(QImage)
    fps_signal = pyqtSignal(float)
    status_signal = pyqtSignal(str)

    def __init__(self, rtsp_url):
        super().__init__()
        self._running = True
        self._rtsp_url = rtsp_url

    def run(self):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        cap = None
        reconnect_delay = 2
        fps_time = time.time()
        frame_count = 0

        while self._running:
            if cap is None or not cap.isOpened():
                self.status_signal.emit("Conectando ao stream...")
                cap = cv2.VideoCapture(self._rtsp_url, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    self.status_signal.emit(f"Falha na conexão. Tentando em {reconnect_delay}s...")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 10)
                    continue
                reconnect_delay = 2
                self.status_signal.emit("Stream conectado")

            ret, frame = cap.read()
            if not ret:
                self.status_signal.emit("Frame perdido, reconectando...")
                cap.release()
                cap = None
                time.sleep(1)
                continue

            # FPS
            frame_count += 1
            elapsed = time.time() - fps_time
            if elapsed >= 1.0:
                self.fps_signal.emit(frame_count / elapsed)
                frame_count = 0
                fps_time = time.time()

            # Timestamp OSD
            ts = datetime.now().strftime("%H:%M:%S")
            cv2.putText(frame, ts, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 1, cv2.LINE_AA)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.frame_signal.emit(img)

        if cap:
            cap.release()

    def stop(self):
        self._running = False
        self.wait(3000)


# ============================================================
#  Thread Async (para reolink_aio)
# ============================================================
class AsyncWorker(QThread):
    """Executa uma coroutine em thread separada e emite o resultado."""
    result_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, coro_func, *args, **kwargs):
        super().__init__()
        self._coro_func = coro_func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._coro_func(*self._args, **self._kwargs))
            self.result_signal.emit(result)
            loop.close()
        except Exception as e:
            self.error_signal.emit(str(e))


# ============================================================
#  Funções Async de controle da câmera
# ============================================================
async def _get_host():
    from reolink_aio.api import Host
    host = Host(host=REOLINK_IP, username=REOLINK_USER, password=REOLINK_PASS, port=REOLINK_PORT)
    await host.get_host_data()
    return host


async def async_ptz(command):
    host = await _get_host()
    try:
        await host.set_ptz_command(CHANNEL, command=command)
    finally:
        await host.logout()
    return f"PTZ: {command}"


async def async_set_ir(enabled):
    host = await _get_host()
    try:
        await host.set_ir_lights(CHANNEL, enabled)
    finally:
        await host.logout()
    return enabled


async def async_set_spotlight(enabled, brightness=None):
    host = await _get_host()
    try:
        if brightness is not None:
            await host.set_whiteled(CHANNEL, state=enabled, brightness=brightness)
        else:
            await host.set_whiteled(CHANNEL, state=enabled)
    finally:
        await host.logout()
    return enabled


async def async_set_audio_alarm(enabled):
    host = await _get_host()
    try:
        await host.set_audio_alarm(CHANNEL, enabled)
    finally:
        await host.logout()
    return enabled


async def async_set_auto_track(enabled):
    host = await _get_host()
    try:
        await host.set_auto_tracking(CHANNEL, enabled)
    finally:
        await host.logout()
    return enabled


async def async_snapshot():
    host = await _get_host()
    try:
        img = await host.get_snapshot(CHANNEL)
        if img:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reolink_snap_{ts}.jpg"
            with open(filename, "wb") as f:
                f.write(img)
            return os.path.abspath(filename)
    finally:
        await host.logout()
    return None


async def async_get_states():
    host = await _get_host()
    try:
        states = {}
        try:
            states["ir"] = host.ir_enabled(CHANNEL)
        except Exception:
            states["ir"] = None
        try:
            states["spotlight"] = host.whiteled_state(CHANNEL)
        except Exception:
            states["spotlight"] = None
        try:
            states["brightness"] = host.whiteled_brightness(CHANNEL)
        except Exception:
            states["brightness"] = 85
        try:
            states["auto_track"] = host.auto_track_enabled(CHANNEL)
        except Exception:
            states["auto_track"] = None
        try:
            states["daynight"] = host.daynight_state(CHANNEL)
        except Exception:
            states["daynight"] = "N/A"
        try:
            states["model"] = host.model
        except Exception:
            states["model"] = "Reolink"
        try:
            states["name"] = host.nvr_name
        except Exception:
            states["name"] = "Camera"
        return states
    finally:
        await host.logout()


# ============================================================
#  GUI Principal
# ============================================================
class ReolinkGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SOGRO — Reolink {REOLINK_IP}")
        self.setMinimumSize(1100, 700)
        self._workers = []  # manter referência para GC
        self._ffplay_proc = None
        self._talk_proc = None
        self._talk_running = False
        self._talk_http_thread = None
        self._selected_mic_index = None  # None = default do sistema

        # Estados
        self._ir_on = False
        self._spot_on = False
        self._alarm_on = False
        self._track_on = False
        self._fps = 0.0

        self._build_ui()
        self._setup_shortcuts()
        self._start_video()
        self._load_states()

    # ── Construir Interface ──
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background: {DARK_BG};")

        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Painel Esquerdo: Vídeo ──
        video_frame = QFrame()
        video_frame.setStyleSheet(f"""
            QFrame {{
                background: #000;
                border: 2px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        video_layout = QVBoxLayout(video_frame)
        video_layout.setContentsMargins(2, 2, 2, 2)

        self.video_label = QLabel("Conectando à câmera...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 14px; border: none;")
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        video_layout.addWidget(self.video_label)

        # Barra inferior do vídeo
        bottom_bar = QHBoxLayout()
        self.lbl_cam_info = QLabel(f"Reolink · {REOLINK_IP}")
        self.lbl_cam_info.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; border: none;")
        self.lbl_fps = QLabel("0 FPS")
        self.lbl_fps.setStyleSheet(f"color: {GREEN}; font-size: 11px; font-weight: bold; border: none;")
        self.lbl_stream_status = QLabel("●")
        self.lbl_stream_status.setStyleSheet(f"color: {ORANGE}; font-size: 14px; border: none;")
        bottom_bar.addWidget(self.lbl_stream_status)
        bottom_bar.addWidget(self.lbl_cam_info)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.lbl_fps)
        video_layout.addLayout(bottom_bar)

        root.addWidget(video_frame, stretch=3)

        # ── Painel Direito: Controles ──
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        # Título
        title = QLabel("🎥 Reolink E1 Pro")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {ACCENT}; font-size: 18px; font-weight: bold;")
        right_panel.addWidget(title)

        self.lbl_cam_name = QLabel("Carregando...")
        self.lbl_cam_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cam_name.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        right_panel.addWidget(self.lbl_cam_name)

        # ── Grupo PTZ ──
        ptz_group = self._make_group("Controle PTZ")
        ptz_inner = QVBoxLayout()

        ptz_grid = QGridLayout()
        ptz_grid.setSpacing(4)
        directions = [
            ("↖", 0, 0, "LeftUp"),   ("↑", 0, 1, "Up"),    ("↗", 0, 2, "RightUp"),
            ("←", 1, 0, "Left"),      ("⏹", 1, 1, "Stop"),  ("→", 1, 2, "Right"),
            ("↙", 2, 0, "LeftDown"),  ("↓", 2, 1, "Down"),  ("↘", 2, 2, "RightDown"),
        ]
        for label, row, col, cmd in directions:
            btn = QPushButton(label)
            btn.setFixedSize(52, 52)
            is_stop = cmd == "Stop"
            bg = RED if is_stop else CARD_BG
            btn.setStyleSheet(self._btn_style(bg))
            btn.pressed.connect(partial(self._ptz, cmd))
            if not is_stop:
                btn.released.connect(partial(self._ptz, "Stop"))
            ptz_grid.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        ptz_inner.addLayout(ptz_grid)

        # Zoom
        zoom_row = QHBoxLayout()
        for label, cmd in [("🔍−  Zoom Out", "ZoomDec"), ("🔍+  Zoom In", "ZoomInc")]:
            btn = QPushButton(label)
            btn.setFixedHeight(36)
            btn.setStyleSheet(self._btn_style(CARD_BG))
            btn.pressed.connect(partial(self._ptz, cmd))
            btn.released.connect(partial(self._ptz, "Stop"))
            zoom_row.addWidget(btn)
        ptz_inner.addLayout(zoom_row)

        ptz_group.layout().addLayout(ptz_inner)
        right_panel.addWidget(ptz_group)

        # ── Grupo Funcionalidades ──
        feat_group = self._make_group("Funcionalidades")
        feat_layout = QGridLayout()
        feat_layout.setSpacing(6)

        # IR
        self.btn_ir = QPushButton("💡 IR")
        self.btn_ir.setCheckable(True)
        self.btn_ir.setFixedHeight(40)
        self.btn_ir.setStyleSheet(self._toggle_style(False))
        self.btn_ir.clicked.connect(self._toggle_ir)
        feat_layout.addWidget(self.btn_ir, 0, 0)

        # Spotlight
        self.btn_spot = QPushButton("🔦 Spotlight")
        self.btn_spot.setCheckable(True)
        self.btn_spot.setFixedHeight(40)
        self.btn_spot.setStyleSheet(self._toggle_style(False))
        self.btn_spot.clicked.connect(self._toggle_spotlight)
        feat_layout.addWidget(self.btn_spot, 0, 1)

        # Alarme
        self.btn_alarm = QPushButton("🔊 Alarme")
        self.btn_alarm.setCheckable(True)
        self.btn_alarm.setFixedHeight(40)
        self.btn_alarm.setStyleSheet(self._toggle_style(False, RED))
        self.btn_alarm.clicked.connect(self._toggle_alarm)
        feat_layout.addWidget(self.btn_alarm, 1, 0)

        # Auto Track
        self.btn_track = QPushButton("🎯 Auto Track")
        self.btn_track.setCheckable(True)
        self.btn_track.setFixedHeight(40)
        self.btn_track.setStyleSheet(self._toggle_style(False))
        self.btn_track.clicked.connect(self._toggle_track)
        feat_layout.addWidget(self.btn_track, 1, 1)

        # Snapshot
        btn_snap = QPushButton("📸 Snapshot")
        btn_snap.setFixedHeight(40)
        btn_snap.setStyleSheet(self._btn_style(CARD_BG))
        btn_snap.clicked.connect(self._take_snapshot)
        feat_layout.addWidget(btn_snap, 2, 0)

        # Ouvir
        self.btn_listen = QPushButton("🔊 Ouvir Áudio")
        self.btn_listen.setCheckable(True)
        self.btn_listen.setFixedHeight(40)
        self.btn_listen.setStyleSheet(self._toggle_style(False))
        self.btn_listen.clicked.connect(self._toggle_listen)
        feat_layout.addWidget(self.btn_listen, 2, 1)

        # Falar (Talkback) — 🎤
        self.btn_talk = QPushButton("🎤 Falar")
        self.btn_talk.setCheckable(True)
        self.btn_talk.setFixedHeight(40)
        self.btn_talk.setStyleSheet(self._toggle_style(False, ORANGE))
        self.btn_talk.clicked.connect(self._toggle_talk)
        feat_layout.addWidget(self.btn_talk, 3, 0)

        # Volume Speaker
        self.btn_volume = QPushButton("🔈 Volume: 90%")
        self.btn_volume.setFixedHeight(40)
        self.btn_volume.setStyleSheet(self._btn_style(CARD_BG))
        self.btn_volume.setEnabled(False)
        feat_layout.addWidget(self.btn_volume, 3, 1)

        feat_group.layout().addLayout(feat_layout)

        # ── Seletor de Microfone ──
        mic_row = QHBoxLayout()
        mic_lbl = QLabel("🎙️ Microfone:")
        mic_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        self.combo_mic = QComboBox()
        self.combo_mic.setFixedHeight(32)
        self.combo_mic.setStyleSheet(f"""
            QComboBox {{
                background: {CARD_BG}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 4px 8px; font-size: 11px;
            }}
            QComboBox::drop-down {{
                border: none; width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none; border-left: 4px solid transparent;
                border-right: 4px solid transparent; border-top: 6px solid {TEXT_DIM};
            }}
            QComboBox QAbstractItemView {{
                background: {PANEL_BG}; color: {TEXT}; border: 1px solid {BORDER};
                selection-background-color: {ACCENT}; font-size: 11px;
            }}
        """)
        self.combo_mic.currentIndexChanged.connect(self._on_mic_changed)
        self._populate_mics()
        btn_refresh_mic = QPushButton("🔄")
        btn_refresh_mic.setFixedSize(32, 32)
        btn_refresh_mic.setToolTip("Atualizar lista de microfones")
        btn_refresh_mic.setStyleSheet(self._btn_style(CARD_BG))
        btn_refresh_mic.clicked.connect(self._populate_mics)
        mic_row.addWidget(mic_lbl)
        mic_row.addWidget(self.combo_mic, stretch=1)
        mic_row.addWidget(btn_refresh_mic)
        feat_group.layout().addLayout(mic_row)

        # Slider de brilho
        bright_row = QHBoxLayout()
        bright_lbl = QLabel("Brilho LED:")
        bright_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        self.slider_brightness = QSlider(Qt.Orientation.Horizontal)
        self.slider_brightness.setRange(0, 100)
        self.slider_brightness.setValue(85)
        self.slider_brightness.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BORDER}; height: 6px; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT}; width: 14px; margin: -4px 0; border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
        """)
        self.lbl_bright_val = QLabel("85%")
        self.lbl_bright_val.setStyleSheet(f"color: {TEXT}; font-size: 11px; min-width: 30px;")
        self.slider_brightness.valueChanged.connect(lambda v: self.lbl_bright_val.setText(f"{v}%"))
        bright_row.addWidget(bright_lbl)
        bright_row.addWidget(self.slider_brightness)
        bright_row.addWidget(self.lbl_bright_val)
        feat_group.layout().addLayout(bright_row)

        right_panel.addWidget(feat_group)

        # ── Status Bar ──
        self.status_label = QLabel("Iniciando...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {GREEN}; background: {CARD_BG}; padding: 8px;
            border-radius: 6px; font-size: 12px;
        """)
        right_panel.addWidget(self.status_label)

        # ── Atalhos ──
        shortcuts_lbl = QLabel("Atalhos: W/A/S/D = PTZ · +/- = Zoom · I = IR · L = Spotlight · P = Snap · T = Falar")
        shortcuts_lbl.setWordWrap(True)
        shortcuts_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcuts_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        right_panel.addWidget(shortcuts_lbl)

        right_panel.addStretch()
        root.addLayout(right_panel, stretch=1)

    # ── Microfone ──
    def _populate_mics(self):
        """Preenche o combo com dispositivos de entrada de áudio (microfones)."""
        self.combo_mic.blockSignals(True)
        self.combo_mic.clear()
        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0]  # índice padrão de entrada
            selected_idx = 0
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    name = dev["name"]
                    label = f"[{i}] {name}"
                    if i == default_input:
                        label += "  ⭐"
                    self.combo_mic.addItem(label, userData=i)
                    # Se já tínhamos um mic selecionado, restaurar
                    if self._selected_mic_index is not None and i == self._selected_mic_index:
                        selected_idx = self.combo_mic.count() - 1
                    elif self._selected_mic_index is None and i == default_input:
                        selected_idx = self.combo_mic.count() - 1
            if self.combo_mic.count() > 0:
                self.combo_mic.setCurrentIndex(selected_idx)
                self._selected_mic_index = self.combo_mic.itemData(selected_idx)
        except Exception as e:
            self.combo_mic.addItem(f"Erro: {e}", userData=None)
            log.error(f"Erro ao listar microfones: {e}")
        self.combo_mic.blockSignals(False)

    def _on_mic_changed(self, index):
        """Atualiza o microfone selecionado quando o combo muda."""
        if index >= 0:
            mic_idx = self.combo_mic.itemData(index)
            self._selected_mic_index = mic_idx
            mic_name = self.combo_mic.currentText()
            log.info(f"Microfone selecionado: {mic_name} (index={mic_idx})")
            self._set_status(f"🎙️ Mic: {mic_name}")

    # ── Helpers de estilo ──
    def _make_group(self, title):
        g = QGroupBox(title)
        g.setStyleSheet(f"""
            QGroupBox {{
                color: {TEXT}; font-weight: bold; font-size: 13px;
                border: 1px solid {BORDER}; border-radius: 8px;
                margin-top: 8px; padding-top: 16px;
                background: {PANEL_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 12px; padding: 0 4px;
            }}
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        g.setLayout(layout)
        return g

    @staticmethod
    def _btn_style(bg=CARD_BG):
        return f"""
            QPushButton {{
                background: {bg}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; font-size: 13px; font-weight: bold; padding: 4px;
            }}
            QPushButton:hover {{ background: {ACCENT}; color: #000; }}
            QPushButton:pressed {{ background: {ACCENT_HOVER}; }}
        """

    @staticmethod
    def _toggle_style(active, color=ACCENT):
        if active:
            return f"""
                QPushButton {{
                    background: {color}; color: #000; border: 1px solid {color};
                    border-radius: 6px; font-size: 12px; font-weight: bold; padding: 4px;
                }}
                QPushButton:hover {{ background: {color}; }}
            """
        else:
            return f"""
                QPushButton {{
                    background: {CARD_BG}; color: {TEXT}; border: 1px solid {BORDER};
                    border-radius: 6px; font-size: 12px; font-weight: bold; padding: 4px;
                }}
                QPushButton:hover {{ background: {BORDER}; }}
            """

    # ── Atalhos de teclado ──
    def _setup_shortcuts(self):
        shortcuts = {
            "W": lambda: self._ptz_tap("Up"),
            "S": lambda: self._ptz_tap("Down"),
            "A": lambda: self._ptz_tap("Left"),
            "D": lambda: self._ptz_tap("Right"),
            "+": lambda: self._ptz_tap("ZoomInc"),
            "=": lambda: self._ptz_tap("ZoomInc"),
            "-": lambda: self._ptz_tap("ZoomDec"),
            "I": self._toggle_ir,
            "L": self._toggle_spotlight,
            "P": self._take_snapshot,
            "T": self._toggle_talk,
            "Space": lambda: self._ptz("Stop"),
        }
        for key, func in shortcuts.items():
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(func)

    def _ptz_tap(self, cmd, duration=0.4):
        """PTZ com duração curta para atalhos de teclado."""
        def _do():
            self._run_async(async_ptz, cmd)
            QTimer.singleShot(int(duration * 1000), lambda: self._run_async(async_ptz, "Stop"))
        _do()

    # ── Inicialização ──
    def _start_video(self):
        self.video_thread = VideoThread(RTSP_URL_SUB)
        self.video_thread.frame_signal.connect(self._update_frame)
        self.video_thread.fps_signal.connect(self._update_fps)
        self.video_thread.status_signal.connect(self._update_stream_status)
        self.video_thread.start()

    def _load_states(self):
        """Carrega estados atuais da câmera."""
        self._run_async(async_get_states, callback=self._apply_states)

    def _apply_states(self, states):
        if not isinstance(states, dict):
            return
        self._ir_on = states.get("ir", False) or False
        self._spot_on = states.get("spotlight", False) or False
        brightness = states.get("brightness", 85) or 85

        self.btn_ir.setChecked(self._ir_on)
        self.btn_ir.setStyleSheet(self._toggle_style(self._ir_on))
        self.btn_ir.setText(f"💡 IR {'ON' if self._ir_on else 'OFF'}")

        self.btn_spot.setChecked(self._spot_on)
        self.btn_spot.setStyleSheet(self._toggle_style(self._spot_on))
        self.btn_spot.setText(f"🔦 Spot {'ON' if self._spot_on else 'OFF'}")

        self.slider_brightness.setValue(brightness)

        model = states.get("model", "Reolink")
        name = states.get("name", "Camera")
        daynight = states.get("daynight", "")
        self.lbl_cam_name.setText(f"{name} · {model} · {daynight}")

        self._set_status(f"Conectado — {model} ({name})")

    # ── Video callbacks ──
    def _update_frame(self, img: QImage):
        scaled = img.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(QPixmap.fromImage(scaled))

    def _update_fps(self, fps):
        self._fps = fps
        self.lbl_fps.setText(f"{fps:.0f} FPS")

    def _update_stream_status(self, msg):
        if "conectado" in msg.lower():
            self.lbl_stream_status.setStyleSheet(f"color: {GREEN}; font-size: 14px; border: none;")
        else:
            self.lbl_stream_status.setStyleSheet(f"color: {ORANGE}; font-size: 14px; border: none;")
        log.info(msg)

    # ── Async helper ──
    def _run_async(self, coro_func, *args, callback=None, err_callback=None):
        worker = AsyncWorker(coro_func, *args)
        if callback:
            worker.result_signal.connect(callback)
        else:
            worker.result_signal.connect(lambda r: log.info(f"OK: {r}"))
        worker.error_signal.connect(err_callback or (lambda e: self._set_status(f"❌ {e}")))
        self._workers.append(worker)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        worker.start()

    # ── PTZ ──
    def _ptz(self, command):
        self._set_status(f"PTZ: {command}")
        self._run_async(async_ptz, command)

    # ── Toggles ──
    def _toggle_ir(self):
        self._ir_on = not self._ir_on
        self.btn_ir.setChecked(self._ir_on)
        self.btn_ir.setStyleSheet(self._toggle_style(self._ir_on))
        self.btn_ir.setText(f"💡 IR {'ON' if self._ir_on else 'OFF'}")
        self._set_status(f"IR: {'Ligando' if self._ir_on else 'Desligando'}...")
        self._run_async(async_set_ir, self._ir_on,
                        callback=lambda _: self._set_status(f"IR {'LIGADO' if self._ir_on else 'DESLIGADO'}"))

    def _toggle_spotlight(self):
        self._spot_on = not self._spot_on
        self.btn_spot.setChecked(self._spot_on)
        self.btn_spot.setStyleSheet(self._toggle_style(self._spot_on))
        self.btn_spot.setText(f"🔦 Spot {'ON' if self._spot_on else 'OFF'}")
        bright = self.slider_brightness.value()
        self._set_status(f"Spotlight: {'Ligando' if self._spot_on else 'Desligando'}...")
        self._run_async(async_set_spotlight, self._spot_on, bright,
                        callback=lambda _: self._set_status(
                            f"Spotlight {'LIGADO (brilho {bright}%)' if self._spot_on else 'DESLIGADO'}"))

    def _toggle_alarm(self):
        self._alarm_on = not self._alarm_on
        self.btn_alarm.setChecked(self._alarm_on)
        self.btn_alarm.setStyleSheet(self._toggle_style(self._alarm_on, RED))
        self.btn_alarm.setText(f"🔊 Alarme {'ON' if self._alarm_on else 'OFF'}")
        self._set_status(f"Alarme: {'Ligando' if self._alarm_on else 'Desligando'}...")
        self._run_async(async_set_audio_alarm, self._alarm_on,
                        callback=lambda _: self._set_status(
                            f"Alarme {'LIGADO ⚠️' if self._alarm_on else 'DESLIGADO'}"))

    def _toggle_track(self):
        self._track_on = not self._track_on
        self.btn_track.setChecked(self._track_on)
        self.btn_track.setStyleSheet(self._toggle_style(self._track_on))
        self.btn_track.setText(f"🎯 Track {'ON' if self._track_on else 'OFF'}")
        self._set_status(f"Auto Track: {'Ligando' if self._track_on else 'Desligando'}...")
        self._run_async(async_set_auto_track, self._track_on,
                        callback=lambda _: self._set_status(
                            f"Auto Track {'LIGADO' if self._track_on else 'DESLIGADO'}"))

    def _take_snapshot(self):
        self._set_status("Capturando snapshot...")
        self._run_async(async_snapshot,
                        callback=lambda path: self._set_status(f"📸 Salvo: {path}" if path else "Falha no snapshot"))

    def _toggle_listen(self):
        if self.btn_listen.isChecked():
            self.btn_listen.setStyleSheet(self._toggle_style(True))
            self.btn_listen.setText("🔊 Ouvindo...")
            self._set_status("Áudio: Iniciando...")
            try:
                rtsp = f"rtsp://{REOLINK_USER}:{REOLINK_PASS}@{REOLINK_IP}:554//h264Preview_01_main"
                self._ffplay_proc = subprocess.Popen(
                    ["ffplay", "-nodisp", "-vn", "-fflags", "nobuffer",
                     "-flags", "low_delay", "-rtsp_transport", "tcp", rtsp],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._set_status("🔊 Áudio ativo")
            except FileNotFoundError:
                self._set_status("❌ ffplay não encontrado (instale ffmpeg)")
                self.btn_listen.setChecked(False)
                self.btn_listen.setStyleSheet(self._toggle_style(False))
                self.btn_listen.setText("🔊 Ouvir Áudio")
        else:
            self.btn_listen.setStyleSheet(self._toggle_style(False))
            self.btn_listen.setText("🔊 Ouvir Áudio")
            if self._ffplay_proc:
                self._ffplay_proc.terminate()
                self._ffplay_proc = None
            self._set_status("Áudio desligado")

    def _toggle_talk(self):
        """Liga/desliga talkback — envia áudio do microfone para o alto-falante da câmera.

        Usa RTSP backchannel (track3 sendonly PCMU/8000) descoberto no SDP da Reolink E1 Pro.
        O fluxo é:
         1. DESCRIBE → obtém SDP com track3 (a=sendonly, PCMU/8000)
         2. SETUP track3 com Transport: RTP/AVP/TCP;interleaved=0-1;mode=record
         3. PLAY
         4. Envia RTP packets com áudio PCMU capturado do microfone
        """
        if self.btn_talk.isChecked():
            self.btn_talk.setStyleSheet(self._toggle_style(True, ORANGE))
            self.btn_talk.setText("🎤 Falando...")
            self._set_status("🎤 Talkback: Iniciando microfone...")
            self._talk_running = True
            mic_device = self._selected_mic_index

            def _talk_rtsp_thread():
                import hashlib
                import re
                import struct
                import audioop

                sock = None
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    sock.connect((REOLINK_IP, 554))

                    rtsp_url = f"rtsp://{REOLINK_IP}:554/Preview_01_main"
                    cseq = 0
                    session_id = None
                    auth_nonce = None
                    auth_realm = None

                    def _make_auth(method, uri):
                        ha1 = hashlib.md5(f"{REOLINK_USER}:{auth_realm}:{REOLINK_PASS}".encode()).hexdigest()
                        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
                        resp = hashlib.md5(f"{ha1}:{auth_nonce}:{ha2}".encode()).hexdigest()
                        return f'Digest username="{REOLINK_USER}", realm="{auth_realm}", nonce="{auth_nonce}", uri="{uri}", response="{resp}"'

                    def _send(method, uri, extra_headers=None):
                        nonlocal cseq, session_id, auth_nonce, auth_realm
                        cseq += 1
                        lines = [f"{method} {uri} RTSP/1.0", f"CSeq: {cseq}"]
                        if session_id:
                            lines.append(f"Session: {session_id}")
                        if auth_nonce and auth_realm:
                            lines.append(f"Authorization: {_make_auth(method, uri)}")
                        if extra_headers:
                            lines.extend(extra_headers)
                        lines.append("")
                        lines.append("")
                        sock.sendall("\r\n".join(lines).encode())

                        # Ler resposta
                        resp = b""
                        while True:
                            try:
                                chunk = sock.recv(4096)
                            except socket.timeout:
                                break
                            if not chunk:
                                break
                            resp += chunk
                            if b"\r\n\r\n" in resp:
                                m = re.search(rb'Content-Length:\s*(\d+)', resp)
                                if m:
                                    cl = int(m.group(1))
                                    he = resp.index(b"\r\n\r\n") + 4
                                    while len(resp) < he + cl:
                                        try:
                                            resp += sock.recv(4096)
                                        except socket.timeout:
                                            break
                                break

                        resp_str = resp.decode('utf-8', errors='replace')

                        # Parse auth
                        m = re.search(r'WWW-Authenticate:\s*Digest\s+realm="([^"]+)".*nonce="([^"]+)"', resp_str)
                        if m:
                            auth_realm = m.group(1)
                            auth_nonce = m.group(2)

                        # Parse session
                        m = re.search(r'Session:\s*(\S+)', resp_str)
                        if m:
                            session_id = m.group(1).split(';')[0]

                        return resp_str

                    # 1. OPTIONS
                    _send("OPTIONS", rtsp_url)

                    # 2. DESCRIBE (com Require backchannel)
                    resp = _send("DESCRIBE", rtsp_url, [
                        "Accept: application/sdp",
                        "Require: www.onvif.org/ver20/backchannel",
                    ])
                    if "401" in resp.split('\r\n')[0]:
                        resp = _send("DESCRIBE", rtsp_url, [
                            "Accept: application/sdp",
                            "Require: www.onvif.org/ver20/backchannel",
                        ])

                    # Verificar se track3 (backchannel) existe
                    if "sendonly" not in resp:
                        raise RuntimeError("Câmera não expôs backchannel no SDP")

                    # 3. SETUP track3 (backchannel) com TCP interleaved
                    track3_url = f"{rtsp_url}/track3"
                    resp = _send("SETUP", track3_url, [
                        "Transport: RTP/AVP/TCP;unicast;interleaved=0-1;mode=record",
                    ])
                    if "200" not in resp.split('\r\n')[0]:
                        raise RuntimeError(f"SETUP track3 falhou: {resp.split(chr(10))[0]}")

                    # Parse server_port se necessário (para UDP) — não usado em TCP interleaved
                    log.info(f"Talkback RTSP: session={session_id}")

                    # 4. PLAY
                    resp = _send("PLAY", rtsp_url, ["Range: npt=0.000-"])
                    if "200" not in resp.split('\r\n')[0]:
                        raise RuntimeError(f"PLAY falhou: {resp.split(chr(10))[0]}")

                    log.info("Talkback RTSP: backchannel ativo, enviando áudio...")
                    from PyQt6.QtCore import QMetaObject, Qt as QtConst, Q_ARG
                    # Atualizar status na thread principal
                    QMetaObject.invokeMethod(
                        self.status_label, "setText",
                        QtConst.ConnectionType.QueuedConnection,
                        Q_ARG(str, "🎤 Talkback ativo — fale no microfone!"),
                    )

                    # Thread para drenar dados recebidos (vídeo/áudio interleaved da câmera)
                    # Sem isso, o buffer TCP enche e bloqueia o envio.
                    sock.settimeout(0.05)

                    def _drain():
                        while self._talk_running:
                            try:
                                sock.recv(65536)
                            except socket.timeout:
                                pass
                            except Exception:
                                break

                    drain_t = threading.Thread(target=_drain, daemon=True)
                    drain_t.start()

                    # 5. Capturar áudio do mic e enviar como RTP/PCMU via TCP interleaved
                    sample_rate = 8000
                    block_size = 160  # 20ms de áudio a 8kHz (padrão RTP)
                    seq = 0
                    timestamp = 0
                    ssrc = 0x12345678

                    with sd.InputStream(samplerate=sample_rate, channels=1,
                                        dtype='int16', blocksize=block_size,
                                        device=mic_device) as stream:
                        while self._talk_running:
                            data, _ = stream.read(block_size)
                            pcm_bytes = data.tobytes()

                            # Converter PCM linear para mu-law (PCMU)
                            mulaw_bytes = audioop.lin2ulaw(pcm_bytes, 2)

                            # Construir pacote RTP
                            # RTP Header: V=2, P=0, X=0, CC=0, M=0, PT=0 (PCMU)
                            rtp_header = struct.pack('>BBHII',
                                0x80,            # V=2, P=0, X=0, CC=0
                                0,               # M=0, PT=0 (PCMU)
                                seq & 0xFFFF,    # sequence number
                                timestamp,       # timestamp
                                ssrc,            # SSRC
                            )
                            rtp_packet = rtp_header + mulaw_bytes
                            seq += 1
                            timestamp += block_size

                            # TCP interleaved framing: $ + channel(1) + length(2) + data
                            frame = struct.pack('>cBH', b'$', 0, len(rtp_packet)) + rtp_packet
                            try:
                                sock.sendall(frame)
                            except (BrokenPipeError, ConnectionResetError):
                                log.warning("Talkback: conexão perdida")
                                break

                except Exception as e:
                    log.error(f"Talkback RTSP erro: {e}")
                    from PyQt6.QtCore import QMetaObject, Qt as QtConst, Q_ARG
                    QMetaObject.invokeMethod(
                        self.status_label, "setText",
                        QtConst.ConnectionType.QueuedConnection,
                        Q_ARG(str, f"❌ Talkback erro: {e}"),
                    )
                finally:
                    if sock:
                        try:
                            # TEARDOWN
                            cseq += 1
                            teardown = f"TEARDOWN {rtsp_url} RTSP/1.0\r\nCSeq: {cseq}\r\n"
                            if session_id:
                                teardown += f"Session: {session_id}\r\n"
                            teardown += "\r\n"
                            sock.sendall(teardown.encode())
                        except Exception:
                            pass
                        sock.close()
                    self._talk_running = False

            self._talk_http_thread = threading.Thread(target=_talk_rtsp_thread, daemon=True)
            self._talk_http_thread.start()
        else:
            self._stop_talk()

    def _stop_talk(self):
        """Para o talkback."""
        self.btn_talk.setStyleSheet(self._toggle_style(False, ORANGE))
        self.btn_talk.setText("🎤 Falar")

        # Para ffmpeg
        if self._talk_proc:
            try:
                self._talk_proc.terminate()
                self._talk_proc.wait(timeout=3)
            except Exception:
                try:
                    self._talk_proc.kill()
                except Exception:
                    pass
            self._talk_proc = None

        # Para HTTP talk
        self._talk_running = False

        self._set_status("🎤 Talkback desligado")

    # ── Status ──
    def _set_status(self, msg):
        self.status_label.setText(msg)
        log.info(msg)

    # ── Cleanup ──
    def closeEvent(self, event):
        log.info("Encerrando GUI...")
        if self._ffplay_proc:
            self._ffplay_proc.terminate()
        self._talk_running = False
        if self._talk_proc:
            try:
                self._talk_proc.terminate()
            except Exception:
                pass
        self.video_thread.stop()
        # Esperar workers finalizarem
        for w in self._workers:
            w.wait(2000)
        event.accept()


# ============================================================
#  Main
# ============================================================
def main():
    app = QApplication(sys.argv)

    # Estilo global da aplicação
    app.setStyle("Fusion")
    app.setFont(QFont(".AppleSystemUIFont", 11))

    window = ReolinkGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
