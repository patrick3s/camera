import sys
import cv2
import requests
import threading
import subprocess
import os
import signal
import socket
from requests.auth import HTTPDigestAuth
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QGridLayout)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap
import json
import logging
import os
from dotenv import load_dotenv
import time

# Carrega arquivo .env
load_dotenv()

# Logger básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# -- Configurações da Câmera --
CAM_USER = os.getenv("CAMERA_USER", "admin")
CAM_PASS = os.getenv("CAMERA_PASS", "admin")
CAM_IP = os.getenv("CAMERA_IP", "192.168.100.2")
CAM_PORT = os.getenv("CAMERA_PORT", "80")
CAM_PORT_ONVIF = os.getenv("CAMERA_PORT_ONVIF", "8899")

# Câmera Jortan JT-8695: RTSP via /onvif1, transporte UDP, Digest Auth, H.265
RTSP_URL_CH0 = f"rtsp://{CAM_USER}:{CAM_PASS}@{CAM_IP}:554/onvif1" 
RTSP_URL_CH1 = f"rtsp://{CAM_USER}:{CAM_PASS}@{CAM_IP}:554/onvif1"
RTSP_URL = RTSP_URL_CH0
ONVIF_URL = f"http://{CAM_IP}:{CAM_PORT_ONVIF}/onvif/ptz_service"
CGI_URL = f"http://{CAM_IP}:{CAM_PORT}/cgi-bin/devconfig.cgi?action=setConfig"
USER = CAM_USER
PASS = CAM_PASS

# Forçar transporte UDP para RTSP (exigido pelo RtspServer da Jortan)
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    
    def __init__(self):
        super().__init__()
        self._run_flag = True

    def run(self):
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        while self._run_flag:
            ret, cv_img = cap.read()
            if ret:
                rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                p = convert_to_Qt_format.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
                self.change_pixmap_signal.emit(p)
            else:
                time.sleep(0.01)
        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()

class CameraControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SOGRO - IA Interface PTZ (RAW SOAP ONVIF)")
        self.setFixedSize(800, 520)

        # Interface Principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # -- Widget de Vídeo (Esquerda) --
        self.video_label = QLabel("Conectando Stream...")
        self.video_label.setFixedSize(640, 480)
        self.video_label.setStyleSheet("background-color: black; color: white; "
                                       "border: 2px solid #333; font-size: 16px;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.video_label)

        # -- Painel de Controle PTZ (Direita) --
        control_layout = QVBoxLayout()
        title = QLabel("Controle PTZ")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2C3E50;")
        control_layout.addWidget(title)
        
        # Grid para o pad direcional
        grid = QGridLayout()
        
        btn_up = QPushButton("⬆️")
        btn_down = QPushButton("⬇️")
        btn_left = QPushButton("⬅️")
        btn_right = QPushButton("➡️")
        btn_stop = QPushButton("🛑 Parar")
        
        for btn in [btn_up, btn_down, btn_left, btn_right]:
            btn.setFixedSize(60, 60)
            btn.setStyleSheet("font-size: 20px; border-radius: 30px; background-color: #ECF0F1;")
        
        btn_stop.setFixedSize(80, 60)
        btn_stop.setStyleSheet("background-color: #E74C3C; color: white; font-weight: bold; border-radius: 10px;")
        
        grid.addWidget(btn_up, 0, 1)
        grid.addWidget(btn_left, 1, 0)
        grid.addWidget(btn_stop, 1, 1)
        grid.addWidget(btn_right, 1, 2)
        grid.addWidget(btn_down, 2, 1)
        
        # Conecta os botões enviados para o payload Raw
        # Câmera inverte o padrão do ONVIF. Y negativo é pra cima. X negativo é direita.
        btn_up.pressed.connect(lambda: self.send_ptz_soap(0.0, -0.5))    
        btn_up.released.connect(self.stop_ptz)
        
        btn_down.pressed.connect(lambda: self.send_ptz_soap(0.0, 0.5))  
        btn_down.released.connect(self.stop_ptz)
        
        btn_left.pressed.connect(lambda: self.send_ptz_soap(0.5, 0.0))  
        btn_left.released.connect(self.stop_ptz)
        
        btn_right.pressed.connect(lambda: self.send_ptz_soap(-0.5, 0.0))  
        btn_right.released.connect(self.stop_ptz)
        
        btn_stop.clicked.connect(self.stop_ptz)

        control_layout.addLayout(grid)
        
        # -- Controles de Áudio --
        audio_title = QLabel("Comunicação Áudio")
        audio_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        audio_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #8E44AD; margin-top: 20px;")
        control_layout.addWidget(audio_title)

        audio_layout = QHBoxLayout()
        self.btn_listen = QPushButton("🔊 Ouvir")
        self.btn_listen.setCheckable(True)
        self.btn_listen.setFixedSize(110, 40)
        self.btn_listen.setStyleSheet("background-color: #3498DB; color: white; font-weight: bold; border-radius: 5px;")
        
        self.btn_talk = QPushButton("🎤 Falar")
        self.btn_talk.setFixedSize(110, 40)
        # Botão desabilitado pois a função Falar nas câmeras Xiongmai exige o protocolo binário proprietário NetSurv(34567) e não HTTP/RTSP aberto.
        self.btn_talk.setDisabled(True)
        self.btn_talk.setToolTip("A sua câmera bloqueia o envio de áudio por meios abertos (Requer App Original/Porta 34567 proprietária).")
        self.btn_talk.setStyleSheet("background-color: #7F8C8D; color: #BDC3C7; font-weight: bold; border-radius: 5px;")
        
        audio_layout.addWidget(self.btn_listen)
        audio_layout.addWidget(self.btn_talk)
        control_layout.addLayout(audio_layout)

        # -- Controles de Luz (Flash) --
        flash_layout = QHBoxLayout()
        self.btn_flash = QPushButton("💡 Luz (Flash)")
        self.btn_flash.setCheckable(True)
        self.btn_flash.setFixedSize(230, 40)
        self.btn_flash.setToolTip("Liga/Desliga a luz branca (WhiteLight) da câmera via CGI Xiongmai.")
        self.btn_flash.setStyleSheet("background-color: #F39C12; color: white; font-weight: bold; border-radius: 5px;")
        flash_layout.addWidget(self.btn_flash)
        control_layout.addLayout(flash_layout)

        # Lógicas de Interação
        self.ffplay_process = None
        self.btn_listen.toggled.connect(self.toggle_listen)
        
        self.btn_talk.pressed.connect(self.start_talking)
        self.btn_talk.released.connect(self.stop_talking)
        
        self.btn_flash.toggled.connect(self.toggle_flash)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        # Inicia a Thread do Vídeo
        self.thread = VideoThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.start()

    def update_image(self, cv_img):
        self.video_label.setPixmap(QPixmap.fromImage(cv_img))

    # --- Controle via RTSP (SET_PARAMETER / USER_CMD_SET) ---
    # A câmera Jortan JT-8695 não possui ONVIF (porta 8899 fechada).
    # Usa-se comandos RTSP com autenticação Digest (realm: HIipCamera).

    def _get_rtsp_digest_auth(self, method, uri):
        """Calcula o header Digest Auth para requisições RTSP."""
        import hashlib, re
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((CAM_IP, 554))
        # OPTIONS
        s.sendall(f'OPTIONS rtsp://{CAM_IP}:554/ RTSP/1.0\r\nCSeq: 1\r\n\r\n'.encode())
        s.recv(4096)
        # DESCRIBE sem auth para pegar nonce
        s.sendall(f'DESCRIBE {uri} RTSP/1.0\r\nCSeq: 2\r\nAccept: application/sdp\r\n\r\n'.encode())
        resp = s.recv(4096).decode(errors='ignore')
        realm_m = re.search(r'realm="(.+?)"', resp)
        nonce_m = re.search(r'nonce="(.+?)"', resp)
        if not realm_m or not nonce_m:
            s.close()
            return None, None
        realm = realm_m.group(1)
        nonce = nonce_m.group(1)
        ha1 = hashlib.md5(f'{USER}:{realm}:{PASS}'.encode()).hexdigest()
        ha2 = hashlib.md5(f'{method}:{uri}'.encode()).hexdigest()
        response = hashlib.md5(f'{ha1}:{nonce}:{ha2}'.encode()).hexdigest()
        auth_hdr = f'Digest username="{USER}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'
        return s, auth_hdr

    def _send_rtsp_command(self, method, body, content_type="application/json"):
        """Envia um comando RTSP (SET_PARAMETER ou USER_CMD_SET) com Digest Auth."""
        uri = f'rtsp://{CAM_IP}:554/onvif1'
        try:
            s, auth = self._get_rtsp_digest_auth(method, uri)
            if not s or not auth:
                print(f"  [!] Falha ao obter auth Digest RTSP")
                return
            req = (f'{method} {uri} RTSP/1.0\r\n'
                   f'CSeq: 3\r\n'
                   f'Authorization: {auth}\r\n'
                   f'Content-Type: {content_type}\r\n'
                   f'Content-Length: {len(body)}\r\n\r\n{body}')
            s.sendall(req.encode())
            resp = s.recv(4096).decode(errors='ignore')
            status_line = resp.split('\r\n')[0] if resp else 'Sem resposta'
            print(f"  [RTSP] {method} -> {status_line}")
            s.close()
        except Exception as e:
            print(f"  [!] Erro RTSP {method}: {e}")

    def send_ptz_soap(self, pan_speed, tilt_speed):
        """Envia comando PTZ via RTSP USER_CMD_SET (protocolo Jortan JT-8695)"""
        # Mapear velocidades para direções do protocolo XM
        if pan_speed > 0:
            direction = "DirectionLeft"
        elif pan_speed < 0:
            direction = "DirectionRight"
        elif tilt_speed < 0:
            direction = "DirectionUp"
        elif tilt_speed > 0:
            direction = "DirectionDown"
        else:
            direction = "DirectionUp"
        
        step = int(abs(pan_speed or tilt_speed) * 10)
        print(f"[*] PTZ -> {direction} (step={step})")
        
        body = json.dumps({
            "Name": "OPPTZControl",
            "OPPTZControl": {
                "Command": direction,
                "Parameter": {
                    "Channel": 0,
                    "MenuOpts": 0,
                    "Pattern": "SetBegin",
                    "Preset": -1,
                    "Step": step,
                    "Tour": 0
                }
            }
        })
        threading.Thread(target=self._send_rtsp_command, args=("USER_CMD_SET", body)).start()

    def stop_ptz(self):
        """Para o motor PTZ via RTSP USER_CMD_SET"""
        print("[*] Parando motor PTZ")
        body = json.dumps({
            "Name": "OPPTZControl",
            "OPPTZControl": {
                "Command": "DirectionUp",
                "Parameter": {
                    "Channel": 0,
                    "MenuOpts": 0,
                    "Pattern": "Stop",
                    "Preset": -1,
                    "Step": 0,
                    "Tour": 0
                }
            }
        })
        threading.Thread(target=self._send_rtsp_command, args=("USER_CMD_SET", body)).start()

    # --- Funções Extras (Luz/Flash) ---
    def toggle_flash(self, checked):
        if checked:
            self.btn_flash.setText("💡 Luz Ligada")
            self.btn_flash.setStyleSheet("background-color: #F1C40F; color: #2C3E50; font-weight: bold; border-radius: 5px;")
            print("[*] Ligando WhiteLight via RTSP")
            body = json.dumps({"Name": "Camera.WhiteLight", "Camera.WhiteLight": {"Enable": True}})
            threading.Thread(target=self._send_rtsp_command, args=("USER_CMD_SET", body)).start()
        else:
            self.btn_flash.setText("💡 Luz (Flash)")
            self.btn_flash.setStyleSheet("background-color: #F39C12; color: white; font-weight: bold; border-radius: 5px;")
            print("[*] Desligando WhiteLight via RTSP")
            body = json.dumps({"Name": "Camera.WhiteLight", "Camera.WhiteLight": {"Enable": False}})
            threading.Thread(target=self._send_rtsp_command, args=("USER_CMD_SET", body)).start()


    # --- Funções de Áudio ---
    def toggle_listen(self, checked):
        if checked:
            print("[*] Iniciando FFPlay para ouvir o áudio da câmera...")
            self.btn_listen.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; border-radius: 5px;")
            self.btn_listen.setText("🔊 Ouvindo...")
            # Usa subprocess pra abrir uma conexão RTSP focada só em áudio
            # -nodisp desabilita vídeo | -vn força ignorar vídeo
            cmd = [
                "ffplay", "-nodisp", "-vn", "-fflags", "nobuffer", "-flags", "low_delay", 
                "-rtsp_transport", "tcp", RTSP_URL
            ]
            # Ocultando logs do ffplay para não poluir
            self.ffplay_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print("[*] Parando retorno de áudio...")
            self.btn_listen.setStyleSheet("background-color: #3498DB; color: white; font-weight: bold; border-radius: 5px;")
            self.btn_listen.setText("🔊 Ouvir")
            if self.ffplay_process:
                self.ffplay_process.terminate()
                self.ffplay_process.wait()
                self.ffplay_process = None

    def start_talking(self):
        # Desabilitado por bloqueio de Hardware
        pass

    def stop_talking(self):
        # Desabilitado por bloqueio de Hardware
        pass

    def closeEvent(self, event):
        print("[*] Encerrando app...")
        if self.ffplay_process:
            self.ffplay_process.terminate()
        self.thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraControlApp()
    window.show()
    sys.exit(app.exec())
