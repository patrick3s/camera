"""
test_flash_light.py - Teste de controle de luz branca (WhiteLight/Flash) da camera Xiongmai
Usa o protocolo binario XM (porta 34567) - unico metodo suportado para configuracao.

Uso:
    python test_flash_light.py                    # Usa admin/admin
    python test_flash_light.py --xm-pass SENHA    # Senha do protocolo XM (iCSee)
    python test_flash_light.py --discover          # Tenta descobrir a senha
"""
import socket
import json
import struct
import hashlib
import time
import sys
import argparse

# -- Configuracoes da Camera --
IP = "192.168.100.2"
PORT_XM = 34567
PORT_HTTP = 80
USER = "admin"
PASS_DEFAULT = "admin"

SEPARADOR = "=" * 55


def xm_hash(password):
    """Gera hash de senha Xiongmai: MD5 -> selecao de 8 chars alfanumericos"""
    if not password:
        return ""
    m = hashlib.md5(password.encode()).digest()
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


class XMClient:
    """Cliente TCP para protocolo binario Xiongmai (DVRIP). Porta padrao: 34567"""

    LOGIN_REQ = 1000
    CONFIG_SET = 1040
    CONFIG_GET = 1042

    def __init__(self, ip, port=34567, user="admin", password="admin"):
        self.ip = ip
        self.port = port
        self.user = user
        self.password = password
        self.sock = None
        self.session_id = 0
        self.seq = 0

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((self.ip, self.port))

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _build(self, msg_id, data):
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8") + b"\x0a\x00"
        header = b"\xff\x01\x00\x00"
        header += struct.pack("<I", self.session_id)
        header += struct.pack("<I", self.seq)
        header += b"\x00\x00"
        header += struct.pack("<H", msg_id)
        header += struct.pack("<I", len(payload))
        self.seq += 1
        return header + payload

    def _recv(self):
        header = b""
        while len(header) < 20:
            chunk = self.sock.recv(20 - len(header))
            if not chunk:
                return None, None
            header += chunk
        data_len = struct.unpack("<I", header[16:20])[0]
        msg_id = struct.unpack("<H", header[14:16])[0]
        data = b""
        while len(data) < data_len:
            chunk = self.sock.recv(min(4096, data_len - len(data)))
            if not chunk:
                break
            data += chunk
        try:
            clean = data.rstrip(b"\x0a\x00").decode("utf-8", "replace")
            return msg_id, json.loads(clean)
        except Exception:
            return msg_id, data

    def login(self):
        self.sock.sendall(
            self._build(
                self.LOGIN_REQ,
                {
                    "EncryptType": "MD5",
                    "LoginType": "DVRIP-Web",
                    "PassWord": xm_hash(self.password),
                    "UserName": self.user,
                },
            )
        )
        msg_id, resp = self._recv()
        if isinstance(resp, dict) and resp.get("Ret") == 100:
            sid = resp.get("SessionID", "0x0")
            self.session_id = int(sid, 16) if isinstance(sid, str) else sid
            return True, resp
        return False, resp

    def get_config(self, name):
        self.sock.sendall(self._build(self.CONFIG_GET, {"Name": name}))
        _, resp = self._recv()
        return resp

    def set_config(self, data):
        self.sock.sendall(self._build(self.CONFIG_SET, data))
        _, resp = self._recv()
        return resp

    @staticmethod
    def ret_msg(code):
        msgs = {
            100: "Sucesso",
            101: "Dados invalidos",
            102: "Sessao invalida",
            105: "Senha incorreta",
            203: "Senha incorreta (XM)",
            206: "Bloqueio temp. ou credenciais incorretas",
            502: "Comando nao suportado",
        }
        return msgs.get(code, "Codigo %d" % code)


# ============================================================
# Funcoes de teste
# ============================================================
def test_conectividade():
    print("\n" + SEPARADOR)
    print("TESTE 0 - Conectividade")
    print(SEPARADOR)
    results = {}

    import requests as req
    try:
        r = req.get("http://%s:%d/" % (IP, PORT_HTTP), timeout=5)
        print("  [v] HTTP (:%d) acessivel - status %d" % (PORT_HTTP, r.status_code))
        results["HTTP"] = True
    except Exception:
        print("  [x] HTTP (:%d) inacessivel" % PORT_HTTP)
        results["HTTP"] = False

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((IP, PORT_XM))
        print("  [v] XM  (:%d) acessivel" % PORT_XM)
        results["XM"] = True
        s.close()
    except Exception:
        print("  [x] XM  (:%d) inacessivel" % PORT_XM)
        results["XM"] = False

    return results


def test_login(password):
    print("\n" + SEPARADOR)
    pw_display = "(vazio)" if not password else password
    print("TESTE 1 - Login XM (user=%s, pass=%s)" % (USER, pw_display))
    print(SEPARADOR)

    cam = XMClient(IP, PORT_XM, USER, password)
    try:
        cam.connect()
        print("  [+] Conectado TCP")
        ok, resp = cam.login()
        ret = resp.get("Ret", -1) if isinstance(resp, dict) else -1
        if ok:
            print("  [v] Login OK - Session: %s" % hex(cam.session_id))
            return True, cam
        else:
            print("  [x] Login falhou: Ret=%d (%s)" % (ret, XMClient.ret_msg(ret)))
            cam.close()
            return False, None
    except Exception as e:
        print("  [x] Erro: %s" % e)
        cam.close()
        return False, None


def test_discover_password():
    print("\n" + SEPARADOR)
    print("TESTE - Descoberta de senha XM")
    print(SEPARADOR)

    senhas = [
        "", "admin", "12345", "123456", "888888", "666666",
        "000000", "111111", "1234", "admin123", "user", "guest",
        "default", "pass", "password",
    ]

    for pw in senhas:
        display = "'%s'" % pw if pw else "(vazio)"
        try:
            cam = XMClient(IP, PORT_XM, USER, pw)
            cam.connect()
            ok, resp = cam.login()
            ret = resp.get("Ret", -1) if isinstance(resp, dict) else -1
            if ok:
                print("  [v] ENCONTRADA: user=%s pass=%s" % (USER, display))
                cam.close()
                return pw
            else:
                print("  [ ] %-15s -> Ret=%d" % (display, ret))
                cam.close()
                time.sleep(1)
        except Exception as e:
            print("  [x] %-15s -> Erro: %s" % (display, e))
            time.sleep(2)

    print("\n  [-] Nenhuma senha comum funcionou.")
    print("  Dica: A senha pode ter sido definida pelo app iCSee.")
    return None


def test_read_config(cam):
    print("\n" + SEPARADOR)
    print("TESTE 2 - Ler configuracoes")
    print(SEPARADOR)
    results = {}

    for name in ["Camera.WhiteLight", "Camera.Param"]:
        print("\n  [>] %s..." % name)
        resp = cam.get_config(name)
        if isinstance(resp, dict):
            ret = resp.get("Ret", -1)
            print("      Ret: %d (%s)" % (ret, XMClient.ret_msg(ret)))
            if ret == 100:
                for k, v in resp.items():
                    if k not in ("Ret", "Name", "SessionID"):
                        print("      %s: %s" % (k, json.dumps(v, ensure_ascii=False)[:300]))
                results[name] = True
            else:
                results[name] = False
        else:
            print("      Raw: %s" % repr(resp)[:200])
            results[name] = False

    return results


def test_set_whitelight(cam, mode):
    print("\n  [>] WhiteLight -> %s..." % mode)
    resp = cam.set_config({
        "Name": "Camera.WhiteLight",
        "Camera.WhiteLight": {"WorkMode": mode},
    })
    if isinstance(resp, dict):
        ret = resp.get("Ret", -1)
        print("      Ret: %d (%s)" % (ret, XMClient.ret_msg(ret)))
        return ret == 100
    else:
        print("      Raw: %s" % repr(resp)[:200])
        return False


def test_ciclo(cam):
    print("\n" + SEPARADOR)
    print("TESTE - Ciclo completo (Color -> Auto -> Intelligent)")
    print(SEPARADOR)

    print("\n  [1/3] LIGANDO...")
    ok1 = test_set_whitelight(cam, "Color")
    if ok1:
        print("  >>> LED deve estar ACESO. Aguardando 5s...")
        time.sleep(5)

    print("\n  [2/3] DESLIGANDO...")
    ok2 = test_set_whitelight(cam, "Auto")
    if ok2:
        print("  >>> LED deve estar APAGADO. Aguardando 3s...")
        time.sleep(3)

    print("\n  [3/3] INTELLIGENT...")
    ok3 = test_set_whitelight(cam, "Intelligent")

    print("\n  Color=%s, Auto=%s, Intelligent=%s" % (
        "OK" if ok1 else "FALHOU",
        "OK" if ok2 else "FALHOU",
        "OK" if ok3 else "FALHOU",
    ))
    return ok1, ok2, ok3


def main():
    global IP
    parser = argparse.ArgumentParser(description="Teste de controle de luz da camera Xiongmai")
    parser.add_argument("--xm-pass", default=PASS_DEFAULT,
                        help="Senha do protocolo XM/iCSee (padrao: admin)")
    parser.add_argument("--discover", action="store_true",
                        help="Tenta descobrir a senha XM testando senhas comuns")
    parser.add_argument("--ip", default=IP, help="IP da camera")
    args = parser.parse_args()

    IP = args.ip
    password = args.xm_pass

    print("")
    print("#" * 55)
    print("  SOGRO - Teste de Flash/WhiteLight")
    print("  Camera: %s (HTTP:%d / XM:%d)" % (IP, PORT_HTTP, PORT_XM))
    print("#" * 55)

    # Conectividade
    conn = test_conectividade()
    if not conn.get("XM"):
        print("\n[-] Porta %d inacessivel." % PORT_XM)
        sys.exit(1)

    # Descoberta de senha
    if args.discover:
        found_pw = test_discover_password()
        if found_pw is not None:
            password = found_pw
            print("\n[+] Use: python test_flash_light.py --xm-pass '%s'" % password)
        else:
            sys.exit(1)

    # Login
    ok, cam = test_login(password)
    if not ok:
        print("\n[-] Login falhou. Use --discover ou --xm-pass SENHA")
        sys.exit(1)

    try:
        # Menu
        print("\n" + SEPARADOR)
        print("Opcoes:")
        print("  1 - Ler configuracao atual")
        print("  2 - LIGAR luz (Color)")
        print("  3 - DESLIGAR luz (Auto)")
        print("  4 - Modo Inteligente")
        print("  5 - Ciclo completo")
        print("  0 - Executar todos")
        print(SEPARADOR)

        escolha = input("\nDigite a opcao: ").strip()
        resultados = {}

        if escolha == "1":
            resultados.update(test_read_config(cam))
        elif escolha == "2":
            resultados["Ligar"] = test_set_whitelight(cam, "Color")
        elif escolha == "3":
            resultados["Desligar"] = test_set_whitelight(cam, "Auto")
        elif escolha == "4":
            resultados["Intelligent"] = test_set_whitelight(cam, "Intelligent")
        elif escolha == "5":
            ok1, ok2, ok3 = test_ciclo(cam)
            resultados = {"Color": ok1, "Auto": ok2, "Intelligent": ok3}
        elif escolha == "0":
            resultados.update(test_read_config(cam))
            ok1, ok2, ok3 = test_ciclo(cam)
            resultados.update({"Color": ok1, "Auto": ok2, "Intelligent": ok3})
        else:
            print("[x] Opcao invalida.")

        # Resumo
        if resultados:
            print("\n" + "#" * 55)
            print("  RESUMO")
            print("#" * 55)
            for nome, ok in resultados.items():
                status = "v PASSOU" if ok else "x FALHOU"
                print("  [%s] %s" % (status, nome))
            total = len(resultados)
            passou = sum(1 for v in resultados.values() if v)
            print("\n  Resultado: %d/%d" % (passou, total))

    finally:
        cam.close()
        print("\n  [*] Conexao encerrada.")

    print("\n" + "#" * 55)
    print("  Teste finalizado.")
    print("#" * 55)
    print("")


if __name__ == "__main__":
    main()
