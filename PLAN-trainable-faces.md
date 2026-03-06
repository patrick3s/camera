# Projeto: Sistema de Reconhecimento Facial Treinável

## Overview
O objetivo é criar um sistema que permita o reconhecimento de pessoas específicas de uma forma muito simples: basta colocar fotos de rosto das pessoas em pastas específicas. O sistema deverá ler essas fotos automaticamente, treinar a inteligência artificial (com Dlib/face_recognition) e aplicar a identificação no feed ao vivo de uma câmera RTSP. As faces não mapeadas serão rotuladas como "Desconhecido".

## Project Type
BACKEND / AUTOMAÇÃO DE VISÃO COMPUTACIONAL (Python)

## Success Criteria
- O sistema deve conseguir identificar pessoas diferentes baseando-se apenas em imagens pré-existentes numa pasta local (Ex: `conhecidos/joao.jpg`).
- Adicionar ou remover imagens deve atualizar os perfis detectados na próxima execução sem a necessidade de intervenção pesada no código.
- As anotações da tela do OpenCV devem refletir o exato nome do arquivo (ex: "Joao" caso o arquivo seja `joao.jpg`).
- Identificação visual precisa da predição ("Quem é") ou rótulo "Desconhecido".

## Tech Stack
- **Python:** Linguagem principal baseada na iteração atual do software.
- **OpenCV (`cv2`):** Gerenciamento do fluxo de vídeo RTSP e desenho na tela.
- **`face_recognition` (Dlib):** Extração de "encodings" faciais e comparação de similaridade de distância.
- **`os` / `pathlib`:** Leitura dinâmica do sistema de arquivos para mapeamento automático das fotos.

## File Structure
```
camera/
├── model_faces/           # Nova pasta para treinar o algoritmo
│   ├── patrick_soares.jpg
│   ├── joao_silva.png
├── detect_known_faces.py  # Novo script de execução e identificação dinâmica
├── scan_cameras.py        # [Existente] Varredor das câmeras
├── view_camera.py         # [Existente] Visualizador local
└── face_detection.py      # [Existente] Detecção facial genérica
```

## Task Breakdown

### 1. Criar a estrutura e diretório do "banco de dados" de rostos
- **Agent:** backend-specialist
- **Skill:** python-patterns
- **Priority:** P1
- **Task:** Criar o diretório `model_faces/` na estruturação do repositório para adicionar e armazenar imagens predefinidas de rostos.
- **INPUT:** Chamada ou manipulação do OS.
- **OUTPUT:** Pasta estruturada pronta para uso.
- **VERIFY:** O script checará a existência deste file no pré-processamento.

### 2. Desenvolver módulo de carregamento e codificação automática
- **Agent:** backend-specialist
- **Skill:** python-patterns
- **Priority:** P1
- **Task:** Criar a base de encoding inteligente no Python que varre o diretório `model_faces/`, converte as imagens num array numérico da face (128D) via biblioteca `face_recognition` e vincula ao nome do arquivo (ex: extraindo o prefixo sem ".jpg").
- **INPUT:** Diretório `model_faces/` com fotos nítidas do rosto.
- **OUTPUT:** Duas listas Python: `known_face_encodings` e `known_face_names`.
- **VERIFY:** O script deve listar no terminal o nome das pessoas "treinadas/carregadas" com êxito na iniciação.

### 3. Integrar Comparador no Loop do Stream (RTSP)
- **Agent:** backend-specialist
- **Skill:** python-patterns
- **Priority:** P1
- **Task:** Embebber os encodings conhecidos (Face Recognition Encoded Array) dentro do loop de captura e aplicar comparação de distância / match_faces em tempo real, respeitando o salto de frames para boa performance imposta no passo 2 de FPS.
- **INPUT:** Frame convertido para RGB minificado, com lista encodada existente.
- **OUTPUT:** Marcação e desenho da string (`[NOME PESSOA]` ou `[Desconhecido]`) na interface GUI original.
- **VERIFY:** Injetar pelo menos 2 rostos teste e simular a câmera (ou acionar a RTSP) para ver no bounding_box se o respectivo nome confere com a pasta model_faces.

## Phase X: Verification
- [ ] O código Python não crasha se a pasta de modelo estiver vazia.
- [ ] Consegue exibir rostos variados com rótulo "Desconhecido" caso os features difiram grandemente do array pré-salvo.
- [ ] Mantém performance mínima detectando a taxa acima de ~10 FPS através da escala/resize da imagem do processo antes de classificar.
- [ ] Testes práticos confirmam que o nome dos arquivos alimentam corretamente as labels descritas no OpenCV Window Mode.
