import requests
import json
import xml.dom.minidom

CAM_IP = "192.168.100.13"

def print_response(name, response):
    print(f"\n================ {name} ================")
    print(f"Status: {response.status_code}")
    print("Headers:", dict(response.headers))
    if response.text:
        try:
            # Tentar formatar XML
            if "<" in response.text and ">" in response.text:
                dom = xml.dom.minidom.parseString(response.text)
                print(dom.toprettyxml(indent="  "))
            else:
                print(response.text)
        except:
            print(response.text)
    else:
        print("<Empty Response>")

def test_http_get(port, path):
    url = f"http://{CAM_IP}:{port}{path}"
    print(f"\n[GET] {url} ... ", end="")
    try:
        resp = requests.get(url, timeout=3)
        print("OK")
        print_response(f"HTTP GET {path}", resp)
    except Exception as e:
        print(f"ERRO: {e}")

def test_onvif(port, path, action, body):
    url = f"http://{CAM_IP}:{port}{path}"
    headers = {
        "Content-Type": f'application/soap+xml; charset=utf-8; action="{action}"'
    }
    print(f"\n[ONVIF POST] {url} (Action: {action.split('/')[-1]}) ... ", end="")
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=3)
        print("OK")
        print_response(f"ONVIF POST {action.split('/')[-1]}", resp)
    except Exception as e:
        print(f"ERRO: {e}")

if __name__ == "__main__":
    print(f"Iniciando testes diretos na câmera {CAM_IP} (Porta 50000)")
    
    # 1. Testar HTTP GET básico nas raízes
    test_http_get(50000, "/")
    test_http_get(50000, "/onvif/device_service")
    test_http_get(50000, "/doc")
    
    # 2. Testar comando ONVIF básico (GetSystemDateAndTime)
    payload_date = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body><tds:GetSystemDateAndTime/></s:Body>
</s:Envelope>"""
    test_onvif(50000, "/onvif/device_service", "http://www.onvif.org/ver10/device/wsdl/GetSystemDateAndTime", payload_date)

    # 3. Testar comando ONVIF GetCapabilities
    payload_caps = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetCapabilities>
      <tds:Category>All</tds:Category>
    </tds:GetCapabilities>
  </s:Body>
</s:Envelope>"""
    test_onvif(50000, "/onvif/device_service", "http://www.onvif.org/ver10/device/wsdl/GetCapabilities", payload_caps)
