import cv2
import mediapipe as mp

# Inicializa o MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_drawn = mp.solutions.drawing_utils

def count_fingers(hand_landmarks):
    """
    Conta o número de dedos levantados baseado nos pontos (landmarks) da mão.
    Retorna o número de dedos ou 0.
    """
    if not hand_landmarks:
        return 0

    fingers = []
    # Pontos das pontas dos dedos (Thumb, Index, Middle, Ring, Pinky)
    tips_ids = [4, 8, 12, 16, 20]
    
    # Verifica o polegar (Thumb) - Lógica diferente porque ele dobra pro lado
    # Compara a ponta (4) com a articulação anterior (3) no eixo X
    # Nota: Isso varia dependendo de qual mão é (esquerda/direita) e se está de costas/frente.
    # Por simplicidade, faremos uma checagem básica de eixo X
    if hand_landmarks.landmark[tips_ids[0]].x < hand_landmarks.landmark[tips_ids[0] - 1].x:
        fingers.append(1)
    else:
        fingers.append(0)

    # Verifica os outros 4 dedos
    for id in range(1, 5):
        # Um dedo está "levantado" se a ponta (tip) estiver mais alta (menor Y) que a articulação do meio (pip)
        if hand_landmarks.landmark[tips_ids[id]].y < hand_landmarks.landmark[tips_ids[id] - 2].y:
            fingers.append(1)
        else:
            fingers.append(0)

    return fingers.count(1)

def recognize_gesture(fingers_count):
    """
    Mapeia a quantidade de dedos para um gesto simples.
    """
    if fingers_count == 0:
        return "Punho Fechado (Pedra)"
    elif fingers_count == 2:
        return "Paz e Amor / Tesoura"
    elif fingers_count == 5:
        return "Palma Aberta (Papel/Pare)"
    elif fingers_count == 1:
        return "Apontando / Um"
    else:
        return f"{fingers_count} dedos"

def run_gesture_recognition():
    print("[*] Iniciando Câmera Frontal para Gestos...")
    cap = cv2.VideoCapture(0)
    
    # Tenta forçar uma resolução menor na Webcam para ganhar FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("[!] Erro: Câmera não encontrada.")
        return

    window_name = "Reconhecimento de Gestos (MediaPipe)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("[!] Ignorando frame vazio.")
            continue

        # Inverte a imagem horizontalmente para visualização espelhada (selfie)
        image = cv2.flip(image, 1)
        
        # Converte a imagem BGR (OpenCV) para RGB (MediaPipe)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Processa a imagem e encontra as mãos
        results = hands.process(image_rgb)

        # Desenha as mãos e conta os dedos
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Desenha os pontos e conexões
                mp_drawn.draw_landmarks(
                    image, 
                    hand_landmarks, 
                    mp_hands.HAND_CONNECTIONS
                )
                
                # Conta os dedos da mão atual
                fingers_count = count_fingers(hand_landmarks)
                gesture_name = recognize_gesture(fingers_count)
                
                # Extrai a posição do pulso para colocar o texto perto da mão
                h, w, c = image.shape
                cx, cy = int(hand_landmarks.landmark[0].x * w), int(hand_landmarks.landmark[0].y * h)
                
                # Exibe o texto
                cv2.putText(image, gesture_name, (cx - 50, cy + 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

        cv2.putText(image, "Pressione 'q' p/ sair", (20, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow(window_name, image)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_gesture_recognition()
