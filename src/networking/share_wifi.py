"""
share_wifi.py — Compartilha a rede Wi-Fi via QR Code

Gera um QR Code que, ao ser escaneado pelo celular (Android/iOS),
conecta automaticamente à rede Wi-Fi.

Uso:
    python share_wifi.py                          # Detecta Wi-Fi atual (macOS)
    python share_wifi.py -s "MinhaRede" -p "senha123"  # Manual
    python share_wifi.py --show                   # Exibe no terminal (ASCII)
"""

import argparse
import subprocess
import sys
import platform
import os

import qrcode
from qrcode.console_scripts import main as qr_main  # noqa: F401


def get_current_ssid_macos() -> str | None:
    """Obtém o SSID da rede Wi-Fi conectada no macOS."""
    # Método 1: system_profiler (mais confiável no macOS recente)
    try:
        result = subprocess.run(
            ["system_profiler", "SPAirPortDataType"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if "Current Network Information:" in line:
                # A próxima linha contém o SSID (indentado, com ":" no final)
                if i + 1 < len(lines):
                    ssid_line = lines[i + 1].strip()
                    if ssid_line.endswith(":"):
                        return ssid_line[:-1]
    except Exception:
        pass

    # Método 2: networksetup
    try:
        result = subprocess.run(
            ["networksetup", "-getairportnetwork", "en0"],
            capture_output=True, text=True, timeout=5,
        )
        line = result.stdout.strip()
        if ":" in line and line.split(":", 1)[1].strip():
            return line.split(":", 1)[1].strip()
    except Exception:
        pass

    # Método 3: airport CLI (legado)
    try:
        result = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport", "-I"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if " SSID:" in line and "BSSID" not in line:
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    return None


def get_password_from_keychain(ssid: str) -> str | None:
    """Tenta obter a senha Wi-Fi do Keychain do macOS (requer permissão)."""
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-D", "AirPort network password",
                "-a", ssid,
                "-w",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def escape_wifi_special(text: str) -> str:
    """Escapa caracteres especiais para o formato WIFI: do QR Code."""
    special = ['\\', '"', ';', ',', ':']
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text


def build_wifi_string(ssid: str, password: str, security: str = "WPA", hidden: bool = False) -> str:
    """
    Gera a string no formato WIFI: para QR Code.
    Formato: WIFI:T:<tipo>;S:<ssid>;P:<senha>;H:<oculta>;;
    """
    s = escape_wifi_special(ssid)
    p = escape_wifi_special(password)
    h = "true" if hidden else "false"
    return f"WIFI:T:{security};S:{s};P:{p};H:{h};;"


def generate_qr(data: str, filename: str | None = None, show_terminal: bool = False) -> str | None:
    """Gera o QR Code como imagem PNG e/ou exibe no terminal."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Exibe no terminal como ASCII
    if show_terminal:
        print()
        qr.print_ascii(invert=True)
        print()

    # Salva imagem PNG
    if filename:
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filename)
        return filename

    # Se não salvou e não mostrou no terminal, salva com nome padrão
    if not show_terminal:
        filename = "wifi_qrcode.png"
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filename)
        return filename

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Compartilha Wi-Fi via QR Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python share_wifi.py                              # Detecta rede atual
  python share_wifi.py -s "MinhaRede" -p "senha"    # Rede específica
  python share_wifi.py --show                        # Exibe no terminal
  python share_wifi.py -o wifi.png                   # Salva como imagem
  python share_wifi.py --security WEP               # Rede WEP
  python share_wifi.py --hidden                      # Rede oculta
        """,
    )
    parser.add_argument("-s", "--ssid", help="Nome da rede Wi-Fi (SSID)")
    parser.add_argument("-p", "--password", help="Senha da rede Wi-Fi")
    parser.add_argument("-o", "--output", help="Arquivo de saída (PNG). Padrão: wifi_qrcode.png")
    parser.add_argument("--security", default="WPA", choices=["WPA", "WEP", "nopass"],
                        help="Tipo de segurança (padrão: WPA)")
    parser.add_argument("--hidden", action="store_true", help="Rede oculta (SSID não visível)")
    parser.add_argument("--show", action="store_true", help="Exibe QR Code no terminal (ASCII)")
    parser.add_argument("--no-image", action="store_true", help="Não salva arquivo de imagem")
    args = parser.parse_args()

    ssid = args.ssid
    password = args.password
    is_macos = platform.system() == "Darwin"

    # ── Detectar SSID automaticamente ──
    if not ssid:
        if is_macos:
            print("[*] Detectando rede Wi-Fi atual...")
            ssid = get_current_ssid_macos()
            if ssid:
                print(f"[v] Rede encontrada: {ssid}")
            else:
                print("[x] Não foi possível detectar a rede Wi-Fi.")
                print("    Use: python share_wifi.py -s 'NomeDaRede' -p 'senha'")
                sys.exit(1)
        else:
            print("[x] Detecção automática só funciona no macOS.")
            print("    Use: python share_wifi.py -s 'NomeDaRede' -p 'senha'")
            sys.exit(1)

    # ── Detectar senha automaticamente ──
    if not password:
        if is_macos:
            print("[*] Buscando senha no Keychain (pode pedir autenticação)...")
            password = get_password_from_keychain(ssid)
            if password:
                print(f"[v] Senha obtida do Keychain")
            else:
                print("[x] Senha não encontrada no Keychain.")
                password = input("    Digite a senha da rede: ").strip()
                if not password:
                    print("[x] Senha não informada. Abortando.")
                    sys.exit(1)
        else:
            password = input("Digite a senha da rede Wi-Fi: ").strip()
            if not password:
                print("[x] Senha não informada. Abortando.")
                sys.exit(1)

    # ── Gerar QR Code ──
    wifi_str = build_wifi_string(ssid, password, args.security, args.hidden)

    print()
    print("=" * 50)
    print(f"  Rede:      {ssid}")
    print(f"  Segurança: {args.security}")
    print(f"  Oculta:    {'Sim' if args.hidden else 'Não'}")
    print("=" * 50)

    output_file = None
    if not args.no_image:
        output_file = args.output or "wifi_qrcode.png"

    saved = generate_qr(wifi_str, filename=output_file, show_terminal=args.show)

    if saved:
        full_path = os.path.abspath(saved)
        print(f"\n[v] QR Code salvo em: {full_path}")
        # Tenta abrir a imagem automaticamente no macOS
        if is_macos:
            try:
                subprocess.Popen(["open", full_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    if not args.show and not saved:
        print("\n[!] Nenhuma saída gerada. Use --show ou remova --no-image.")

    print("\n[*] Aponte a câmera do celular para o QR Code para conectar ao Wi-Fi.")
    print()


if __name__ == "__main__":
    main()
