import sys
import subprocess
import requests
from requests.auth import HTTPDigestAuth
from onvif import ONVIFCamera
import time

IP = "192.168.100.2"
PORT_ONVIF = 8899
USER = "admin"
PASS = "admin"
RTSP_URL = f"rtsp://{USER}:{PASS}@{IP}:554/live/ch0"

def check_rtsp_audio():
    print(f"\n[*] Analisando stream RTSP ({RTSP_URL}) com ffprobe para encontrar faixa de Áudio...")
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-of", "default=noprint_wrappers=1:nokey=1", RTSP_URL
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if output:
            print(f"  [+] Áudio DETECTADO no RTSP! Formato: {output.replace(chr(10), ' | ')}")
            return True
        else:
            print("  [-] Nenhuma faixa de áudio detectada no stream RTSP principal.")
            return False
    except Exception as e:
        print(f"  [!] Erro ao executar ffprobe: {e}\n  (ffprobe não está instalado ou erro de rede)")
        return False

def check_onvif_audio_capabilities():
    print(f"\n[*] Analisando perfis ONVIF na porta {PORT_ONVIF} buscando configurações de Áudio...")
    try:
        mycam = ONVIFCamera(IP, PORT_ONVIF, USER, PASS)
        media = mycam.create_media_service()
        profiles = media.GetProfiles()
        
        has_audio = False
        for p in profiles:
            print(f"  -> Perfil: {p.Name}")
            if hasattr(p, 'AudioSourceConfiguration') and p.AudioSourceConfiguration:
                print(f"     [+] AudioSourceConfiguration ENCONTRADA no perfil.")
                has_audio = True
            if hasattr(p, 'AudioEncoderConfiguration') and p.AudioEncoderConfiguration:
                print(f"     [+] AudioEncoderConfiguration ENCONTRADA. Codec: {p.AudioEncoderConfiguration.Encoding}")
                has_audio = True
                
        if not has_audio:
            print("  [-] O ONVIF não exposou perfis de áudio (Pode ser que a porta não suporte ou a câmera não tenha microfone habilitado).")
    except Exception as e:
        print(f"  [!] Erro no ONVIF Media: {e}")

def check_cgi_audio_talkback():
    print(f"\n[*] Procurando endpoints CGI (HTTP 80) comuns de Talkback (Envio de Áudio)...")
    endpoints = [
        "/cgi-bin/audio.cgi?action=getAudioFormat",
        "/cgi-bin/devVideoInput.cgi?action=getAudioContext",
        "/ISAPI/System/TwoWayAudio/channels/1",
        "/Device/AudioCtrl"
    ]
    
    for ep in endpoints:
        url = f"http://{IP}:80{ep}"
        print(f"  -> Testando {url}...")
        try:
            # Testa sem auth e depois com auth
            r = requests.get(url, timeout=2)
            if r.status_code == 401:
                r = requests.get(url, auth=HTTPDigestAuth(USER, PASS), timeout=2)
            
            print(f"     Status: {r.status_code}")
            if r.status_code == 200:
                print(f"     [+] Rota promissora encontrada! Resposta: {r.text[:100].strip()}")
        except Exception as e:
            pass

if __name__ == "__main__":
    print("=== INICIANDO AUDITORIA DE ÁUDIO ===")
    check_rtsp_audio()
    check_onvif_audio_capabilities()
    check_cgi_audio_talkback()
    print("\n=== AUDITORIA FINALIZADA ===")
