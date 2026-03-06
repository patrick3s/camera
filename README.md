# SOGRO - Camera AI & Reconhecimento Facial 👁️

Este projeto é um conjunto de ferramentas focado na detecção de câmeras IP na rede local e em sistemas de Reconhecimento Facial treináveis em tempo real. Ele foi otimizado para lidar com streams de câmeras de segurança (via protocolo RTSP).

## 🚀 Como Executar o Projeto

Este projeto utiliza o **`uv`** como gerenciador de dependências e ambiente virtual, garantindo que as bibliotecas e suas versões fiquem isoladas.

### 1. Pré-Requisitos
Certifique-se de ter o `uv` e o `cmake` instalados no seu macOS:
```bash
brew install cmake
```

### 2. Rodando o Sistema de Reconhecimento Facial Inteligente
Este script conecta-se a câmera via RTSP e detecta os rostos presentes na tela, dividindo-os entre pessoas "Cadastradas" e "Desconhecido".

No terminal, dentro da pasta do projeto (`camera/`), execute:
```bash
uv run python3 detect_known_faces.py
```
*(Para encerrar, basta apertar a letra **`q`** na tela do vídeo.)*

---

## 📷 Outras Funcionalidades

### Função: Snapshot Limpo (Sem Marcações Vísiveis)
Enquanto a tela da câmera estiver focada e aberta com o `detect_known_faces.py`, você pode apertar a tecla **`s`**. Isso fará o software baixar a imagem nativa que estava passando (livre de tags verdes e textos gerados), salvando como `captura_limpa_[timestamp].jpg` na raiz do seu projeto.


### Buscar Câmeras na Rede
Caso não saiba o IP da sua câmera, o buscador interno usa o protocolo *ONVIF* e rastreio de portas comuns de IP Cams.
```bash
uv run python3 scan_cameras.py
```

### Script de Detecção Genérica (Haar Cascades)
Se quiser apenas rodar um modelo extremamente leve que não reconhece NOMES de pessoas, apenas "Humanos":
```bash
uv run python3 face_detection.py
```

---

## 🧠 Como Funciona o Treinamento da Inteligência Artificial

O sistema é dinâmico. Você **não precisa** escrever o nome das pessoas no script. Ele se baseia na estrutura de arquivos e pastas para gerar os rostos e respectivos Nomes rotulados no software, tudo em tempo real. 

Basta usar a seguinte arquitetura de diretórios para alimentar o banco:

### Arquitetura da Pasta `model_faces/`

A pasta de primeiro nível sempre será considerada **O Nome do Alvo**.
As subpastas seguintes servem apenas para a sua organização pessoal de fotos e ângulos (elas não interferem).

```text
model_faces/
    ├── patrick_soares/                 <-- Esse será o Nome que aparece na Câmera
    │   ├── frontal_rosto/
    │   │   ├── foto_clara.png
    │   │   └── com_oculos.jpg
    │   ├── rosto_perfil_direito/
    │   │   └── image_1.png
    │   └── rosto_perfil_esquerdo/
    │       └── image_1.png
    │
    └── joao_silva/                     <-- Outro alvo cadastrado
        └── foto_generica.jpg
```

Sempre que adicionar ou remover pastas, reinicie o script `detect_known_faces.py` para ele compilar a IA baseada nas novas imagens.
