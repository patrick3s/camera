import requests
import time
from requests.auth import HTTPBasicAuth
from requests.auth import HTTPDigestAuth

# Configurações Base
IP = "192.168.100.2"
USER = "admin"
PASS = "admin"
PORT = 80 # Tentando via interface web comum agora

print(f"[*] Escaneando backdoors CGI/ISAPI comuns em {IP}...")

# Lista de endpoints conhecidos para mover a câmera P/ CIMA (UP)
endpoints = [
    # Hikvision ISAPI Padrão
    {"method": "PUT", "url": f"http://{IP}:{PORT}/ISAPI/PTZCtrl/channels/1/continuous", "data": "<PTZData><pan>0</pan><tilt>10</tilt></PTZData>"},
    # Dahua/Amcrest CGI
    {"method": "GET", "url": f"http://{IP}:{PORT}/cgi-bin/ptz.cgi?action=start&channel=0&code=Up&arg1=0&arg2=1&arg3=0"},
    # Xiongmai (XM) - Mais propício para "H264"
    {"method": "GET", "url": f"http://{IP}:{PORT}/Device/PTZCtrl/up"},
    {"method": "GET", "url": f"http://{IP}:{PORT}/cgi-bin/ptzctrl.cgi?act=up"},
    # Foscam / VStarcam genérico
    {"method": "GET", "url": f"http://{IP}:{PORT}/decoder_control.cgi?command=0&user={USER}&pwd={PASS}"}
]

def try_request(endpoint, auth_type):
    try:
        if auth_type == "basic":
            auth = HTTPBasicAuth(USER, PASS)
        elif auth_type == "digest":
            auth = HTTPDigestAuth(USER, PASS)
        else:
            auth = None

        if endpoint["method"] == "GET":
            response = requests.get(endpoint["url"], auth=auth, timeout=2)
        else:
            response = requests.put(endpoint["url"], auth=auth, data=endpoint.get("data", ""), timeout=2)
            
        return response.status_code, response.text
    except Exception as e:
        return None, str(e)

for endpoint in endpoints:
    print(f"\n[?] Tentando URL: {endpoint['url']}")
    
    # Tenta Auth Basic, Digest e Nenhuma
    for auth_name in ["basic", "digest", "none"]:
        status, text = try_request(endpoint, auth_name)
        
        if status:
            print(f"    -> AUTH [{auth_name.upper()}]: Status {status}")
            if status in [200, 201, 204]:
                print(f"    [!!!] COMANDO ACEITO! A câmera deve ter movido para cima.")
                print(f"    [!!!] Endpoint Válido: {endpoint['url']} via {auth_name.upper()}")
                time.sleep(1) # Espera 1s caso tenha movido
        else:
            # Timeouts ou erros de conexão ignoramos verbosidades extremas
            pass
            
print("\n[*} Fim da auditoria de CGI.")
