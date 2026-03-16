"""
Teste específico para a Câmera Jortan JT-8695 (iCSee).
Testa TODAS as URLs RTSP conhecidas para este modelo,
e também faz varredura completa de portas.
"""
import socket
import cv2
import os
import threading
from dotenv import load_dotenv

load_dotenv()

IP = os.getenv("CAMERA_IP", "192.168.100.8")
USER = os.getenv("CAMERA_USER", "admin")
PASS = os.getenv("CAMERA_PASS", "admin")

# URLs RTSP específicas para câmeras iCSee / Jortan (pesquisadas na internet)
RTSP_URLS = [
    # Formato iCSee com autenticação por query string (mais provável!)
    f"rtsp://{IP}:554/user={USER}&password={PASS}&channel=1&stream=0.sdp?",
    f"rtsp://{IP}:554/user={USER}&password={PASS}&channel=1&stream=1.sdp?",
    # Formato com credenciais na URL
    f"rtsp://{USER}:{PASS}@{IP}:554/user={USER}&password={PASS}&channel=1&stream=0.sdp?",
    f"rtsp://{USER}:{PASS}@{IP}:554/user={USER}&password={PASS}&channel=1&stream=1.sdp?",
    # Formato ONVIF
    f"rtsp://{USER}:{PASS}@{IP}:554/onvif1",
    f"rtsp://{USER}:{PASS}@{IP}:554/onvif2",
    # Formatos genéricos
    f"rtsp://{USER}:{PASS}@{IP}:554/live/ch0",
    f"rtsp://{USER}:{PASS}@{IP}:554/live/ch1",
    f"rtsp://{USER}:{PASS}@{IP}:554/ucast/11",
    f"rtsp://{USER}:{PASS}@{IP}:554/ucast/12",
    f"rtsp://{USER}:{PASS}@{IP}:554/",
    f"rtsp://{USER}:{PASS}@{IP}:554",
    f"rtsp://{USER}:{PASS}@{IP}:554/cam/realmonitor?channel=0&subtype=0",
    f"rtsp://{USER}:{PASS}@{IP}:554/cam/realmonitor?channel=1&subtype=0",
    f"rtsp://{USER}:{PASS}@{IP}:554/h264/ch1/main/av_stream",
    f"rtsp://{USER}:{PASS}@{IP}:554/Streaming/Channels/101",
    # Sem credenciais (câmera pode ser aberta)
    f"rtsp://{IP}:554/",
    f"rtsp://{IP}:554/onvif1",
    f"rtsp://{IP}:554/live/ch0",
]

def full_port_scan(ip, start=1, end=65535, batch_size=500):
    """Varredura COMPLETA de todas as portas TCP."""
    print(f"\n[*] Varredura COMPLETA de portas em {ip} (1-65535)...")
    open_ports = []
    
    def check(port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            if s.connect_ex((ip, port)) == 0:
                open_ports.append(port)
                print(f"  [+] Porta {port} ABERTA!")
            s.close()
        except:
            pass
    
    # Primeiro: portas mais comuns de câmeras
    priority_ports = [80, 443, 554, 8000, 8080, 8554, 8899, 9000, 
                      34567, 34568, 34569, 5000, 37777, 37778, 
                      7070, 1935, 3702, 49152, 6660, 6670]
    
    print(f"  [*] Fase 1: Testando {len(priority_ports)} portas prioritárias...")
    threads = []
    for port in priority_ports:
        t = threading.Thread(target=check, args=(port,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    
    # Segundo: varredura de faixas conhecidas de firmware iCSee
    extra_ranges = [(550, 560), (8890, 8910), (34560, 34580), (49150, 49170)]
    print(f"  [*] Fase 2: Testando faixas de firmware iCSee...")
    threads = []
    for start_p, end_p in extra_ranges:
        for port in range(start_p, end_p):
            if port not in priority_ports:
                t = threading.Thread(target=check, args=(port,))
                threads.append(t)
                t.start()
    for t in threads:
        t.join()
    
    return sorted(open_ports)

def test_rtsp(url, timeout=5):
    """Tenta abrir um stream RTSP e ler um frame."""
    try:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|analyzeduration;1000000|probesize;1000000"
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
        
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                return True, f"✅ FRAME CAPTURADO! ({w}x{h})"
            return False, "Abriu mas sem frame"
        cap.release()
        return False, "Não abriu"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    print("=" * 60)
    print(f"  🎯 TESTE ESPECÍFICO: JORTAN JT-8695 ({IP})")
    print("=" * 60)
    
    # FASE 1: Varredura de portas
    open_ports = full_port_scan(IP)
    print(f"\n  📊 Total de portas abertas: {len(open_ports)}")
    print(f"  📋 Portas: {open_ports}")
    
    # FASE 2: Teste de RTSP
    print(f"\n{'='*60}")
    print(f"  🎬 TESTANDO {len(RTSP_URLS)} URLs RTSP...")
    print(f"{'='*60}")
    
    working_urls = []
    for i, url in enumerate(RTSP_URLS, 1):
        # Esconde senha no log
        safe_url = url.replace(PASS, "***")
        print(f"\n  [{i}/{len(RTSP_URLS)}] {safe_url}")
        success, msg = test_rtsp(url)
        print(f"         → {msg}")
        if success:
            working_urls.append(url)
    
    # RESULTADO FINAL
    print(f"\n{'='*60}")
    print(f"  📋 RESULTADO FINAL")
    print(f"{'='*60}")
    
    if working_urls:
        print(f"\n  🎉 {len(working_urls)} URL(s) FUNCIONANDO:")
        for url in working_urls:
            safe_url = url.replace(PASS, "***")
            print(f"    ✅ {safe_url}")
        print(f"\n  💡 Cole no .env: CAMERA_RTSP_URL={working_urls[0]}")
    else:
        print(f"\n  ❌ Nenhuma URL RTSP funcionou.")
        print(f"  📌 Portas abertas detectadas: {open_ports}")
        if open_ports:
            non_554 = [p for p in open_ports if p != 554]
            if non_554:
                print(f"  💡 Tente acessar no browser: http://{IP}:{non_554[0]}/")
    
    print(f"\n{'='*60}")
