import sys
from onvif import ONVIFCamera

# Configurações baseadas na varredura anterior
IP = "192.168.100.2"
PORT = 8899  # Porta do serviço onvif/device_service
USER = "admin"
PASS = "admin"

def main():
    print(f"[*] Conectando à câmera ONVIF em {IP}:{PORT}...")
    try:
        # Tenta conectar no serviço ONVIF (Padrão mundial para interoperabilidade de IP Cams)
        cam = ONVIFCamera(IP, PORT, USER, PASS)
        print("[+] Conectado com sucesso através do protocolo ONVIF!\n")
        
        # 1. Obter informações básicas
        try:
            device_info = cam.devicemgmt.GetDeviceInformation()
            print("--- 📱 INFO DO DISPOSITIVO ---")
            print(f"Fabricante: {device_info.Manufacturer}")
            print(f"Modelo:     {device_info.Model}")
            print(f"Firmware:   {device_info.FirmwareVersion}")
        except Exception as e:
            print(f"Não foi possível extrair info do modelo: {e}")

        # 2. Obter mapeamento de capacidades e comandos que a câmera aceita "Ouvir"
        print("\n--- 🎧 CAPACIDADES E COMANDOS SUPORTADOS ---")
        capabilities = cam.devicemgmt.GetCapabilities()
        
        if capabilities.PTZ:
            print("[+] PTZ (Pan/Tilt/Zoom): HABILITADO")
            print("    -> A câmera PODE receber comandos de movimento (Girar Direita, Esquerda, Zoom).")
        else:
            print("[-] PTZ: DESABILITADO (Câmera estática).")
            
        if capabilities.Imaging:
            print("[+] IMAGING (Controle de Imagem): HABILITADO")
            print("    -> A câmera PODE receber comandos para alterar Brilho, Foco, Saturação e Exposição via script.")
            
        if capabilities.Events:
            print("[+] EVENTS (Eventos de Alarme): HABILITADO")
            print("    -> A câmera PODE enviar e receber triggers para alertas como 'Movimento Detectado'.")
            
        print("\n--- 🛠️ EXEMPLO DE COMANDOS DIRETOS QUE PODEMOS ENVIAR ---")
        print("Se ela possuir suporte PTZ, podemos usar o Python para enviar ordens como:")
        print(" - ContinuousMove (Girar X/Y)")
        print(" - Stop (Parar motor)")
        print(" - AbsoluteMove (Virar para coordenada específica)")
        print(" - SetPreset / GotoPreset (Gravar posições como 'Focar_na_Porta')")
        print("\nCaso a câmera aceite comandos HTTP simples (CGI/ISAPI), o usual seria algo como:")
        print(" http://192.168.100.2/cgi-bin/ptzctrl.cgi?act=up")
        
    except Exception as e:
        print(f"\n[!] Falha na conexão de auditoria ONVIF:")
        print(f"Erro: {e}")
        print("\nDica: Se erro for de autenticação, o Usuário/Senha podem estar diferentes (ex: admin/12345).")

if __name__ == "__main__":
    main()
