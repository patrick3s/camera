import cv2
import mediapipe as mp
import csv
import os

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

CSV_FILE = "gestures_dataset.csv"

# Classes dicionário para exibir na tela
CLASSES = {
    0: "Aberta (Pare)",
    1: "Fechada (Soco)",
    2: "Joinha (OK)",
    3: "Paz e Amor",
    4: "Rock / Horns"
}

def init_csv():
    # Se o arquivo não existe, cria os cabeçalhos das colunas
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            writer = csv.writer(f)
            header = ['label']
            for i in range(21):
                header.extend([f'x_{i}', f'y_{i}', f'z_{i}'])
            writer.writerow(header)

def normalize_landmarks(hand_landmarks):
    # Pega a posição do pulso (landmark 0) como origem/ponto zero
    base_x = hand_landmarks.landmark[0].x
    base_y = hand_landmarks.landmark[0].y
    base_z = hand_landmarks.landmark[0].z
    
    row = []
    for lm in hand_landmarks.landmark:
        # Subtrai o pulso para a mão não depender da posição na câmera
        row.extend([lm.x - base_x, lm.y - base_y, lm.z - base_z])
    return row

def main():
    init_csv()
    
    cap = cv2.VideoCapture(0)
    
    # Reduz resolução pra ficar mais rápido
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("=== 📸 COLETADOR DE GESTOS ===")
    print("Mantenha a mão na frente da câmera e aperte os FOCADOS:")
    for k, v in CLASSES.items():
        print(f"[{k}] -> {v}")
    print("Aperte 'q' para sair.")

    window_name = "Coletando Dados (Pressione 0 a 4)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        success, img = cap.read()
        if not success:
            continue

        # Inverte e converte cor
        img = cv2.flip(img, 1)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Processa as mãos
        results = hands.process(img_rgb)
        
        # Monitora o teclado
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

        if results.multi_hand_landmarks:
            # Pega a primeira mão detectada (Simplificação)
            hand_landmarks = results.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # Se um número for apertado, grava a linha
            if ord('0') <= key <= ord('4'):
                class_id = key - ord('0')
                row_data = normalize_landmarks(hand_landmarks)
                
                with open(CSV_FILE, mode='a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([class_id] + row_data)
                
                print(f"[+] Salvo gesto '{CLASSES[class_id]}'")
                
                # Exibe na tela 1 frame de confirmação
                cv2.putText(img, f"GRAVADO: {CLASSES[class_id]}", (50, 100), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Linha inferior de dicas
        cv2.putText(img, "Dicas: 0:Pare | 1:Soco | 2:Joinha | 3:Paz | 4:Rock", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        cv2.imshow(window_name, img)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
