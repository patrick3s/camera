import requests
from requests.auth import HTTPDigestAuth
import time

IP = "192.168.100.2"
PORT = 80
USER = "admin"
PASS = "admin"

def dummy_audio_generator():
    print("[*] Gerando stream de dados dummy G711...")
    # 8000 Hz, 1 channel, 8 bits/sample = 8000 bytes/sec
    # Chunk de 800 bytes = 100ms
    dummy_chunk = b'\xd5' * 800  # \xd5 é o silence no G.711a
    for _ in range(30): # 3 segundos
        yield dummy_chunk
        time.sleep(0.1)

def test_endpoint(url):
    print(f"\n[*] Testando POST em: {url}")
    try:
        r = requests.post(
            url, 
            data=dummy_audio_generator(), 
            auth=HTTPDigestAuth(USER, PASS),
            headers={"Content-Type": "application/octet-stream"},
            timeout=5
        )
        print(f"  [+] Status: {r.status_code}")
        print(f"  [+] Resposta: {r.text[:100]}")
    except Exception as e:
        print(f"  [-] Erro: {e}")

if __name__ == "__main__":
    urls_to_test = [
        f"http://{IP}:{PORT}/cgi-bin/audio.cgi?action=postAudio&channel=0",
        f"http://{IP}:{PORT}/cgi-bin/audio.cgi?action=postAudio&httptype=singlepart&channel=0",
        f"http://{IP}:{PORT}/cgi-bin/audio.cgi",
        f"http://{IP}:{PORT}/Device/AudioCtrl",
    ]
    
    for u in urls_to_test:
        test_endpoint(u)
