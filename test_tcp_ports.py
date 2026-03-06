import socket
import time
import json
import binascii

CAM_IP = "192.168.100.13"

PAYLOADS = {
    "Vazio (Apenas conectar)": b"",
    "HTTP GET Básico": b"GET / HTTP/1.1\r\nHost: " + CAM_IP.encode() + b"\r\n\r\n",
    "String aleatoria": b"hello\n",
    "JSON Simples (SystemInfo)": json.dumps({"Name": "SystemInfo"}).encode(),
    "DVRIP / XMeye Header (Login)": binascii.unhexlify("ff00000000000000000000000000000000000000"),
    # Outro possível header P2P/Jortan (0x01 + length)
    "Header P2P Genérico A": binascii.unhexlify("0100000000000000"),
    "Header P2P Genérico B": binascii.unhexlify("aa00000000000000"),
}

def test_tcp_port(port):
    print(f"\n==============================================")
    print(f"📡 TESTANDO PORTA TCP: {port}")
    print(f"==============================================")
    
    for name, payload in PAYLOADS.items():
        print(f"\n--- Enviando: {name} ---")
        if payload:
            print(f"Hex: {payload.hex()}")
            try:
                print(f"ASCII: {payload.decode('ascii', errors='ignore')}")
            except:
                pass
                
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)  # Timeout de 3 segundos
            s.connect((CAM_IP, port))
            
            if payload:
                s.sendall(payload)
                
            try:
                # Esperar por uma resposta
                resp = s.recv(4096)
                if resp:
                    print(f"✅ RESPOSTA RECEBIDA ({len(resp)} bytes):")
                    print(f"   Hex: {resp.hex()}")
                    print(f"   ASCII: {resp.decode('ascii', errors='replace')}")
                else:
                    print(f"❌ Conexão fechada pela câmera sem resposta (0 bytes).")
            except socket.timeout:
                print(f"⏳ Timeout (3s). A câmera não respondeu a este payload.")
            except Exception as e:
                print(f"❌ Erro ao ler resposta: {e}")
                
            s.close()
            time.sleep(0.5)
            
        except ConnectionRefusedError:
            print(f"❌ Porta {port} fechada ou recusou a conexão.")
            break # Não adianta tentar outros payloads se a porta está fechada
        except Exception as e:
            print(f"❌ Erro na conexão: {e}")

if __name__ == "__main__":
    print(f"Iniciando sondagem TCP na câmera {CAM_IP}")
    test_tcp_port(554)  # RTSP - deve responder
    test_tcp_port(5000)
    test_tcp_port(50000)
    print("\nTestes concluídos!")
