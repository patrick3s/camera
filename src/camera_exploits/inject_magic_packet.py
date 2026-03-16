import socket
import binascii
import os
from dotenv import load_dotenv

load_dotenv()

# Configuração da nossa Câmera
IP = os.getenv("CAMERA_IP", "192.168.100.2")
PORTA_MAGICA = int(os.getenv("CAMERA_PORT_NETSURV", "34567"))


def inject_payload(hex_stream):
    print(f"\n[*] Conectando à câmera {IP}:{PORTA_MAGICA} na surdina...")
    # 1. Cria um socket (um "túnel" de dados) - sem saber o que é HTTP ou RTSP
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    
    try:
        s.connect((IP, PORTA_MAGICA))
        print("[+] Túnel conectado!")
        
        # 2. Converte a linha de texto do Wireshark (Hex) para Bytes de verdade
        packet_bytes = binascii.unhexlify(hex_stream)
        
        # 3. Empurra os bytes para a câmera (Exatamente como o celular fez!)
        s.sendall(packet_bytes)
        print("[+] Encomenda mágica despachada!")
        
        # 4. Espera a câmera responder com o comprovante (ACK)
        response = s.recv(4096)
        print(f"[+] Resposta Bruta da Câmera (Hex): {binascii.hexlify(response).decode('utf-8')}")
        
    except Exception as e:
        print(f"[-] Erro mortal no socket: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    # COLOQUE AQUI O SEU CÓDIGO DO WIRESHARK!
    # Aquele texto que vc clicou "Copy -> ...As a Hex Stream" do pacote de LIGAR A LUZ
    LIGAR_LUZ_HEX = "ff000000... (COLE AQUI O SEU)"
    
    # E o comando da Luz desligando (O PSH ACK que disparou qnd vc apertou pra desligar)
    DESLIGAR_LUZ_HEX = "ff000000... (COLE AQUI)"
    
    # Se quiser testar, é só pedir pro python jogar:
    # inject_payload(LIGAR_LUZ_HEX)
