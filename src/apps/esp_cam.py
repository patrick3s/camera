import cv2
import time
import sys
import os

def display_camera(stream_url):
    """Tenta abrir e exibir o stream de vídeo da câmera."""
    print(f"[*] Tentando conectar ao stream: {stream_url}")
    
    # Define variáveis de ambiente para o OpenCV não travar em caso de erro de conexão
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    
    cap = cv2.VideoCapture(stream_url)
    
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
    # Configuração para ESP-CAM
    CAMERA_IP = "192.168.168.102"
    
    # Caminhos comuns para streaming de ESP32-CAM:
    # O stream MJPEG na maioria dos projetos 'CameraWebServer' fica na porta 81 com o caminho /stream.
    # Ex: http://192.168.168.102:81/stream
    # Caso sua ESP-CAM esteja configurada para a raiz na porta 80, altere para "http://{CAMERA_IP}/"
    STREAM_URL = f"http://{CAMERA_IP}:81/stream"
    
    # Se o usuário passar uma URL por argumento, usamos ela
    if len(sys.argv) > 1:
        STREAM_URL = sys.argv[1]
        
    display_camera(STREAM_URL)
