"""
test_flash_http.py - Teste de flash via interface HTTP/CGI da camera Xiongmai
Usa o fluxo de login da interface web e testa diferentes rotas de configuracao.
"""
import requests
import json
import hashlib
import time
import sys

IP = "192.168.100.2"
PORT = 80
USER = "admin"
PASS = "admin"
BASE = f"http://{IP}:{PORT}"


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


def pp(data):
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data)


def main():
    sep = "=" * 55
    print(sep)
    print(f"  Teste de Flash via HTTP ({IP}:{PORT})")
    print(sep)

    session = requests.Session()
    headers = {"Content-Type": "application/json"}

    # === Passo 1: GetPreLoginInfo ===
    print("\n[1] GetPreLoginInfo...")
    try:
        r = session.post(
            f"{BASE}/cgi-bin/login.cgi",
            data=json.dumps({"Name": "GetPreLoginInfo"}),
            headers=headers,
            timeout=5,
        )
        resp = json.loads(r.text.strip())
        pp(resp)
        if resp.get("Ret") != 100:
            print("[-] Camera nao respondeu corretamente.")
            sys.exit(1)
    except Exception as e:
        print(f"[-] Erro: {e}")
        sys.exit(1)

    # === Passo 2: Login DVRIP-Web ===
    print("\n[2] Login DVRIP-Web...")
    pw_hash = xm_hash(PASS)
    login_data = {
        "EncryptType": "MD5",
        "LoginType": "DVRIP-Web",
        "PassWord": pw_hash,
        "UserName": USER,
    }
    try:
        r = session.post(
            f"{BASE}/cgi-bin/login.cgi",
            data=json.dumps(login_data),
            headers=headers,
            timeout=5,
        )
        resp = json.loads(r.text.strip())
        pp(resp)
        cookies = dict(session.cookies)
        resp_headers = dict(r.headers)
        print(f"  Cookies: {cookies}")
        print(f"  Set-Cookie header: {resp_headers.get('Set-Cookie', 'nenhum')}")

        if resp.get("Ret") != 100:
            print(f"[-] Login falhou (Ret={resp.get('Ret')})")
            # Tentar com senha vazia
            print("\n[2b] Tentando com senha vazia...")
            login_data["PassWord"] = ""
            r = session.post(
                f"{BASE}/cgi-bin/login.cgi",
                data=json.dumps(login_data),
                headers=headers,
                timeout=5,
            )
            resp = json.loads(r.text.strip())
            pp(resp)
            if resp.get("Ret") != 100:
                print("[-] Login com senha vazia tambem falhou.")
                sys.exit(1)
    except Exception as e:
        print(f"[-] Erro no login: {e}")
        sys.exit(1)

    print("[+] Login OK")

    # === Passo 3: Testar varias rotas de setConfig ===
    print("\n[3] Testando rotas de configuracao com sessao autenticada...")

    rotas_test = [
        # POST JSON para devconfig
        (
            "POST",
            f"{BASE}/cgi-bin/devconfig.cgi?action=setConfig",
            {"Name": "Camera.WhiteLight", "Camera.WhiteLight": {"WorkMode": "Color"}},
        ),
        # POST JSON para devconfig sem action na URL
        (
            "POST",
            f"{BASE}/cgi-bin/devconfig.cgi",
            {"action": "setConfig", "Name": "Camera.WhiteLight", "Camera.WhiteLight": {"WorkMode": "Color"}},
        ),
        # GET config
        (
            "POST",
            f"{BASE}/cgi-bin/devconfig.cgi?action=getConfig",
            {"Name": "Camera.WhiteLight"},
        ),
        # Tentar rota snapshot (validar se sessao funciona)
        (
            "POST",
            f"{BASE}/cgi-bin/snapshot.cgi",
            {"Name": "Snap"},
        ),
        # Tentar Camera.Param
        (
            "POST",
            f"{BASE}/cgi-bin/devconfig.cgi?action=setConfig",
            {"Name": "Camera.Param", "Camera.Param": [{"DayNightColor": "0x00000002"}]},
        ),
        # Rota configManager (estilo Dahua)
        (
            "POST",
            f"{BASE}/cgi-bin/configManager.cgi?action=setConfig",
            {"Name": "Camera.WhiteLight", "Camera.WhiteLight": {"WorkMode": "Color"}},
        ),
    ]

    for method, url, payload in rotas_test:
        print(f"\n  [{method}] {url}")
        print(f"      Payload: {json.dumps(payload)[:120]}")
        try:
            r = session.post(url, data=json.dumps(payload), headers=headers, timeout=5)
            body = r.text[:300].strip()
            print(f"      Status: {r.status_code}")
            print(f"      Resp: {body}")
            try:
                rj = json.loads(body)
                if rj.get("Ret") == 100:
                    print("      >>> ACEITO <<<")
            except Exception:
                pass
        except requests.exceptions.ConnectionError:
            print("      [x] Conexao recusada/fechada")
        except Exception as e:
            print(f"      [x] Erro: {e}")

    # === Passo 4: Testar com Digest Auth adicionalmente ===
    print("\n[4] Testando com Digest Auth + sessao...")
    from requests.auth import HTTPDigestAuth

    payload = {"Name": "Camera.WhiteLight", "Camera.WhiteLight": {"WorkMode": "Color"}}
    try:
        r = session.post(
            f"{BASE}/cgi-bin/devconfig.cgi?action=setConfig",
            data=json.dumps(payload),
            headers=headers,
            auth=HTTPDigestAuth(USER, PASS),
            timeout=5,
        )
        print(f"  Status: {r.status_code}")
        print(f"  Resp: {r.text[:300].strip()}")
    except Exception as e:
        print(f"  Erro: {e}")

    print(f"\n{sep}")
    print("  Teste finalizado.")
    print(sep)


if __name__ == "__main__":
    main()
