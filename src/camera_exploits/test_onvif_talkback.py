from onvif import ONVIFCamera

IP = "192.168.100.2"
PORT = 8899
USER = "admin"
PASS = "admin"

def check_onvif_audio_outputs():
    try:
        mycam = ONVIFCamera(IP, PORT, USER, PASS)
        media = mycam.create_media_service()

        print("[*] Buscando perfis de mídia...")
        profiles = media.GetProfiles()
        token = profiles[0].token

        print(f"[*] Perfil principal token: {token}")

        try:
            print("\n[*] GetAudioOutputs()...")
            outputs = media.GetAudioOutputs()
            print("  Saídas de áudio:", outputs)
        except Exception as e:
            print("  [-] Falha ao buscar AudioOutputs:", e)

        try:
            print("\n[*] GetAudioOutputConfigurations()...")
            out_configs = media.GetAudioOutputConfigurations()
            print("  Configurações:", out_configs)
        except Exception as e:
            print("  [-] Falha ao buscar AudioOutputConfigs:", e)

        try:
            print("\n[*] GetStreamUri para perfil (Verificando Backchannel)...")
            req = media.create_type('GetStreamUri')
            req.ProfileToken = token
            req.StreamSetup = {
                'Stream': 'RTP-Unicast',
                'Transport': {'Protocol': 'RTSP'}
            }
            res = media.GetStreamUri(req)
            print(f"  URI RTSP Padrão: {res.Uri}")
        except Exception as e:
            print("  [-] Falha ao obter RTSP URI:", e)

    except Exception as e:
        print(f"[!] Erro de conexão ONVIF: {e}")

if __name__ == "__main__":
    check_onvif_audio_outputs()
