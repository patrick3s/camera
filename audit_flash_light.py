import requests
from requests.auth import HTTPDigestAuth
import json

IP = "192.168.100.2"
PORT = 80
USER = "admin"
PASS = "admin"

def test_xiongmai_daynight_color():
    print("=== Testando Forçar DayNightColor (Acender Luz) ===")
    
    # 1. Utilizando a rota devconfig (que é nativa da Xiongmai iCSee/Xmeye)
    payload_devconfig = {
        "Name": "Camera.WhiteLight",
        "Camera.WhiteLight": {
            "WorkMode": "Color" # Intelligent, Color, Auto
        }
    }
    
    # 2. Rota DayNightColor
    payload_daynight = {
        "Name": "Camera.Param",
        "Camera.Param": {
            "DayNightColor": "Color" # Força a ficar colorido (pode acender o LED)
        }
    }
    
    url_base = f"http://{IP}:{PORT}/cgi-bin/devconfig.cgi?action=setConfig"
    url_param = f"http://{IP}:{PORT}/cgi-bin/devconfig.cgi?action=setConfig"
    
    print("\n[*] POST devconfig (WhiteLight):")
    try:
        r = requests.post(url_base, data=json.dumps(payload_devconfig), auth=HTTPDigestAuth(USER, PASS), timeout=3)
        print(f"  [+] Status: {r.status_code}")
        print(f"  [+] Resposta: {r.text[:200].strip()}")
    except Exception as e:
        print(f"  [-] Erro: {e}")
        
    print("\n[*] POST devconfig (DayNightColor):")
    try:
        r = requests.post(url_param, data=json.dumps(payload_daynight), auth=HTTPDigestAuth(USER, PASS), timeout=3)
        print(f"  [+] Status: {r.status_code}")
        print(f"  [+] Resposta: {r.text[:200].strip()}")
    except Exception as e:
        print(f"  [-] Erro: {e}")

if __name__ == "__main__":
    test_xiongmai_daynight_color()
