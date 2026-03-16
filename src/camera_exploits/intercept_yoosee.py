import os
from scapy.all import sniff, IP, UDP, conf
from dotenv import load_dotenv

load_dotenv()
CAM_IP = os.getenv("CAMERA_IP", "192.168.100.13")

print("""
==============================================================
🕵️‍♂️ INTERCEPTADOR DE PACOTES YOOSEE (P2P UDP)
==============================================================
Instruções:
1. Deixe este script rodando.
2. Certifique-se que o seu Celular e o Computador estão no MEsMO Wi-Fi.
3. Abra o app Yoosee no celular.
4. Mova a câmera (PTZ) ou ligue/desligue a luz pelo app.
5. Os pacotes capturados aparecerão aqui embaixo.
==============================================================
""")

def process_packet(packet):
    if IP in packet and UDP in packet:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        src_port = packet[UDP].sport
        dst_port = packet[UDP].dport
        
        # Filtramos apenas pacotes de/para a câmera
        if src_ip == CAM_IP or dst_ip == CAM_IP:
            # Ignorar pacotes comuns de DNS ou Broadcasts normais se houver (quase todos P2P usam portas altas > 10000)
            if dst_port < 1000 and src_port < 1000:
                pass
                
            payload = bytes(packet[UDP].payload)
            if payload:
                direction = "-> CÂMERA" if dst_ip == CAM_IP else "<- RESPOSTA"
                print(f"\n[+] Pacote UDP {direction}")
                print(f"    Origem: {src_ip}:{src_port} | Destino: {dst_ip}:{dst_port}")
                print(f"    Tamanho: {len(payload)} bytes")
                
                # Tentativa de mostrar o payload em Hex e ASCII legível
                hex_str = payload.hex()
                # Formatar o hex string em blocos para facilitar leitura
                hex_formatted = " ".join([hex_str[i:i+4] for i in range(0, len(hex_str), 4)])
                print(f"    Hex: {hex_formatted}")
                
                # ASCII seguro
                ascii_str = ""
                for byte in payload:
                    if 32 <= byte <= 126:
                        ascii_str += chr(byte)
                    else:
                        ascii_str += "."
                print(f"    ASCII: {ascii_str}")

# Usar BPF Filter para capturar apenas o IP da câmera e ignorar TCP (focar no UDP P2P)
filter_str = f"host {CAM_IP} and udp"

try:
    print(f"⏳ Aguardando tráfego UDP de/para {CAM_IP}...\n")
    # Para Mac, geralmente a interface 'en0' é o Wi-Fi. O Scapy costuma pegar a default.
    sniff(filter=filter_str, prn=process_packet, store=0)
except PermissionError:
    print("\n[!] ERRO DE PERMISSÃO")
    print("Para capturar pacotes de rede (sniffing), você precisa rodar este script como root.")
    print("Execute no terminal: sudo uv run python intercept_yoosee.py")
except Exception as e:
    print(f"\n[!] Erro durante a captura: {e}")
