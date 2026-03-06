import socket
import uuid
import time
import re
import threading

# Configurações de Rede
MULTICAST_IP = "239.255.255.250"
MULTICAST_PORT = 3702
COMMON_CAMERA_PORTS = [80, 443, 554, 8000, 8080, 8888, 37777]

# XML de Probe para ONVIF WS-Discovery
WS_DISCOVERY_PROBE = """<?xml version="1.0" encoding="utf-8"?>
<Envelope xmlns:tds="http://www.onvif.org/ver10/device/wsdl" xmlns="http://www.w3.org/2003/05/soap-envelope">
  <Header>
    <MessageID xmlns="http://schemas.xmlsoap.org/ws/2004/08/addressing">uuid:{uuid}</MessageID>
    <To xmlns="http://schemas.xmlsoap.org/ws/2004/08/addressing">urn:schemas-xmlsoap-org:ws:2004:08:addressing:discovery</To>
    <Action xmlns="http://schemas.xmlsoap.org/ws/2004/08/addressing">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</Action>
  </Header>
  <Body>
    <Probe xmlns="http://schemas.xmlsoap.org/ws/2005/04/discovery">
      <Types>tds:Device</Types>
    </Probe>
  </Body>
</Envelope>"""

def discover_onvif_cameras():
    """Descobre câmeras usando o protocolo ONVIF WS-Discovery."""
    print("[*] Iniciando descoberta ONVIF (WS-Discovery)...")
    cameras = []
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(3)
    
    # Envia o probe via multicast
    probe_content = WS_DISCOVERY_PROBE.format(uuid=str(uuid.uuid4()))
    sock.sendto(probe_content.encode('utf-8'), (MULTICAST_IP, MULTICAST_PORT))
    
    try:
        while True:
            data, addr = sock.recvfrom(65536)
            response = data.decode('utf-8', errors='ignore')
            
            # Tenta extrair informações básicas como XAddrs (URL do serviço)
            xaddrs = re.findall(r'<[^>]*:XAddrs>(.*?)<\/[^>]*:XAddrs>', response)
            model = re.findall(r'd:Device model:(.*?) ', response)
            
            camera_info = {
                "ip": addr[0],
                "type": "ONVIF",
                "xaddrs": xaddrs[0] if xaddrs else "Não encontrado",
                "model": model[0] if model else "Desconhecido"
            }
            
            if camera_info["ip"] not in [c["ip"] for c in cameras]:
                cameras.append(camera_info)
                print(f"[+] Câmera ONVIF encontrada: {addr[0]} | Modelo: {camera_info['model']}")
                
    except socket.timeout:
        pass
    finally:
        sock.close()
        
    return cameras

def check_port(ip, port, timeout=1):
    """Verifica se uma porta específica está aberta."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((ip, port))
    sock.close()
    return result == 0

def scan_network_ports(base_ip):
    """Varredura simples de portas em uma faixa de IP para encontrar câmeras não-ONVIF."""
    print(f"[*] Iniciando varredura de portas comuns em {base_ip}.0/24...")
    found = []
    
    def worker(ip):
        # Verifica se pelo menos uma das portas de câmera está aberta
        for port in COMMON_CAMERA_PORTS:
            if check_port(ip, port):
                print(f"[?] Possível câmera encontrada em {ip} (Porta {port} aberta)")
                found.append({"ip": ip, "type": "Generic/PortScan", "port": port})
                break

    threads = []
    for i in range(1, 255):
        ip = f"{base_ip}.{i}"
        t = threading.Thread(target=worker, args=(ip,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    return found

def get_local_base_ip():
    """Tenta obter a base do IP da rede local (ex: 192.168.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ".".join(ip.split(".")[:-1])
    except:
        return "192.168.1"

if __name__ == "__main__":
    print("="*50)
    print(" BUSCADOR DE CÂMERAS IP NA REDE LOCAL ")
    print("="*50)
    
    # 1. Descoberta ONVIF (Mais precisa para câmeras modernas)
    onvif_cameras = discover_onvif_cameras()
    
    # 2. Varredura de Portas (Caso a câmera não suporte ONVIF ou esteja com ele desligado)
    base_ip = get_local_base_ip()
    port_cameras = scan_network_ports(base_ip)
    
    # Consolidação de Resultados
    print("\n" + "="*50)
    print(" RESULTADO FINAL DA BUSCA ")
    print("="*50)
    
    combined_ips = set()
    
    if onvif_cameras:
        print("\n[Câmeras ONVIF Detectadas]")
        for cam in onvif_cameras:
            print(f"- IP: {cam['ip']} | Modelo: {cam['model']} | URL: {cam['xaddrs']}")
            combined_ips.add(cam['ip'])
    
    other_cameras = [c for c in port_cameras if c['ip'] not in combined_ips]
    if other_cameras:
        print("\n[Outros Dispositivos (Possíveis Câmeras por Porta)]")
        for cam in other_cameras:
            print(f"- IP: {cam['ip']} (Porta {cam['port']} aberta)")
            
    if not onvif_cameras and not other_cameras:
        print("\n[-] Nenhuma câmera encontrada na rede.")
        
    print("\n[Dica] Certifique-se que o seu computador e as câmeras estão na MESMA REDE.")
    print("="*50)
