import cv2
import mediapipe as mp
import pickle
import numpy as np
import warnings

# Oculta avisos chatos do scikit-learn
warnings.filterwarnings("ignore")

MODEL_FILE = "gesture_model.pkl"

# Dicionário da tela (precisa ser O MESMO do treinamento!)
CLASSES = {
    0: "Aberta (Pare)",
    1: "Fechada (Soco)",
    2: "Joinha (OK)",
    3: "Paz e Amor",
    4: "Rock / Horns"
}

# Inicializa o MediaPipe Hands (o mesmo do treinamento e os mesmos parametros)
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_drawn = mp.solutions.drawing_utils

def normalize_landmarks(hand_landmarks):
    # A IA só sabe ler as coordenas EXATAMENTE no mesmo formato (Pulso no 0,0,0)
    base_x = hand_landmarks.landmark[0].x
    base_y = hand_landmarks.landmark[0].y
    base_z = hand_landmarks.landmark[0].z
    
    row = []
    for lm in hand_landmarks.landmark:
        row.extend([lm.x - base_x, lm.y - base_y, lm.z - base_z])
    return row

def run_recognition():
    # Tenta carregar o modelo de Machine Learning treinado
    try:
        with open(MODEL_FILE, 'rb') as f:
            model = pickle.load(f)
        print("[*] 🧠 Modelo de IA carregado com sucesso!")
    except FileNotFoundError:
        print("[!] ❌ Modelo não encontrado. Rode o 'train_gesture_model.py' primeiro!")
        return

    print("[*] 📷 Iniciando Câmera Frontal para Gestos Customizados...")
    cap = cv2.VideoCapture(0)
    # Reduzir resolução processa mais FPS e trava menos o PC
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    window_name = "Reconhecimento Customizado IA - Scikit-Learn"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            continue

        # Efeito espelho para webcam
        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Faz as conexoes na imagem BGR com a lib do mediapipe
        results = hands.process(image_rgb)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawn.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
                # Extrai dados da mesma forma que o script de treinamento ('x', 'y', 'z')
                features = normalize_landmarks(hand_landmarks)
                
                # Converte para arquivo Numpy pra ficar compatível (1 foto = 1 array 2D e 63 colunas)
                features_arr = np.array([features])
                
                # O modelo prediz a classe VENCEDORA E a PROBABILIDADE
                prediction = model.predict(features_arr)[0]
                probabilities = model.predict_proba(features_arr)[0]
                confidence = probabilities[prediction]
                
                # Filtro de Confiança:
                # Só mostra algo tiver mais de 65% de certeza, pra evitar falsos positivos
                if confidence > 0.65:
                    gesture_name = CLASSES.get(prediction, f"Gesto {prediction}")
                    text = f"{gesture_name} ({confidence*100:.1f}%)"
                    color = (0, 255, 0) # Verde se achou com certeza
                else:
                    text = "Aguardando Confianca..."
                    color = (0, 255, 255) # Amarelo

                h, w, c = image.shape
                # Localização do texto é encima do Pulso (Landmark 0)
                cx, cy = int(hand_landmarks.landmark[0].x * w), int(hand_landmarks.landmark[0].y * h)
                
                # Drop shadow para ver fácil
                cv2.putText(image, text, (cx - 50 + 2, cy - 30 + 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
                cv2.putText(image, text, (cx - 50, cy - 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)

        cv2.putText(image, "Pressione 'q' p/ sair", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow(window_name, image)

        # Atualiza tela
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    # Limpeza
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_recognition()
