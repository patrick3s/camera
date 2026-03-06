"""
Descoberta Avançada de Câmeras Xiongmai/iCSee na Rede Local.
Testa múltiplos caminhos RTSP, portas NetSurveillance (34567),
e portas ONVIF (8899) em cada IP encontrado.
"""
import socket
import threading
import cv2
import os
import json
from dotenv import load_dotenv

load_dotenv()

CAM_USER = os.getenv("CAMERA_USER", "admin") 
CAM_PASS = os.getenv("CAMERA_PASS", "admin")

# Portas que câmeras Xiongmai/Jortan costumam usar
CAMERA_PORTS = [80, 554, 8899, 34567, 8000, 8080, 9000]

# Caminhos RTSP conhecidos para câmeras IP chinesas
RTSP_PATHS = [
    "/live/ch0",
    "/live/ch1",
    "/ucast/11",
    "/ucast/12",
    "/h264/ch1/main/av_stream",
    "/h264/ch1/sub/av_stream",
    "/cam/realmonitor?channel=1&subtype=0",
    "/Streaming/Channels/101",
    "/",
    "",
]

def get_local_base_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ".".join(ip.split(".")[:-1]), ip
    except:
        return "192.168.100", "192.168.100.1"

def check_port(ip, port, timeout=0.8):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((ip, port))
    sock.close()
    return result == 0

def check_netsurv_login(ip, port=34567, timeout=3):
    """Tenta um handshake básico no protocolo NetSurveillance (porta 34567).
    Se a câmera responder com bytes, é Xiongmai confirmado."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        
        # Cabeçalho mínimo do protocolo NetSurveillance/Sofia (login request)
        # Bytes: ff 01 00 00 (magic) + 00 00 00 00 (session) + 00 00 00 00 (seq) + ...
        login_payload = {
            "EncryptType": "MD5",
            "LoginType": "DVRIP-Web",
            "PassWord": "tlJwpbo6",  # MD5 hash de "admin" no protocolo XM
            "UserName": CAM_USER
        }
        json_data = json.dumps(login_payload).encode('utf-8')
        
        # Header do protocolo NetSurveillance
        header = bytearray(20)
        header[0] = 0xff  # Magic byte head
        header[1] = 0x01  # Version  
        header[3] = 0x00  # Reserved
        # Message ID para login = 0x03e8 (1000)
        header[14] = 0xe8
        header[15] = 0x03
        # Tamanho do payload JSON
        data_len = len(json_data)
        header[16] = data_len & 0xff
        header[17] = (data_len >> 8) & 0xff
        header[18] = (data_len >> 16) & 0xff
        header[19] = (data_len >> 24) & 0xff
        
        s.sendall(header + json_data)
        response = s.recv(2048)
        s.close()
        
        if len(response) > 0:
            # Tenta decodificar a resposta JSON (pula o header de 20 bytes)
            try:
                resp_json = json.loads(response[20:].decode('utf-8', errors='ignore').strip('\x00'))
                return True, resp_json
            except:
                return True, {"raw_len": len(response)}
        return False, None
    except Exception as e:
        return False, str(e)

def try_rtsp_stream(ip, path, timeout=3):
    """Tenta abrir um stream RTSP real e ler um frame."""
    url = f"rtsp://{CAM_USER}:{CAM_PASS}@{ip}:554{path}"
    try:
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                return True, url
            return False, url
        cap.release()
        return False, url
    except:
        return False, url

def scan_ip(ip, results):
    """Escaneia um IP específico em busca de sinais de câmera."""
    open_ports = []
    for port in CAMERA_PORTS:
        if check_port(ip, port):
            open_ports.append(port)
    
    if not open_ports:
        return
    
    info = {"ip": ip, "ports": open_ports, "is_camera": False, "rtsp_url": None, "netsurv": False, "netsurv_resp": None}
    
    # Teste 1: Porta NetSurveillance (34567) = Xiongmai confirmado
    if 34567 in open_ports:
        success, resp = check_netsurv_login(ip)
        info["netsurv"] = success
        info["netsurv_resp"] = resp
        if success:
            info["is_camera"] = True
    
    # Teste 2: Tenta RTSP se a porta 554 está aberta
    if 554 in open_ports:
        for path in RTSP_PATHS:
            success, url = try_rtsp_stream(ip, path, timeout=3)
            if success:
                info["is_camera"] = True
                info["rtsp_url"] = url
                break
    
    results.append(info)

if __name__ == "__main__":
    print("=" * 60)
    print("  🔎 DESCOBERTA AVANÇADA DE CÂMERAS XIONGMAI/iCSEE")
    print("=" * 60)
    
    base_ip, my_ip = get_local_base_ip()
    print(f"[*] Seu IP: {my_ip}")
    print(f"[*] Escaneando rede: {base_ip}.0/24")
    print(f"[*] Portas alvo: {CAMERA_PORTS}")
    print(f"[*] Caminhos RTSP: {len(RTSP_PATHS)} variações")
    print("-" * 60)
    
    results = []
    threads = []
    
    for i in range(1, 255):
        ip = f"{base_ip}.{i}"
        if ip == my_ip:
            continue
        t = threading.Thread(target=scan_ip, args=(ip, results))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Ordena: câmeras confirmadas primeiro
    results.sort(key=lambda x: (not x["is_camera"], not x["netsurv"]))
    
    print("\n" + "=" * 60)
    print("  📋 RESULTADOS")
    print("=" * 60)
    
    cameras_found = [r for r in results if r["is_camera"]]
    other_devices = [r for r in results if not r["is_camera"]]
    
    if cameras_found:
        print("\n🎯 CÂMERAS CONFIRMADAS:")
        for cam in cameras_found:
            print(f"\n  📹 IP: {cam['ip']}")
            print(f"     Portas abertas: {cam['ports']}")
            if cam["netsurv"]:
                print(f"     ✅ Protocolo NetSurveillance (Xiongmai/iCSee) CONFIRMADO!")
                if isinstance(cam["netsurv_resp"], dict):
                    print(f"     📦 Resposta: {json.dumps(cam['netsurv_resp'], indent=2)[:300]}")
            if cam["rtsp_url"]:
                print(f"     🎬 Stream de Vídeo: {cam['rtsp_url']}")
            
            # Sugestão de .env
            print(f"\n     💡 Sugestão para .env:")
            print(f"        CAMERA_IP={cam['ip']}")
    else:
        print("\n⚠️  Nenhuma câmera Xiongmai/iCSee confirmada na rede!")
    
    if other_devices:
        print(f"\n📱 Outros dispositivos ({len(other_devices)}):")
        for dev in other_devices:
            print(f"  - {dev['ip']} | Portas: {dev['ports']}")
    
    print("\n" + "=" * 60)
