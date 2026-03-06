"""
create_hotspot.py — Cria um hotspot Wi-Fi (ponto de acesso) no macOS

Transforma o Mac em um roteador Wi-Fi, compartilhando a internet
(Ethernet/Thunderbolt/USB) via Wi-Fi para outros dispositivos.

IMPORTANTE: No macOS, o compartilhamento de internet via Wi-Fi
exige que a internet venha por OUTRA interface (Ethernet, USB, etc).
Se você já está conectado via Wi-Fi, o Mac não pode usar o mesmo
adaptador Wi-Fi para receber E compartilhar ao mesmo tempo.

Uso:
    python create_hotspot.py                                  # Interativo
    python create_hotspot.py -s "MeuHotspot" -p "senha123"   # Direto
    python create_hotspot.py --stop                           # Desliga hotspot
    python create_hotspot.py --status                         # Verifica status

Requer: sudo (permissão de administrador)
"""

import argparse
import subprocess
import sys
import plistlib
import os
import tempfile
import time
import signal


# ── Constantes ──
SHARING_PLIST = "/Library/Preferences/SystemConfiguration/com.apple.nat.plist"
WIFI_INTERFACE = "en0"


def run_cmd(cmd, sudo=False, check=False):
    """Executa um comando, opcionalmente com sudo."""
    if sudo:
        cmd = ["sudo"] + cmd
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if check and result.returncode != 0:
        raise RuntimeError(f"Comando falhou: {' '.join(cmd)}\n{result.stderr}")
    return result


def get_active_interfaces():
    """Retorna interfaces de rede ativas (com IP) exceto Wi-Fi."""
    interfaces = []
    result = run_cmd(["ifconfig"])
    current_iface = None
    has_inet = False

    for line in result.stdout.splitlines():
        if not line.startswith("\t") and ":" in line:
            if current_iface and has_inet and current_iface != WIFI_INTERFACE:
                interfaces.append(current_iface)
            current_iface = line.split(":")[0]
            has_inet = False
        elif "inet " in line and "127.0.0.1" not in line:
            has_inet = True

    if current_iface and has_inet and current_iface != WIFI_INTERFACE:
        interfaces.append(current_iface)

    return interfaces


def get_interface_info(iface):
    """Retorna informações sobre uma interface."""
    result = run_cmd(["ifconfig", iface])
    ip = None
    for line in result.stdout.splitlines():
        if "inet " in line:
            parts = line.strip().split()
            idx = parts.index("inet") if "inet" in parts else -1
            if idx >= 0 and idx + 1 < len(parts):
                ip = parts[idx + 1]
    return {"name": iface, "ip": ip}


def get_hardware_port(device):
    """Retorna o nome da porta de hardware para um device."""
    result = run_cmd(["networksetup", "-listallhardwareports"])
    lines = result.stdout.splitlines()
    for i, line in enumerate(lines):
        if f"Device: {device}" in line and i > 0:
            port_line = lines[i - 1]
            if "Hardware Port:" in port_line:
                return port_line.split(":", 1)[1].strip()
    return device


def check_internet_sharing_status():
    """Verifica se o compartilhamento de internet está ativo."""
    result = run_cmd(["sudo", "launchctl", "list"], sudo=False)
    if "com.apple.InternetSharing" in result.stdout:
        return True
    # Verificação alternativa
    result2 = run_cmd(["ps", "aux"])
    if "InternetSharing" in result2.stdout:
        return True
    return False


def create_nat_plist(ssid, password, source_iface, channel=149):
    """Cria o plist de configuração do NAT/Internet Sharing."""
    # Configuração do compartilhamento
    nat_config = {
        "NAT": {
            "Enabled": True,
            "PrimaryInterface": source_iface,
            "SharingDevices": [WIFI_INTERFACE],
            "AirPort": {
                "Channel": channel,
                "SSID": ssid,
                "SecurityMode": "WPA2_PSK" if password else "NONE",
            },
        },
    }

    if password:
        nat_config["NAT"]["AirPort"]["Password"] = password
        nat_config["NAT"]["AirPort"]["SecurityMode"] = "WPA2_PSK"

    return nat_config


def start_hotspot(ssid, password, source_iface, channel=149):
    """Inicia o hotspot Wi-Fi via Internet Sharing do macOS."""
    print(f"\n{'=' * 50}")
    print(f"  Criando Hotspot Wi-Fi")
    print(f"{'=' * 50}")
    print(f"  SSID:       {ssid}")
    print(f"  Senha:      {'*' * len(password) if password else '(aberta)'}")
    print(f"  Canal:      {channel}")
    print(f"  Fonte:      {source_iface} ({get_hardware_port(source_iface)})")
    print(f"  Wi-Fi:      {WIFI_INTERFACE}")
    print(f"{'=' * 50}")

    # Verificar se já está ativo
    if check_internet_sharing_status():
        print("\n[!] Compartilhamento de internet já está ativo.")
        print("    Use --stop para desligar primeiro.")
        return False

    # Método 1: Via Sharing Preferences (macOS nativo)
    print("\n[1/3] Configurando NAT...")

    nat_config = create_nat_plist(ssid, password, source_iface, channel)

    # Salvar configuração temporária
    tmp_plist = tempfile.mktemp(suffix=".plist")
    with open(tmp_plist, "wb") as f:
        plistlib.dump(nat_config, f)

    try:
        run_cmd(["cp", tmp_plist, SHARING_PLIST], sudo=True, check=True)
        print("    [v] Plist configurado")
    except Exception as e:
        print(f"    [x] Erro ao configurar plist: {e}")
        os.unlink(tmp_plist)
        return False
    finally:
        if os.path.exists(tmp_plist):
            os.unlink(tmp_plist)

    # Iniciar o serviço
    print("[2/3] Iniciando Internet Sharing...")
    try:
        run_cmd(
            ["launchctl", "load", "-w",
             "/System/Library/LaunchDaemons/com.apple.InternetSharing.plist"],
            sudo=True,
        )
        time.sleep(3)
    except Exception as e:
        print(f"    [!] launchctl: {e}")

    # Verificar
    print("[3/3] Verificando...")
    time.sleep(2)

    # Checar se a interface Wi-Fi mudou de modo
    result = run_cmd(["ifconfig", WIFI_INTERFACE])
    if "status: active" in result.stdout.lower() or "running" in result.stdout.lower():
        print(f"\n{'#' * 50}")
        print(f"  [v] HOTSPOT ATIVO!")
        print(f"  Rede: {ssid}")
        print(f"  Conecte dispositivos a esta rede Wi-Fi")
        print(f"{'#' * 50}")
        return True
    else:
        print("\n[!] O hotspot pode não ter iniciado corretamente.")
        print("    Tente ativar manualmente em:")
        print("    Ajustes > Geral > Compartilhamento > Compartilhamento de Internet")
        print(f"\n    Ou use o método alternativo:")
        print(f"    sudo networksetup -createnetworkservice Hotspot {WIFI_INTERFACE}")
        return False


def stop_hotspot():
    """Para o hotspot/compartilhamento de internet."""
    print("\n[*] Desligando compartilhamento de internet...")

    try:
        run_cmd(
            ["launchctl", "unload", "-w",
             "/System/Library/LaunchDaemons/com.apple.InternetSharing.plist"],
            sudo=True,
        )
        print("    [v] Internet Sharing descarregado")
    except Exception:
        pass

    # Fallback: matar processo
    result = run_cmd(["pgrep", "-f", "InternetSharing"])
    if result.stdout.strip():
        run_cmd(["killall", "InternetSharing"], sudo=True)
        print("    [v] Processo InternetSharing encerrado")

    time.sleep(2)
    print("[v] Hotspot desligado.")
    return True


def show_status():
    """Mostra o status do compartilhamento de internet."""
    print(f"\n{'=' * 50}")
    print("  Status do Compartilhamento de Internet")
    print(f"{'=' * 50}")

    # Verificar serviço
    active = check_internet_sharing_status()
    print(f"  Internet Sharing: {'ATIVO' if active else 'INATIVO'}")

    # Verificar interfaces
    print(f"\n  Interfaces com IP:")
    ifaces = get_active_interfaces()
    for iface in ifaces:
        info = get_interface_info(iface)
        port = get_hardware_port(iface)
        print(f"    {iface} ({port}): {info['ip']}")

    # Wi-Fi
    wifi_info = get_interface_info(WIFI_INTERFACE)
    print(f"    {WIFI_INTERFACE} (Wi-Fi): {wifi_info['ip'] or 'sem IP'}")

    # Verificar NAT plist
    if os.path.exists(SHARING_PLIST):
        try:
            result = run_cmd(["cat", SHARING_PLIST], sudo=True)
            if result.stdout:
                with open(SHARING_PLIST, "rb") as f:
                    config = plistlib.load(f)
                nat = config.get("NAT", {})
                airport = nat.get("AirPort", {})
                print(f"\n  Configuração atual:")
                print(f"    SSID:     {airport.get('SSID', 'N/A')}")
                print(f"    Canal:    {airport.get('Channel', 'N/A')}")
                print(f"    Fonte:    {nat.get('PrimaryInterface', 'N/A')}")
        except Exception:
            pass

    print(f"{'=' * 50}")


def open_system_sharing():
    """Abre as configurações de Compartilhamento do macOS."""
    print("\n[*] Abrindo configurações de Compartilhamento de Internet...")
    # macOS Sequoia 15+
    subprocess.Popen(
        ["open", "x-apple.systempreferences:com.apple.Sharing-Settings.extension"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print("    Ative 'Compartilhamento de Internet' na janela que abriu.")


def main():
    parser = argparse.ArgumentParser(
        description="Cria um hotspot Wi-Fi no macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python create_hotspot.py -s "SogroWiFi" -p "senha123"
  python create_hotspot.py --stop
  python create_hotspot.py --status
  python create_hotspot.py --gui    # Abre configurações do macOS

NOTA: Requer que a internet venha por cabo (Ethernet/Thunderbolt/USB).
      O Mac não pode receber E compartilhar Wi-Fi pelo mesmo adaptador.
        """,
    )
    parser.add_argument("-s", "--ssid", help="Nome da rede Wi-Fi a criar")
    parser.add_argument("-p", "--password", help="Senha da rede (mín. 8 caracteres)")
    parser.add_argument("-c", "--channel", type=int, default=149,
                        help="Canal Wi-Fi (padrão: 149 = 5GHz)")
    parser.add_argument("-i", "--interface", help="Interface fonte de internet (ex: en1, en4)")
    parser.add_argument("--stop", action="store_true", help="Desliga o hotspot")
    parser.add_argument("--status", action="store_true", help="Mostra status atual")
    parser.add_argument("--gui", action="store_true",
                        help="Abre configurações do macOS (método visual)")
    args = parser.parse_args()

    # ── Ações rápidas ──
    if args.stop:
        stop_hotspot()
        return

    if args.status:
        show_status()
        return

    if args.gui:
        open_system_sharing()
        return

    # ── Criar hotspot ──
    print()
    print("#" * 50)
    print("  SOGRO - Criar Hotspot Wi-Fi")
    print("#" * 50)

    # Verificar interfaces disponíveis
    ifaces = get_active_interfaces()
    if not ifaces:
        print("\n[x] Nenhuma interface de internet ativa encontrada (exceto Wi-Fi).")
        print("    Para criar um hotspot, conecte um cabo Ethernet ou USB.")
        print("\n    Alternativa: Use o método GUI do macOS:")
        print("    python create_hotspot.py --gui")
        sys.exit(1)

    # Selecionar interface fonte
    source = args.interface
    if not source:
        if len(ifaces) == 1:
            source = ifaces[0]
            port = get_hardware_port(source)
            info = get_interface_info(source)
            print(f"\n[v] Interface de internet detectada: {source} ({port}) - {info['ip']}")
        else:
            print("\n[?] Múltiplas interfaces encontradas:")
            for i, iface in enumerate(ifaces, 1):
                port = get_hardware_port(iface)
                info = get_interface_info(iface)
                print(f"    {i}. {iface} ({port}) - {info['ip']}")
            escolha = input("\nEscolha a interface (número): ").strip()
            try:
                idx = int(escolha) - 1
                source = ifaces[idx]
            except (ValueError, IndexError):
                print("[x] Opção inválida.")
                sys.exit(1)

    # Nome e senha
    ssid = args.ssid
    if not ssid:
        ssid = input("\nNome da rede Wi-Fi (SSID): ").strip()
        if not ssid:
            ssid = "SogroWiFi"
            print(f"    Usando padrão: {ssid}")

    password = args.password
    if not password:
        password = input("Senha (mín. 8 chars, Enter para aberta): ").strip()

    if password and len(password) < 8:
        print("[x] Senha WPA2 precisa ter no mínimo 8 caracteres.")
        sys.exit(1)

    # Iniciar
    ok = start_hotspot(ssid, password, source, args.channel)

    if not ok:
        print("\n[?] Quer abrir as configurações do macOS para ativar manualmente? (s/n)")
        resp = input("    ").strip().lower()
        if resp in ("s", "sim", "y", "yes"):
            open_system_sharing()

    print()


if __name__ == "__main__":
    main()
