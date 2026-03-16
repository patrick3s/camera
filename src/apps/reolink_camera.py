"""
reolink_camera.py — Conecta e controla câmera Reolink

Detectada em: 192.168.1.84
Portas: 80 (HTTP/API), 443 (HTTPS), 554 (RTSP), 8000 (ONVIF), 9000 (Baichuan)

Funcionalidades:
  - Info do dispositivo (modelo, firmware, MAC, etc.)
  - Stream de vídeo ao vivo (RTSP via OpenCV)
  - Controle PTZ (pan, tilt, zoom)
  - IR / Spotlight / Sirene
  - Captura de snapshot

Uso:
    python reolink_camera.py                      # Info + vídeo ao vivo
    python reolink_camera.py --info               # Só informações
    python reolink_camera.py --stream             # Só vídeo ao vivo
    python reolink_camera.py --snapshot           # Captura foto
    python reolink_camera.py --ptz up             # Move câmera
    python reolink_camera.py --ir on              # Liga infravermelho
    python reolink_camera.py --spotlight on       # Liga holofote
    python reolink_camera.py --siren on           # Liga sirene
    python reolink_camera.py --gui                # Interface gráfica
"""

import asyncio
import argparse
import sys
import os
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ── Configurações ──
REOLINK_IP = os.getenv("REOLINK_IP", "192.168.1.84")
REOLINK_USER = os.getenv("REOLINK_USER", "admin")
REOLINK_PASS = os.getenv("REOLINK_PASS", "")
REOLINK_PORT = int(os.getenv("REOLINK_PORT", "80"))
CHANNEL = 0  # Canal padrão (0 = primeira câmera)

SEP = "=" * 55


# ============================================================
#  Funções com reolink_aio (API oficial)
# ============================================================
async def get_host():
    """Cria e conecta ao host Reolink."""
    from reolink_aio.api import Host

    host = Host(
        host=REOLINK_IP,
        username=REOLINK_USER,
        password=REOLINK_PASS,
        port=REOLINK_PORT,
    )
    await host.get_host_data()
    return host


async def show_info():
    """Mostra informações detalhadas do dispositivo."""
    print(f"\n{SEP}")
    print("  INFORMAÇÕES DA CÂMERA REOLINK")
    print(SEP)

    try:
        host = await get_host()

        print(f"  Modelo:       {host.model}")
        print(f"  Nome:         {host.nvr_name}")
        print(f"  Hardware:     {host.hardware_version}")
        print(f"  Firmware:     {host.sw_version}")
        print(f"  MAC:          {host.mac_address}")
        print(f"  Tipo:         {'NVR' if host.is_nvr else 'Câmera IP'}")
        print(f"  Canais:       {host.channels}")
        print(f"  ONVIF:        porta {host.onvif_port}")

        # Capabilities do canal 0
        ch = CHANNEL
        print(f"\n  [Canal {ch}]")

        try:
            print(f"  IR LED:       {'Ligado' if host.ir_enabled(ch) else 'Desligado'}")
        except Exception:
            print(f"  IR LED:       N/A")

        try:
            print(f"  WhiteLED:     {'Ligado' if host.whiteled_state(ch) else 'Desligado'} (brilho: {host.whiteled_brightness(ch)}%)")
        except Exception:
            print(f"  WhiteLED:     N/A")

        try:
            print(f"  Auto Track:   {'Ligado' if host.auto_track_enabled(ch) else 'Desligado'}")
        except Exception:
            print(f"  Auto Track:   N/A")

        try:
            print(f"  Dia/Noite:    {host.daynight_state(ch)}")
        except Exception:
            print(f"  Dia/Noite:    N/A")

        try:
            print(f"  Áudio:        {'Gravando' if host.audio_record(ch) else 'Desligado'}")
        except Exception:
            print(f"  Áudio:        N/A")

        try:
            presets = host.ptz_presets(ch)
            print(f"  PTZ Presets:  {list(presets.values()) if presets else 'Nenhum'}")
        except Exception:
            print(f"  PTZ Presets:  N/A")

        try:
            print(f"  PTZ Pos:      pan={host.ptz_pan_position(ch)}, tilt={host.ptz_tilt_position(ch)}")
        except Exception:
            print(f"  PTZ Pos:      N/A")

        # URLs de stream
        print(f"\n  [Streams]")
        try:
            rtsp_main = f"rtsp://{REOLINK_USER}:{REOLINK_PASS}@{REOLINK_IP}:554//h264Preview_01_main"
            rtsp_sub = f"rtsp://{REOLINK_USER}:{REOLINK_PASS}@{REOLINK_IP}:554//h264Preview_01_sub"
            print(f"  RTSP Main:    rtsp://{REOLINK_USER}:****@{REOLINK_IP}:554//h264Preview_01_main")
            print(f"  RTSP Sub:     rtsp://{REOLINK_USER}:****@{REOLINK_IP}:554//h264Preview_01_sub")
        except Exception:
            pass

        await host.logout()
        print(f"\n{SEP}")
        return True

    except Exception as e:
        print(f"\n  [x] Erro: {e}")
        print(f"\n  Dicas:")
        print(f"  - Verifique se IP ({REOLINK_IP}) está correto")
        print(f"  - Verifique usuário/senha (use --user e --pass)")
        print(f"  - Tente acessar http://{REOLINK_IP} no navegador")
        print(f"{SEP}")
        return False


async def do_ptz(direction, speed=5, duration=1):
    """Executa movimento PTZ."""
    print(f"\n[*] PTZ: {direction} (velocidade={speed}, duração={duration}s)")

    host = await get_host()

    try:
        # Reolink usa set_ptz_command com comandos string
        ptz_cmds = {
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
            "upleft": "LeftUp",
            "upright": "RightUp",
            "downleft": "LeftDown",
            "downright": "RightDown",
            "stop": "Stop",
        }

        if direction == "zoomin":
            await host.set_ptz_command(CHANNEL, command="ZoomInc")
            await asyncio.sleep(duration)
            await host.set_ptz_command(CHANNEL, command="Stop")
            print("  [v] Zoom in")
        elif direction == "zoomout":
            await host.set_ptz_command(CHANNEL, command="ZoomDec")
            await asyncio.sleep(duration)
            await host.set_ptz_command(CHANNEL, command="Stop")
            print("  [v] Zoom out")
        elif direction in ptz_cmds:
            cmd = ptz_cmds[direction]
            await host.set_ptz_command(CHANNEL, command=cmd)
            if direction != "stop":
                await asyncio.sleep(duration)
                await host.set_ptz_command(CHANNEL, command="Stop")
            print(f"  [v] {direction.upper()} OK")
        else:
            print(f"  [x] Direção inválida: {direction}")
            print(f"      Opções: up, down, left, right, upleft, upright, downleft, downright, zoomin, zoomout, stop")
    finally:
        await host.logout()


async def set_ir(enabled):
    """Liga/desliga infravermelho."""
    host = await get_host()
    try:
        await host.set_ir_lights(CHANNEL, enabled)
        print(f"  [v] IR {'LIGADO' if enabled else 'DESLIGADO'}")
    finally:
        await host.logout()


async def set_spotlight(enabled):
    """Liga/desliga holofote/spotlight (WhiteLED)."""
    host = await get_host()
    try:
        await host.set_whiteled(CHANNEL, state=enabled)
        print(f"  [v] Spotlight {'LIGADO' if enabled else 'DESLIGADO'}")
    finally:
        await host.logout()


async def set_siren(enabled):
    """Liga/desliga sirene."""
    host = await get_host()
    try:
        await host.set_audio_alarm(CHANNEL, enabled)
        print(f"  [v] Alarme de áudio {'LIGADO' if enabled else 'DESLIGADO'}")
    finally:
        await host.logout()


async def take_snapshot(output=None):
    """Captura um snapshot da câmera."""
    host = await get_host()
    try:
        img = await host.get_snapshot(CHANNEL)
        if img:
            if not output:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                output = f"reolink_snap_{ts}.jpg"
            with open(output, "wb") as f:
                f.write(img)
            print(f"  [v] Snapshot salvo: {os.path.abspath(output)}")
        else:
            print("  [x] Não foi possível obter snapshot")
    finally:
        await host.logout()


# ============================================================
#  Stream de vídeo (OpenCV)
# ============================================================
def stream_video(use_sub=False):
    """Exibe stream de vídeo ao vivo via RTSP."""
    import cv2

    stream = "sub" if use_sub else "main"
    rtsp_url = f"rtsp://{REOLINK_USER}:{REOLINK_PASS}@{REOLINK_IP}:554//h264Preview_01_{stream}"

    print(f"\n[*] Conectando ao stream RTSP ({stream})...")
    print(f"    URL: rtsp://{REOLINK_USER}:****@{REOLINK_IP}:554//h264Preview_01_{stream}")
    print(f"    Pressione 'q' para sair")
    print(f"    Pressione 's' para salvar screenshot")
    print(f"    Pressione 'f' para tela cheia")

    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print(f"  [x] Não foi possível abrir o stream RTSP")
        print(f"      Tente: --sub (stream de menor resolução)")
        return

    window_name = f"Reolink {REOLINK_IP} [{stream}]"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 540)

    fps_time = time.time()
    frame_count = 0
    fullscreen = False

    while True:
        ret, frame = cap.read()
        if not ret:
            print("  [!] Frame perdido, reconectando...")
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            continue

        # FPS counter
        frame_count += 1
        elapsed = time.time() - fps_time
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            frame_count = 0
            fps_time = time.time()
            cv2.setWindowTitle(window_name, f"Reolink {REOLINK_IP} [{stream}] - {fps:.0f} FPS")

        # OSD: data/hora
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, ts, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            snap_name = f"reolink_snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(snap_name, frame)
            print(f"  [v] Screenshot: {snap_name}")
        elif key == ord("f"):
            fullscreen = not fullscreen
            if fullscreen:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)

    cap.release()
    cv2.destroyAllWindows()
    print("  [*] Stream encerrado.")


# ============================================================
#  GUI PyQt6
# ============================================================
def launch_gui():
    """Interface gráfica com vídeo + controles PTZ."""
    import cv2
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout,
        QHBoxLayout, QPushButton, QLabel, QGridLayout,
    )
    from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
    from PyQt6.QtGui import QImage, QPixmap

    stream_url = f"rtsp://{REOLINK_USER}:{REOLINK_PASS}@{REOLINK_IP}:554//h264Preview_01_sub"

    class VideoThread(QThread):
        frame_signal = pyqtSignal(QImage)

        def __init__(self):
            super().__init__()
            self._running = True

        def run(self):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
            while self._running:
                ret, frame = cap.read()
                if ret:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                    self.frame_signal.emit(img.scaled(800, 480, Qt.AspectRatioMode.KeepAspectRatio))
                else:
                    time.sleep(0.5)
            cap.release()

        def stop(self):
            self._running = False
            self.wait()

    class ReolinkGUI(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"Reolink {REOLINK_IP}")
            self.setMinimumSize(900, 600)

            # Video label
            self.video_label = QLabel("Conectando...")
            self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.video_label.setStyleSheet("background: #1a1a2e; color: #aaa; font-size: 16px;")

            # PTZ buttons
            btn_style = """
                QPushButton {
                    background: #16213e; color: white; border: 1px solid #0f3460;
                    border-radius: 6px; padding: 10px; font-size: 14px; font-weight: bold;
                }
                QPushButton:hover { background: #0f3460; }
                QPushButton:pressed { background: #e94560; }
            """

            ptz_grid = QGridLayout()
            directions = [
                ("↖", 0, 0, "upleft"), ("↑", 0, 1, "up"), ("↗", 0, 2, "upright"),
                ("←", 1, 0, "left"), ("⏹", 1, 1, "stop"), ("→", 1, 2, "right"),
                ("↙", 2, 0, "downleft"), ("↓", 2, 1, "down"), ("↘", 2, 2, "downright"),
            ]
            for label, row, col, cmd in directions:
                btn = QPushButton(label)
                btn.setFixedSize(60, 60)
                btn.setStyleSheet(btn_style)
                btn.pressed.connect(lambda c=cmd: self.ptz_cmd(c))
                btn.released.connect(lambda: self.ptz_cmd("stop"))
                ptz_grid.addWidget(btn, row, col)

            # Zoom buttons
            zoom_layout = QHBoxLayout()
            for label, cmd in [("🔍+", "zoomin"), ("🔍−", "zoomout")]:
                btn = QPushButton(label)
                btn.setFixedSize(90, 50)
                btn.setStyleSheet(btn_style)
                btn.clicked.connect(lambda _, c=cmd: self.ptz_cmd(c))
                zoom_layout.addWidget(btn)

            # Feature buttons
            feature_layout = QVBoxLayout()
            features = [
                ("💡 IR", self.toggle_ir),
                ("🔦 Spotlight", self.toggle_spotlight),
                ("🔊 Sirene", self.toggle_siren),
                ("📸 Snapshot", self.do_snapshot),
            ]
            self._ir_on = False
            self._spot_on = False
            self._siren_on = False

            for label, callback in features:
                btn = QPushButton(label)
                btn.setFixedSize(120, 45)
                btn.setStyleSheet(btn_style)
                btn.clicked.connect(callback)
                feature_layout.addWidget(btn)

            # Status
            self.status_label = QLabel("Pronto")
            self.status_label.setStyleSheet("color: #27ae60; padding: 5px;")

            # Layout
            right_panel = QVBoxLayout()
            right_panel.addLayout(ptz_grid)
            right_panel.addSpacing(10)
            right_panel.addLayout(zoom_layout)
            right_panel.addSpacing(10)
            right_panel.addLayout(feature_layout)
            right_panel.addStretch()
            right_panel.addWidget(self.status_label)

            main_layout = QHBoxLayout()
            main_layout.addWidget(self.video_label, 3)
            main_layout.addLayout(right_panel, 1)

            container = QWidget()
            container.setLayout(main_layout)
            container.setStyleSheet("background: #0a0a23;")
            self.setCentralWidget(container)

            # Start video
            self.video_thread = VideoThread()
            self.video_thread.frame_signal.connect(self.update_frame)
            self.video_thread.start()

        def update_frame(self, img):
            self.video_label.setPixmap(QPixmap.fromImage(img))

        def ptz_cmd(self, direction):
            self.status_label.setText(f"PTZ: {direction}")
            asyncio.get_event_loop().run_until_complete(self._async_ptz(direction))

        async def _async_ptz(self, direction):
            try:
                host = await get_host()
                ptz_cmds = {
                    "up": "Up", "down": "Down",
                    "left": "Left", "right": "Right",
                    "upleft": "LeftUp", "upright": "RightUp",
                    "downleft": "LeftDown", "downright": "RightDown",
                    "stop": "Stop",
                    "zoomin": "ZoomInc", "zoomout": "ZoomDec",
                }
                cmd = ptz_cmds.get(direction, "Stop")
                await host.set_ptz_command(CHANNEL, command=cmd)
                await host.logout()
            except Exception as e:
                self.status_label.setText(f"Erro: {e}")

        def toggle_ir(self):
            self._ir_on = not self._ir_on
            asyncio.get_event_loop().run_until_complete(set_ir(self._ir_on))
            self.status_label.setText(f"IR: {'ON' if self._ir_on else 'OFF'}")

        def toggle_spotlight(self):
            self._spot_on = not self._spot_on
            asyncio.get_event_loop().run_until_complete(set_spotlight(self._spot_on))
            self.status_label.setText(f"Spotlight: {'ON' if self._spot_on else 'OFF'}")

        def toggle_siren(self):
            self._siren_on = not self._siren_on
            asyncio.get_event_loop().run_until_complete(set_siren(self._siren_on))
            self.status_label.setText(f"Sirene: {'ON' if self._siren_on else 'OFF'}")

        def do_snapshot(self):
            asyncio.get_event_loop().run_until_complete(take_snapshot())
            self.status_label.setText("Snapshot salvo!")

        def closeEvent(self, event):
            self.video_thread.stop()
            event.accept()

    app = QApplication(sys.argv)
    window = ReolinkGUI()
    window.show()
    sys.exit(app.exec())


# ============================================================
#  Main
# ============================================================
def main():
    global REOLINK_IP, REOLINK_USER, REOLINK_PASS, REOLINK_PORT

    parser = argparse.ArgumentParser(
        description="Conecta e controla câmera Reolink",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Câmera detectada: {REOLINK_IP}
Portas: 80 (HTTP), 443 (HTTPS), 554 (RTSP), 8000 (ONVIF), 9000 (Baichuan)

Exemplos:
  python reolink_camera.py --info
  python reolink_camera.py --stream
  python reolink_camera.py --stream --sub
  python reolink_camera.py --snapshot
  python reolink_camera.py --ptz up
  python reolink_camera.py --ptz left --speed 8
  python reolink_camera.py --ir on
  python reolink_camera.py --spotlight on
  python reolink_camera.py --siren on
  python reolink_camera.py --gui

Variáveis de ambiente (.env):
  REOLINK_IP=192.168.1.84
  REOLINK_USER=admin
  REOLINK_PASS=sua_senha
  REOLINK_PORT=80
        """,
    )
    parser.add_argument("--ip", default=REOLINK_IP, help="IP da câmera")
    parser.add_argument("--user", default=REOLINK_USER, help="Usuário (padrão: admin)")
    parser.add_argument("--pass", dest="password", default=REOLINK_PASS, help="Senha")
    parser.add_argument("--port", type=int, default=REOLINK_PORT, help="Porta HTTP")

    parser.add_argument("--info", action="store_true", help="Mostra informações do dispositivo")
    parser.add_argument("--stream", action="store_true", help="Stream de vídeo ao vivo")
    parser.add_argument("--sub", action="store_true", help="Usa sub-stream (menor resolução)")
    parser.add_argument("--snapshot", action="store_true", help="Captura snapshot")
    parser.add_argument("--snap-output", help="Arquivo de saída do snapshot")

    parser.add_argument("--ptz", choices=["up", "down", "left", "right", "zoomin", "zoomout", "stop"],
                        help="Comando PTZ")
    parser.add_argument("--speed", type=int, default=5, help="Velocidade PTZ (1-10)")
    parser.add_argument("--duration", type=float, default=1.0, help="Duração do movimento PTZ (s)")

    parser.add_argument("--ir", choices=["on", "off"], help="Liga/desliga infravermelho")
    parser.add_argument("--spotlight", choices=["on", "off"], help="Liga/desliga holofote")
    parser.add_argument("--siren", choices=["on", "off"], help="Liga/desliga sirene")

    parser.add_argument("--gui", action="store_true", help="Interface gráfica")
    args = parser.parse_args()

    # Sobrescrever globais
    REOLINK_IP = args.ip
    REOLINK_USER = args.user
    REOLINK_PASS = args.password
    REOLINK_PORT = args.port

    print()
    print("#" * 55)
    print(f"  REOLINK CAMERA CONTROLLER")
    print(f"  Câmera: {REOLINK_IP}:{REOLINK_PORT}")
    print("#" * 55)

    # Se nenhum comando, mostra info
    has_action = any([
        args.info, args.stream, args.snapshot, args.ptz,
        args.ir, args.spotlight, args.siren, args.gui,
    ])

    if not has_action:
        args.info = True

    # Executar ações
    if args.gui:
        launch_gui()
        return

    if args.info:
        asyncio.run(show_info())

    if args.ptz:
        asyncio.run(do_ptz(args.ptz, speed=args.speed, duration=args.duration))

    if args.ir:
        asyncio.run(set_ir(args.ir == "on"))

    if args.spotlight:
        asyncio.run(set_spotlight(args.spotlight == "on"))

    if args.siren:
        asyncio.run(set_siren(args.siren == "on"))

    if args.snapshot:
        asyncio.run(take_snapshot(args.snap_output))

    if args.stream:
        stream_video(use_sub=args.sub)

    print()


if __name__ == "__main__":
    main()
