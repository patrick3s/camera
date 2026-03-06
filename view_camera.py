import cv2
import time
import sys
import os

def display_camera(rtsp_url):
    """Tenta abrir e exibir o stream de vídeo da câmera."""
    print(f"[*] Tentando conectar ao stream: {rtsp_url}")
    
    # Define variáveis de ambiente para o OpenCV não travar em caso de erro de conexão
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    
    cap = cv2.VideoCapture(rtsp_url)
    
    if not cap.isOpened():
        print("[!] Erro: Não foi possível abrir o stream RTSP.")
        print("[!] Verifique se o IP, porta, usuário e senha estão corretos.")
        return

    print("[+] Conectado! Pressione 'q' para sair ou 's' para salvar um snapshot.")
    
    window_name = "Visualizador de Câmera - SOGRO"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("[!] Perda de sinal do stream.")
            break
            
        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('s'):
            filename = f"snapshot_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"[+] Snapshot salvo como: {filename}")

    cap.release()
    cv2.destroyAllWindows()
    print("[*] Visualizador encerrado.")

if __name__ == "__main__":
    # Configuração da câmera encontrada (Ajuste usuário e senha se necessário)
    CAMERA_IP = "192.168.100.2"
    USER = "admin"
    PASS = "admin"  # <--- Tente 'admin', '12345' ou a senha configurada na câmera
    
    # Caminhos RTSP comuns (varia por fabricante)
    # 1. Hikvision/Dahua: /live/ch0 ou /cam/realmonitor?channel=1&subtype=0
    # 2. ONVIF Genérico: /onvif1 ou /onvif-profile-1
    RTSP_URL = f"rtsp://{USER}:{PASS}@{CAMERA_IP}:554/live/ch0"
    
    # Se o usuário passar um IP por argumento, usamos ele
    if len(sys.argv) > 1:
        RTSP_URL = sys.argv[1]
        
    display_camera(RTSP_URL)
