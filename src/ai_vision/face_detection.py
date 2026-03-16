import cv2
import time
import os
import numpy as np

def face_recognition_stream(rtsp_url):
    """
    Realiza a detecção de rostos em tempo real usando a biblioteca 'face_recognition' (Dlib HOG).
    Muito precisa, não reconhece braços ou sombras, mas requer otimização para manter o FPS.
    """
    import face_recognition
    
    print(f"[*] Iniciando detecção focada (Dlib-HOG) no stream: {rtsp_url}")
    
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    cap = cv2.VideoCapture(rtsp_url)
    
    if not cap.isOpened():
        print("[!] Erro: Não foi possível conectar à câmera.")
        return

    window_name = "SOGRO - IA Ultra Precisão (Face-Recognition)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    prev_time = 0
    print("[+] IA Ativa! Pressione 'q' para sair.")

    # Variáveis de otimização de performance
    process_this_frame = True
    face_locations = []

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("[!] Falha na captura do frame.")
            break

        # ==========================================================
        # OTIMIZAÇÃO DE PERFORMANCE (O CUSTO DA PRECISÃO)
        # ==========================================================
        
        # 1. Redimensionamos o frame para 1/4 do tamanho. O cálculo do Dlib fica 4x mais rápido
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

        # 2. O OpenCV usa BGR, o face_recognition usa RGB.
        rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])

        # 3. Processa apenas "metade" dos frames alternadamente para poupar o processador. 
        # A detecção acontece em um modelo de HOG (Histogram of Oriented Gradients), extremamente preciso.
        if process_this_frame:
            # Pega as localizações dos rostos usando o modelo padrão HOG
            face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")

        # Alterna para processar o próximo, ou pular.
        process_this_frame = not process_this_frame
        
        # ==========================================================

        # Desenha resultados (precisamos multiplicar por 4 para voltar ao tamanho do frame original)
        for (top, right, bottom, left) in face_locations:
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            # Desenha o quadrado em volta da face detectada
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            
            # Etiqueta
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, "Humano", (left + 6, bottom - 6), font, 1.0, (0, 0, 0), 1)

        # Calculo do FPS Real na Tela
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time
        
        # Status Text UI
        cv2.putText(frame, f"Detectados (HOG): {len(face_locations)}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
        cv2.putText(frame, f"FPS: {int(fps)}", (20, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow(window_name, frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[*] Detecção facial encerrada.")


    cap.release()
    cv2.destroyAllWindows()
    print("[*] Reconhecimento facial encerrado.")

if __name__ == "__main__":
    # Dados da sua câmera detectada anteriormente
    CAMERA_IP = "192.168.100.2"
    USER = "admin"
    PASS = "admin"
    RTSP_URL = f"rtsp://{USER}:{PASS}@{CAMERA_IP}:554/live/ch0"
    
    face_recognition_stream(RTSP_URL)
