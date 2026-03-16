"""
test_xm_flash_quick.py - Teste rapido de flash via protocolo XM (porta 34567)
Faz login, le config WhiteLight, liga, espera, desliga.
"""
import socket
import json
import struct
import hashlib
import time
import sys

IP = "192.168.100.2"
PORT = 34567
USER = "admin"
PASS = "admin"


def xm_hash(pw):
    if not pw:
        return ""
    m = hashlib.md5(pw.encode()).digest()
    s = ""
    for i in range(8):
        n = (m[2 * i] + m[2 * i + 1]) % 0x3E
        if n < 10:
            s += chr(0x30 + n)
        elif n < 36:
            s += chr(0x41 + n - 10)
        else:
            s += chr(0x61 + n - 36)
    return s


def build(mid, data, sid=0, seq=0):
    p = json.dumps(data, separators=(",", ":")).encode() + b"\x0a\x00"
    h = (
        b"\xff\x01\x00\x00"
        + struct.pack("<I", sid)
        + struct.pack("<I", seq)
        + b"\x00\x00"
        + struct.pack("<H", mid)
        + struct.pack("<I", len(p))
    )
    return h + p


def rx(sock):
    h = b""
    while len(h) < 20:
        c = sock.recv(20 - len(h))
        if not c:
            return None, None
        h += c
    dl = struct.unpack("<I", h[16:20])[0]
    mi = struct.unpack("<H", h[14:16])[0]
    d = b""
    while len(d) < dl:
        c = sock.recv(min(4096, dl - len(d)))
        if not c:
            break
        d += c
    try:
        return mi, json.loads(d.rstrip(b"\x0a\x00").decode("utf-8", "replace"))
    except Exception:
        return mi, d


def pp(r):
    if isinstance(r, dict):
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print(repr(r))


def main():
    print("=" * 50)
    print(f"  Teste rapido de Flash via XM ({IP}:{PORT})")
    print("=" * 50)

    # Conectar
    print("\n[*] Conectando...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((IP, PORT))
    except Exception as e:
        print(f"[-] Falha na conexao: {e}")
        sys.exit(1)
    print("[+] Conectado")

    # Login
    print("\n[*] Login com admin/admin...")
    s.sendall(
        build(
            1000,
            {
                "EncryptType": "MD5",
                "LoginType": "DVRIP-Web",
                "PassWord": xm_hash(PASS),
                "UserName": USER,
            },
        )
    )
    mi, r = rx(s)
    pp(r)

    if not isinstance(r, dict) or r.get("Ret") != 100:
        ret = r.get("Ret", -1) if isinstance(r, dict) else -1
        print(f"\n[-] Login falhou (Ret={ret})")
        if ret == 203:
            print("    Senha incorreta para protocolo XM")
        elif ret == 206:
            print("    Bloqueio temporario. Aguarde 1-2 min e tente novamente.")
        s.close()
        sys.exit(1)

    sid_str = r.get("SessionID", "0x0")
    sid = int(sid_str, 16) if isinstance(sid_str, str) else sid_str
    print(f"[+] Login OK - Session: {hex(sid)}")
    seq = 1

    # GET WhiteLight
    print("\n[*] Lendo Camera.WhiteLight...")
    s.sendall(build(1042, {"Name": "Camera.WhiteLight"}, sid, seq))
    seq += 1
    mi, r = rx(s)
    pp(r)

    # GET Camera.Param
    print("\n[*] Lendo Camera.Param...")
    s.sendall(build(1042, {"Name": "Camera.Param"}, sid, seq))
    seq += 1
    mi, r = rx(s)
    pp(r)

    # SET WhiteLight -> Color (LIGAR)
    print("\n[*] LIGANDO luz (Camera.WhiteLight -> Color)...")
    s.sendall(
        build(
            1040,
            {
                "Name": "Camera.WhiteLight",
                "Camera.WhiteLight": {"WorkMode": "Color"},
            },
            sid,
            seq,
        )
    )
    seq += 1
    mi, r = rx(s)
    pp(r)
    ret_ligar = r.get("Ret", -1) if isinstance(r, dict) else -1
    if ret_ligar == 100:
        print("[+] Luz LIGADA com sucesso")
    else:
        print(f"[~] Ret={ret_ligar}")

    # Esperar
    print("\n[*] Aguardando 5s com luz ligada... (verifique a camera)")
    time.sleep(5)

    # SET WhiteLight -> Auto (DESLIGAR)
    print("\n[*] DESLIGANDO luz (Camera.WhiteLight -> Auto)...")
    s.sendall(
        build(
            1040,
            {
                "Name": "Camera.WhiteLight",
                "Camera.WhiteLight": {"WorkMode": "Auto"},
            },
            sid,
            seq,
        )
    )
    seq += 1
    mi, r = rx(s)
    pp(r)
    ret_desligar = r.get("Ret", -1) if isinstance(r, dict) else -1
    if ret_desligar == 100:
        print("[+] Luz DESLIGADA com sucesso")
    else:
        print(f"[~] Ret={ret_desligar}")

    # Resumo
    print("\n" + "=" * 50)
    print("  RESUMO")
    print("=" * 50)
    print(f"  Login:    OK")
    print(f"  Ligar:    {'OK' if ret_ligar == 100 else 'FALHOU (Ret=' + str(ret_ligar) + ')'}")
    print(f"  Desligar: {'OK' if ret_desligar == 100 else 'FALHOU (Ret=' + str(ret_desligar) + ')'}")
    print("=" * 50)

    s.close()
    print("\n[*] Conexao encerrada.")


if __name__ == "__main__":
    main()
