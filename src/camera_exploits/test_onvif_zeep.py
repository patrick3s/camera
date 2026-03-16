import os
from dotenv import load_dotenv
from onvif import ONVIFCamera
import zeep

load_dotenv()
CAM_IP = os.getenv("CAMERA_IP", "192.168.100.13")
CAM_USER = os.getenv("CAMERA_USER", "admin")
CAM_PASS = os.getenv("CAMERA_PASS", "mito010894")

PORTS_TO_TEST = [50000, 8899, 5000, 80, 8080, 554]

print(f"==================================================")
print(f"🕵️‍♂️ TESTE DE PROTOCOLO ONVIF OFICIAL (onvif-zeep)")
print(f"Câmera: {CAM_IP} | Usuário: {CAM_USER}")
print(f"==================================================\n")

def test_onvif_port(port):
    print(f"Tentando conectar via ONVIF na porta {port}...")
    try:
        # A biblioteca onvif-zeep requer o path wsdl local. 
        # Como instalamos via pip, geralmente ele usa a de default se passarmos None.
        # No uv/pip, às vezes precisamos apontar o wsdl_dir. Usualmente fica na lib do python
        
        # O mais simples é passar o wsdl_dir padrão do sistema ou usar um try/except para capturar o erro de WSDL
        mycam = ONVIFCamera(CAM_IP, port, CAM_USER, CAM_PASS)
        
        print(f"✅ CONECTADO NA PORTA: {port}")
        
        print("\nObtendo Informações do Dispositivo...")
        resp = mycam.devicemgmt.GetDeviceInformation()
        print(f"  Fabricante: {resp.Manufacturer}")
        print(f"  Modelo:     {resp.Model}")
        print(f"  Firmware:   {resp.FirmwareVersion}")
        
        print("\nVerificando suporte a PTZ...")
        media_service = mycam.create_media_service()
        profiles = media_service.GetProfiles()
        
        if not profiles:
            print("  ❌ Nenhum Media Profile encontrado.")
            return True
            
        profile_token = profiles[0].token
        print(f"  Media Profile: {profile_token}")
        
        try:
            ptz_service = mycam.create_ptz_service()
            print("  ✅ Serviço PTZ Disponível!")
            
            # Tentar pegar os nós PTZ
            try:
                nodes = ptz_service.GetNodes()
                print(f"  PTZ Nodes: {len(nodes)}")
            except Exception as e:
                print(f"  Aviso ao pegar PTZ Nodes: {e}")
                
            print("\n  >> TENTANDO MOVER A CÂMERA PARA A ESQUERDA <<")
            req = ptz_service.create_type('ContinuousMove')
            req.ProfileToken = profile_token
            req.Velocity = ptz_service.GetStatus({'ProfileToken': profile_token}).Position
            # Limpar posição antiga
            req.Velocity = ptz_service.create_type('PTZSpeed')
            req.Velocity.PanTilt = ptz_service.create_type('Vector2D')
            
            # Movimento contínuo Pan X (-1 esquerda, 1 direita)
            req.Velocity.PanTilt.x = -1.0 
            req.Velocity.PanTilt.y = 0.0
            
            ptz_service.ContinuousMove(req)
            print("  Comando enviado! Verifique se a câmera mexeu.")
            
        except Exception as ptz_e:
            print(f"  ❌ Erro ao instanciar PTZ: {ptz_e}")

        return True # Se chegou aqui, encontrou o ONVIF

    except zeep.exceptions.Fault as error:
        print(f"  ❌ Erro de Autenticação/Fault na porta {port}: {error}")
    except Exception as e:
        print(f"  ❌ Falha na porta {port}: {type(e).__name__} - {str(e)[:100]}")
        
    return False

if __name__ == "__main__":
    success = False
    for p in PORTS_TO_TEST:
        if test_onvif_port(p):
            success = True
            break
            
    if not success:
        print("\n❌ Nenhuma porta respondeu ao protocolo ONVIF (onvif-zeep).")
        print("   O protocolo desta câmera parece ser 100% fechado/proprietário P2P.")
