import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import pickle

CSV_FILE = "gestures_dataset.csv"
MODEL_FILE = "gesture_model.pkl"

def main():
    print(f"[*] Carregando dataset de {CSV_FILE}...")
    try:
        df = pd.read_csv(CSV_FILE)
    except FileNotFoundError:
        print("[!] Arquivo CSV não encontrado! Rode o coletor de dados primeiro e grave gestos.")
        return

    # Separação das Features (X) e a variável Alvo (y - o rótulo da classe)
    X = df.drop('label', axis=1)
    y = df['label']

    print(f"[*] Foram encontrados {len(df)} exemplos no dataset.")
    if len(df) < 50:
        print("[!] Aviso: Tem poucos dados na base. Tente gravar pelo menos umas 50/100 amostras por gesto!")

    # Divide em Treino (80%) e Teste (20%)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("[*] Treinando modelo Random Forest (Pode demorar uns segundos)...")
    # Random Forest é excelente para este tipo de Classificação Multiclasse e Features Numéricas
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Avaliação num conjunto separado para garantir que ele não "decorou" os dados
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"[*] ✅ Acurácia do modelo no teste: {acc * 100:.2f}%")

    # Salva o modelo treinado (os pesos e a árvore de conhecimento)
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"[*] 🚀 IA treinada salva com sucesso em '{MODEL_FILE}'.")
    print("Agora você já pode executar o arquivo detect_custom_gestures.py para exibir!")

if __name__ == "__main__":
    main()
