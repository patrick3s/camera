import cv2
import face_recognition
import os
import time
import numpy as np
import pickle
from datetime import datetime
from dotenv import load_dotenv

# Carrega arquivo .env global
load_dotenv()

# Configurações de conexão baseadas no .env
USE_WEBCAM = os.getenv("USE_WEBCAM", "False").lower() in ("true", "1", "t", "yes")
CAM_USER = os.getenv("CAMERA_USER", "admin")
CAM_PASS = os.getenv("CAMERA_PASS", "mito010894")
CAM_IP = os.getenv("CAMERA_IP", "192.168.100.13")

# Fonte de vídeo (Webcam ou Câmera IP RTSP)
if USE_WEBCAM:
    VIDEO_SOURCE = 0
else:
    VIDEO_SOURCE = f"rtsp://{CAM_USER}:{CAM_PASS}@{CAM_IP}:554/onvif1"

# Configuração da pasta de rostos conhecidos
KNOWN_FACES_DIR = "model_faces"
TOLERANCE = 0.5 # Sensibilidade. Padrão é 0.6. Quanto menor, mais rigoroso (menos falsos positivos).

def load_known_faces():
    """
    Varre a pasta `model_faces/NOME_DA_PESSOA/CATEGORIA/imagem.jpg` de forma recursiva.
    O nome da pessoa sempre será o nome da PRIMEIRA pasta dentro de model_faces.
    Ex: 'model_faces/patrick_soares/perfil_direito/img1.jpg' -> Rótulo gerado: 'Patrick Soares'.
    """
    CACHE_FILE = "encodings.pkl"
    known_face_encodings = []
    known_face_names = []
    
    if not os.path.exists(KNOWN_FACES_DIR):
        os.makedirs(KNOWN_FACES_DIR)
        print(f"[*] Pasta base criada: '{KNOWN_FACES_DIR}'.")
        print("    Crie subpastas com o nome da pessoa. Ex: model_faces/joao/frontal.jpg")
        return [], []

    # Se o arquivo de Cache existir, ele carrega em milissegundos
    if os.path.exists(CACHE_FILE):
        print(f"[*] '[CACHE]' Encontrado! Carregando '{CACHE_FILE}' super rápido (sem rever imagens)...")
        print("    (DICA: Se você adicionar fotos novas na pasta, apague o arquivo 'encodings.pkl' p/ forçar o re-treino)")
        with open(CACHE_FILE, 'rb') as f:
            data = pickle.load(f)
            return data["encodings"], data["names"]

    print("[*] '[TREINO NOVO]' Lendo fotos do disco (Isso demorará proporcionalmente ao nº de imagens)...")
    
    # os.walk percorre todas as pastas e subpastas recursivamente
    for root, dirs, files in os.walk(KNOWN_FACES_DIR):
        for filename in files:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(root, filename)
                
                # Descobre o nome da pessoa pela pasta DE PRIMEIRO NÍVEL
                path_parts = os.path.relpath(filepath, KNOWN_FACES_DIR).split(os.sep)
                
                if len(path_parts) >= 2:
                    raw_name = path_parts[0]
                    name = raw_name.replace("_", " ").title()
                else:
                    name = os.path.splitext(filename)[0].replace("_", " ").title()
                    
                try:
                    image = face_recognition.load_image_file(filepath)
                    encodings = face_recognition.face_encodings(image)
                    
                    if len(encodings) > 0:
                        encoding = encodings[0]
                        known_face_encodings.append(encoding)
                        known_face_names.append(name)
                        sub_path = os.path.join(*path_parts[1:-1]) if len(path_parts) > 2 else "raiz"
                        print(f"    [+] Adicionado: '{name}' | {sub_path} ({filename})")
                    else:
                        print(f"    [!] Nenhum rosto nítido em '{filepath}'. Pulei.")
                except Exception as e:
                    print(f"    [!] Erro crítico ao processar '{filepath}': {e}")
                
    if not known_face_encodings:
         print("    [-] O banco de rostos está vazio.")
    else:
         print(f"[*] Salvando CACHE de {len(known_face_names)} rostos para as próximas inicializações serem instantâneas...")
         with open(CACHE_FILE, 'wb') as f:
             pickle.dump({"encodings": known_face_encodings, "names": known_face_names}, f)
         
    return known_face_encodings, known_face_names


def run_recognition(video_source, known_face_encodings, known_face_names):
    """
    Loop principal do feed de vídeo, rodando o comparador de rostos.
    """
    print(f"\n[*] Conectando à Câmera: {'Webcam (Local)' if video_source == 0 else video_source}")
    
    if isinstance(video_source, str) and video_source.startswith("rtsp"):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
        cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
    else:
        cap = cv2.VideoCapture(video_source)
        # Tenta forçar uma resolução menor na Webcam para ganhar FPS
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("[!] Erro fatal: Câmera não respondeu ou credenciais incorretas.")
        return

    window_name = "Reconhecimento Facial V2 (Treinado)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    print("[+] Sistema Operacional! Exibindo Feed. (Use 'q' para sair)")
    
    prev_time = 0
    frame_count = 0
    # Altere de 3 a 10 dependendo do seu computador. Quanto maior, mais FPS (mas demora um pouco mais a caixa atualizar a posição do rosto ao mover)
    PROCESS_EVERY_N_FRAMES = 5 
    process_this_frame = True

    # Cache de resultados por frame pulado
    face_locations = []
    face_encodings = []
    face_names = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("[!] Falha de sincronia na câmera. Loop quebrado.")
            break
            
        # Salva o frame original, ANTES de desenharmos os quadrados por cima
        clean_frame = frame.copy()

        # Reduzir tamanho (1/5) para o algoritmo rodar muito rápido em CPU
        small_frame = cv2.resize(frame, (0, 0), fx=0.2, fy=0.2)
        
        # Converte de BGR (OpenCV) pra RGB (face_recognition). cv2.cvtColor costuma ser mais rápido que slice do numpy
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Apenas processa as engrenagens pesadas a cada N frames
        if frame_count % PROCESS_EVERY_N_FRAMES == 0:
            # 1. Acha ONDE tem rosto na imagem minificada (usamos modelo HOG)
            face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
            
            # 2. Transforma cada rosto detectado num array de características exclusivas
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            face_names = []
            # 3. Para cada rosto no frame atuam, checa contra os rostos na nossa base
            for face_encoding in face_encodings:
                name = "Desconhecido"
                
                if known_face_encodings:
                    # Compara as distâncias vetoriais (quanto a cara no feed difere da foto no pc)
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    
                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        # Se for menor que a TOLERÂNCIA (0.5), é a mesma pessoa!
                        if face_distances[best_match_index] <= TOLERANCE:
                            name = known_face_names[best_match_index]
                
                face_names.append(name)

        frame_count += 1

        # ========================================================
        # INTERFACE VISUAL (Desenho das Tags)
        # ========================================================
        # Os locations estavam em uma escala 1/5 (multiplica por 5 de novo)
        for (top, right, bottom, left), name in zip(face_locations, face_names):
            top *= 5
            right *= 5
            bottom *= 5
            left *= 5

            # Define a cor baseado em "Sei quem é" vs "Intruso"
            color = (0, 255, 0) if name != "Desconhecido" else (0, 0, 255)

            # Box de foco
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            # Fundo da etiqueta de nome
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            
            # Texto
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

        # Atualiza métricas
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time
        
        cv2.putText(frame, f"FPS: {int(fps)} | Pessoas na tela: {len(face_locations)}", (20, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        cv2.putText(frame, "Pressione 's' p/ foto limpa ou 'q' p/ sair", (20, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            save_dir = "desconhecidos"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            filename = os.path.join(save_dir, f"captura_limpa_{int(time.time())}.jpg")
            # Salva o frame clonado lá do começo, sem os desenhos
            cv2.imwrite(filename, clean_frame)
            print(f"[+] Foto salva sem marcações: {filename}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # Carrega database em disco antes da câmera ligar
    encodings, names = load_known_faces()
    
    # Inicia motor e feed
    run_recognition(VIDEO_SOURCE, encodings, names)
