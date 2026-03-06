import sys
import cv2
import requests
import threading
import subprocess
import os
import signal
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

    def send_onvif_auxiliary(self, command):
        """Envia comandos auxiliares ONVIF (ex: tt:LightOn para ligar LED)"""
        print(f"[*] Enviando comando auxiliar de luz ONVIF: {command}")
        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
  <soap:Body>
    <tptz:SendAuxiliaryCommand>
      <tptz:ProfileToken>000</tptz:ProfileToken>
      <tptz:AuxiliaryData>{command}</tptz:AuxiliaryData>
    </tptz:SendAuxiliaryCommand>
  </soap:Body>
</soap:Envelope>"""
        threading.Thread(target=self._fire_soap, args=(soap_body,)).start()


    def _fire_soap(self, soap_body):
        """Dispara a instrução SOAP em back via Thread"""
        headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
        try:
            requests.post(ONVIF_URL, data=soap_body, headers=headers, auth=HTTPDigestAuth(USER, PASS), timeout=2)
        except Exception as e:
            print(f"[!] Erro ao enviar SOAP: {e}")

    def send_ptz_soap(self, pan_speed, tilt_speed):
        """Monta e injeta XML limpo (sem Speed namespace) direto na porta de serviço ONVIF"""
        print(f"[*] Movendo -> Pan: {pan_speed}, Tilt: {tilt_speed}")
        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
  <soap:Body>
    <tptz:ContinuousMove>
      <tptz:ProfileToken>000</tptz:ProfileToken>
      <tptz:Velocity>
        <tt:PanTilt x="{pan_speed}" y="{tilt_speed}" space="http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace"/>
      </tptz:Velocity>
    </tptz:ContinuousMove>
  </soap:Body>
</soap:Envelope>"""
        threading.Thread(target=self._fire_soap, args=(soap_body,)).start()

    def stop_ptz(self):
        """Envia pacote SOAP explícito exigindo parar motores"""
        print("[*] Parando motor PTZ")
        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <soap:Body>
    <tptz:Stop>
      <tptz:ProfileToken>000</tptz:ProfileToken>
      <tptz:PanTilt>true</tptz:PanTilt>
      <tptz:Zoom>true</tptz:Zoom>
    </tptz:Stop>
  </soap:Body>
</soap:Envelope>"""
        threading.Thread(target=self._fire_soap, args=(soap_body,)).start()

    # --- Funções Extras (Luz/Flash) ---
    def _fire_cgi(self, payload):
        """Envia comando CGI (devconfig) em background via Thread"""
        headers = {"Content-Type": "application/json"}
        try:
            r = requests.post(CGI_URL, data=json.dumps(payload), headers=headers,
                              auth=HTTPDigestAuth(USER, PASS), timeout=3)
            print(f"  [CGI] Status: {r.status_code} | Resposta: {r.text[:200].strip()}")
        except Exception as e:
            print(f"  [!] Erro ao enviar CGI: {e}")

    def toggle_flash(self, checked):
        if checked:
            self.btn_flash.setText("💡 Luz Ligada")
            self.btn_flash.setStyleSheet("background-color: #F1C40F; color: #2C3E50; font-weight: bold; border-radius: 5px;")
            self.send_onvif_auxiliary("tt:LightOn")
        else:
            self.btn_flash.setText("💡 Luz (Flash)")
            self.btn_flash.setStyleSheet("background-color: #F39C12; color: white; font-weight: bold; border-radius: 5px;")
            self.send_onvif_auxiliary("tt:LightOff")


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
