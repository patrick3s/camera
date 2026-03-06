"""
Web Camera Lab - Interface de teste interativo para câmera Jortan JT-8695.
Inclui stream de vídeo MJPEG + controles de teste para PTZ/Flash/Info (RTSP e HTTP/ONVIF).
"""
import socket
import hashlib
import re
import json
import os
import cv2
import threading
import time
import requests
from flask import Flask, render_template_string, request, jsonify, Response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CAM_IP = os.getenv("CAMERA_IP", "192.168.100.13")
CAM_USER = os.getenv("CAMERA_USER", "admin")
CAM_PASS = os.getenv("CAMERA_PASS", "mito010894")

RTSP_URL = f"rtsp://{CAM_USER}:{CAM_PASS}@{CAM_IP}:554/onvif1"

# Forçar transporte UDP para RTSP
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'

# ---- Engine de Comunicação ----

def rtsp_send(method, path, body="", content_type="application/json"):
    """Envia comando RTSP com Digest Auth e retorna resposta."""
    uri = f"rtsp://{CAM_IP}:554{path}"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((CAM_IP, 554))
        s.sendall(f"OPTIONS rtsp://{CAM_IP}:554/ RTSP/1.0\r\nCSeq: 1\r\n\r\n".encode())
        s.recv(4096)
        s.sendall(f"DESCRIBE {uri} RTSP/1.0\r\nCSeq: 2\r\nAccept: application/sdp\r\n\r\n".encode())
        resp = s.recv(4096).decode(errors="ignore")
        realm_m = re.search(r'realm="(.+?)"', resp)
        nonce_m = re.search(r'nonce="(.+?)"', resp)
        auth_hdr = ""
        if realm_m and nonce_m:
            realm, nonce = realm_m.group(1), nonce_m.group(1)
            ha1 = hashlib.md5(f"{CAM_USER}:{realm}:{CAM_PASS}".encode()).hexdigest()
            ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
            resp_hash = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
            auth_hdr = f'Authorization: Digest username="{CAM_USER}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{resp_hash}"\r\n'
        req = f"{method} {uri} RTSP/1.0\r\nCSeq: 3\r\n{auth_hdr}"
        if body:
            req += f"Content-Type: {content_type}\r\nContent-Length: {len(body)}\r\n\r\n{body}"
        else:
            req += "\r\n"
        s.sendall(req.encode())
        resp = s.recv(8192).decode(errors="ignore")
        s.close()
        return {"ok": True, "request": req, "response": resp}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def http_onvif_send(port, path, body="", method="POST"):
    """Envia comando HTTP/ONVIF e retorna resposta."""
    url = f"http://{CAM_IP}:{port}{path}"
    headers = {"Content-Type": "application/soap+xml; charset=utf-8; action=\"http://www.onvif.org/ver10/device/wsdl/GetSystemDateAndTime\""} if "Envelope" in body else {}
    if method == "GET":
        headers = {}
        
    try:
        if method == "POST":
            resp = requests.post(url, data=body, headers=headers, timeout=5)
        else:
            resp = requests.get(url, timeout=5)
            
        return {
            "ok": resp.status_code < 400,
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "response": resp.text
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def tcp_send(port, data_bytes, wait_secs=3):
    """Envia bytes via TCP e retorna resposta."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(wait_secs)
        s.connect((CAM_IP, port))
        if data_bytes:
            s.sendall(data_bytes)
        try:
            resp = s.recv(8192)
        except socket.timeout:
            resp = b""
        s.close()
        return {"ok": True, "hex": resp.hex(), "ascii": resp.decode(errors="replace"), "length": len(resp)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def scan_ports():
    """Varredura de portas."""
    ports = [80, 443, 554, 5000, 8000, 8080, 8554, 8899, 34567, 34568, 9000, 37777, 3000, 3001, 50000]
    results = {}
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.8)
        results[p] = s.connect_ex((CAM_IP, p)) == 0
        s.close()
    return results

# ---- Stream de Vídeo MJPEG ----

class VideoStream:
    def __init__(self):
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
    
    def start(self):
        if self.running: return
        self.running = True
        threading.Thread(target=self._capture, daemon=True).start()
    
    def _capture(self):
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            print("[!] Falha ao abrir stream RTSP")
            self.running = False
            return
        print("[✓] Stream RTSP conectado")
        while self.running:
            ret, frame = cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.05)
        cap.release()
    
    def get_frame(self):
        with self.lock:
            if self.frame is None: return None
            _, buf = cv2.imencode('.jpg', self.frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return buf.tobytes()

video = VideoStream()

def gen_mjpeg():
    """Gera stream MJPEG para o browser."""
    while True:
        frame = video.get_frame()
        if frame:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.1)

# ---- HTML ----

HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🔬 Camera Lab - Jortan JT-8695</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root { --bg:#0a0e17; --card:#111827; --border:#1e293b; --accent:#3b82f6; --accent2:#10b981; --warn:#f59e0b; --danger:#ef4444; --text:#e2e8f0; --muted:#64748b; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Inter',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
  
  .header { background:linear-gradient(135deg,#1e1b4b,#0f172a); padding:12px 20px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
  .header h1 { font-size:18px; background:linear-gradient(90deg,#60a5fa,#34d399); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
  .header .info { font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--muted); }
  
  .main { display:grid; grid-template-columns:1fr 340px; gap:12px; padding:12px; height:calc(100vh - 50px); }
  
  .left { display:flex; flex-direction:column; gap:12px; }
  
  .video-wrap { background:#000; border-radius:12px; overflow:hidden; position:relative; flex:1; min-height:300px; }
  .video-wrap img { width:100%; height:100%; object-fit:contain; }
  .video-label { position:absolute; top:8px; left:8px; background:rgba(0,0,0,0.7); padding:3px 8px; border-radius:4px; font-size:11px; font-family:'JetBrains Mono',monospace; color:#34d399; }
  
  .log-wrap { background:var(--card); border:1px solid var(--border); border-radius:12px; max-height:250px; overflow-y:auto; padding:8px; }
  .log-wrap h3 { font-size:12px; color:var(--muted); margin-bottom:6px; padding:0 4px; }
  
  .right { display:flex; flex-direction:column; gap:12px; overflow-y:auto; }
  
  .panel { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px; }
  .panel h2 { font-size:12px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); margin-bottom:8px; }
  
  .ports { display:grid; grid-template-columns:repeat(4,1fr); gap:3px; }
  .port { padding:3px; border-radius:3px; font-family:'JetBrains Mono',monospace; font-size:10px; text-align:center; }
  .port.open { background:rgba(16,185,129,0.2); color:#34d399; }
  .port.closed { background:rgba(255,255,255,0.03); color:var(--muted); text-decoration:line-through; }
  
  .quick-btns { display:grid; grid-template-columns:1fr 1fr; gap:6px; }
  .quick-btn { padding:8px 6px; border:1px solid var(--border); border-radius:6px; background:rgba(255,255,255,0.03); color:var(--text); font-size:11px; cursor:pointer; transition:all .15s; font-family:'Inter',sans-serif; }
  .quick-btn:hover { background:rgba(59,130,246,0.15); border-color:var(--accent); transform:scale(1.02); }
  .quick-btn:active { transform:scale(0.98); }
  .quick-btn.ptz { background:rgba(16,185,129,0.08); border-color:rgba(16,185,129,0.25); }
  .quick-btn.light { background:rgba(245,158,11,0.08); border-color:rgba(245,158,11,0.25); }
  .quick-btn.danger { background:rgba(239,68,68,0.06); border-color:rgba(239,68,68,0.25); }
  .quick-btn.full { grid-column:1/-1; }
  
  .form-group { margin-bottom:8px; }
  .form-group label { display:block; font-size:10px; text-transform:uppercase; letter-spacing:.5px; color:var(--muted); margin-bottom:3px; }
  .form-group select,.form-group input,.form-group textarea { width:100%; padding:6px 8px; background:var(--bg); border:1px solid var(--border); border-radius:4px; color:var(--text); font-family:'JetBrains Mono',monospace; font-size:12px; }
  .form-group textarea { min-height:70px; resize:vertical; }
  
  .send-btn { width:100%; padding:10px; background:linear-gradient(135deg,var(--accent),#2563eb); border:none; border-radius:6px; color:white; font-weight:700; font-size:13px; cursor:pointer; transition:all .2s; }
  .send-btn:hover { box-shadow:0 4px 12px rgba(59,130,246,0.4); }
  .send-btn:disabled { opacity:.5; cursor:wait; }
  
  .log-entry { padding:6px 8px; border-bottom:1px solid var(--border); font-size:11px; font-family:'JetBrains Mono',monospace; }
  .log-entry:last-child { border:none; }
  .log-entry .ts { color:var(--muted); font-size:10px; }
  .log-entry .ok { color:var(--accent2); font-weight:700; }
  .log-entry .err { color:var(--danger); font-weight:700; }
  .log-entry pre { margin:4px 0 0; white-space:pre-wrap; word-break:break-all; background:rgba(0,0,0,0.3); padding:6px; border-radius:4px; font-size:10px; max-height:120px; overflow-y:auto; }
</style>
</head>
<body>
<div class="header">
  <h1>🔬 Camera Lab</h1>
  <div class="info">{{ cam_ip }} · Jortan JT-8695 · HIipCamera</div>
</div>

<div class="main">
  <div class="left">
    <div class="video-wrap">
      <img id="stream" src="/video_feed" alt="Camera Stream">
      <div class="video-label">🔴 LIVE · RTSP /onvif1 · H.265</div>
    </div>
    <div class="log-wrap">
      <h3>📋 Log de Respostas</h3>
      <div id="log"></div>
    </div>
  </div>
  
  <div class="right">
    <div class="panel">
      <h2>📡 Portas</h2>
      <div class="ports" id="ports">Escaneando...</div>
      <div style="margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
        <button class="quick-btn" onclick="qc('http_50000_root')">🌐 HTTP GET :50000</button>
        <button class="quick-btn" onclick="qc('onvif_50000_date')">🕒 ONVIF :50000 Date</button>
      </div>
    </div>
    
    <div class="panel">
      <h2>⚡ Comandos Rápidos</h2>
      <div class="quick-btns">
        <button class="quick-btn ptz" onclick="qc('ptz_up')">⬆️ Up</button>
        <button class="quick-btn ptz" onclick="qc('ptz_down')">⬇️ Down</button>
        <button class="quick-btn ptz" onclick="qc('ptz_left')">⬅️ Left</button>
        <button class="quick-btn ptz" onclick="qc('ptz_right')">➡️ Right</button>
        <button class="quick-btn ptz" onclick="qc('ptz_stop')">🛑 Stop</button>
        <button class="quick-btn ptz" onclick="qc('ptz_zoom_in')">🔍 Zoom</button>
        <button class="quick-btn light" onclick="qc('light_on')">💡 Luz ON</button>
        <button class="quick-btn light" onclick="qc('light_off')">🌑 Luz OFF</button>
        <button class="quick-btn" onclick="qc('get_info')">ℹ️ Info</button>
        <button class="quick-btn" onclick="qc('get_abilities')">🔧 Abilities</button>
        <button class="quick-btn" onclick="qc('get_channels')">📺 Channels</button>
        <button class="quick-btn" onclick="qc('get_encode')">🎬 Encode</button>
        <button class="quick-btn full" onclick="qc('describe')">📜 RTSP DESCRIBE</button>
        <button class="quick-btn full danger" onclick="qc('scan_ports_full')">📡 Full Port Scan (1-65535)</button>
      </div>
    </div>
    
    <div class="panel">
      <h2>🛠️ Manual</h2>
      <div class="form-group">
        <label>Protocolo</label>
        <select id="proto">
          <option value="rtsp_user_cmd">RTSP USER_CMD_SET</option>
          <option value="rtsp_set_param">RTSP SET_PARAMETER</option>
          <option value="rtsp_get_param">RTSP GET_PARAMETER</option>
          <option value="rtsp_describe">RTSP DESCRIBE</option>
          <option value="http_get">HTTP GET (path=porta/caminho) ex: 50000/onvif/device_service</option>
          <option value="http_post_onvif">ONVIF POST (path=porta/caminho)</option>
          <option value="tcp_raw">TCP Raw (porta)</option>
        </select>
      </div>
      <div class="form-group">
        <label>Path/Porta</label>
        <input type="text" id="path" value="/onvif1">
      </div>
      <div class="form-group">
        <label>Body</label>
        <textarea id="body" placeholder='{"Name":"Camera.WhiteLight"}'></textarea>
      </div>
      <button class="send-btn" id="sendBtn" onclick="sendManual()">🚀 Enviar</button>
    </div>
  </div>
</div>

<script>
const ONVIF_DATE_PAYLOAD = `<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body><tds:GetSystemDateAndTime/></s:Body>
</s:Envelope>`;

const Q={
  ptz_left:  {p:'rtsp_user_cmd',b:JSON.stringify({Name:'OPPTZControl',OPPTZControl:{Command:'DirectionLeft',Parameter:{Channel:0,Step:5,Pattern:'SetBegin',Preset:-1,MenuOpts:0,Tour:0}}})},
  ptz_right: {p:'rtsp_user_cmd',b:JSON.stringify({Name:'OPPTZControl',OPPTZControl:{Command:'DirectionRight',Parameter:{Channel:0,Step:5,Pattern:'SetBegin',Preset:-1,MenuOpts:0,Tour:0}}})},
  ptz_up:    {p:'rtsp_user_cmd',b:JSON.stringify({Name:'OPPTZControl',OPPTZControl:{Command:'DirectionUp',Parameter:{Channel:0,Step:5,Pattern:'SetBegin',Preset:-1,MenuOpts:0,Tour:0}}})},
  ptz_down:  {p:'rtsp_user_cmd',b:JSON.stringify({Name:'OPPTZControl',OPPTZControl:{Command:'DirectionDown',Parameter:{Channel:0,Step:5,Pattern:'SetBegin',Preset:-1,MenuOpts:0,Tour:0}}})},
  ptz_stop:  {p:'rtsp_user_cmd',b:JSON.stringify({Name:'OPPTZControl',OPPTZControl:{Command:'DirectionUp',Parameter:{Channel:0,Step:0,Pattern:'Stop',Preset:-1,MenuOpts:0,Tour:0}}})},
  ptz_zoom_in:{p:'rtsp_user_cmd',b:JSON.stringify({Name:'OPPTZControl',OPPTZControl:{Command:'ZoomWide',Parameter:{Channel:0,Step:5,Pattern:'SetBegin',Preset:-1,MenuOpts:0,Tour:0}}})},
  light_on:  {p:'rtsp_user_cmd',b:JSON.stringify({Name:'Camera.WhiteLight',"Camera.WhiteLight":{Enable:true}})},
  light_off: {p:'rtsp_user_cmd',b:JSON.stringify({Name:'Camera.WhiteLight',"Camera.WhiteLight":{Enable:false}})},
  get_info:  {p:'rtsp_user_cmd',b:JSON.stringify({Name:'SystemInfo'})},
  get_abilities:{p:'rtsp_user_cmd',b:JSON.stringify({Name:'SystemFunction'})},
  get_channels:{p:'rtsp_user_cmd',b:JSON.stringify({Name:'ChannelTitle'})},
  get_encode:{p:'rtsp_user_cmd',b:JSON.stringify({Name:'Simplify.Encode'})},
  describe:  {p:'rtsp_describe',b:''},
  scan_ports_full:{p:'scan_full',b:''},
  http_50000_root:{p:'http_get',path:'50000/',b:''},
  onvif_50000_date:{p:'http_post_onvif',path:'50000/onvif/device_service',b:ONVIF_DATE_PAYLOAD},
};

function log(label,ok,content,req=''){
  const el=document.getElementById('log');
  const t=new Date().toLocaleTimeString();
  let h=`<div class="log-entry"><span class="ts">${t}</span> <span class="${ok?'ok':'err'}">${label}</span>`;
  if(req)h+=`<pre>📤 ${req.substring(0,100)}</pre>`;
  h+=`<pre>📥 ${content}</pre></div>`;
  el.innerHTML=h+el.innerHTML;
}

async function qc(n){
  const c=Q[n];
  if(c.p==='scan_full'){scanFull();return;}
  const reqPath = c.path || '/onvif1';
  const r=await fetch('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({protocol:c.p,path:reqPath,body:c.b})});
  const d=await r.json();
  log(n,d.ok,d.response||d.error||JSON.stringify(d),c.b.substring(0,80));
}

async function sendManual(){
  const btn=document.getElementById('sendBtn');
  btn.disabled=true;btn.textContent='⏳...';
  const r=await fetch('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({protocol:document.getElementById('proto').value,path:document.getElementById('path').value,body:document.getElementById('body').value})});
  const d=await r.json();
  log('MANUAL',d.ok,d.response||d.hex||d.error||JSON.stringify(d,null,2),document.getElementById('body').value.substring(0,100));
  btn.disabled=false;btn.textContent='🚀 Enviar';
}

async function scanPorts(){
  const r=await fetch('/api/scan');
  const d=await r.json();
  document.getElementById('ports').innerHTML=Object.entries(d).map(([p,o])=>`<div class="port ${o?'open':'closed'}">${p}</div>`).join('');
}

async function scanFull(){
  log('SCAN','ok','Escaneando 1-65535... aguarde');
  const r=await fetch('/api/scan_full');
  const d=await r.json();
  log('SCAN_FULL',true,'Portas abertas: '+JSON.stringify(d.open_ports));
}

scanPorts();
</script>
</body>
</html>
"""

# ---- API Routes ----

@app.route("/")
def index():
    return render_template_string(HTML, cam_ip=CAM_IP)

@app.route("/video_feed")
def video_feed():
    return Response(gen_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/scan")
def api_scan():
    return jsonify(scan_ports())

@app.route("/api/scan_full")
def api_scan_full():
    """Scan completo de portas (1-65535)."""
    open_ports = []
    for p in range(1, 65536):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        if s.connect_ex((CAM_IP, p)) == 0:
            open_ports.append(p)
        s.close()
    return jsonify({"open_ports": open_ports})

@app.route("/api/send", methods=["POST"])
def api_send():
    data = request.json
    protocol = data.get("protocol", "rtsp_user_cmd")
    path = data.get("path", "/onvif1")
    body = data.get("body", "")
    
    if protocol == "rtsp_user_cmd":
        return jsonify(rtsp_send("USER_CMD_SET", path, body))
    elif protocol == "rtsp_set_param":
        return jsonify(rtsp_send("SET_PARAMETER", path, body, "text/parameters"))
    elif protocol == "rtsp_get_param":
        return jsonify(rtsp_send("GET_PARAMETER", path, body))
    elif protocol == "rtsp_describe":
        return jsonify(rtsp_send("DESCRIBE", path, "", "application/sdp"))
    elif protocol == "http_get":
        parts = path.split('/', 1)
        port = int(parts[0]) if parts[0].isdigit() else 80
        req_path = '/' + (parts[1] if len(parts) > 1 else '')
        return jsonify(http_onvif_send(port, req_path, method="GET"))
    elif protocol == "http_post_onvif":
        parts = path.split('/', 1)
        port = int(parts[0]) if parts[0].isdigit() else 80
        req_path = '/' + (parts[1] if len(parts) > 1 else 'onvif/device_service')
        return jsonify(http_onvif_send(port, req_path, body, method="POST"))
    elif protocol == "tcp_raw":
        port = int(path) if path.isdigit() else 5000
        try:
            raw = bytes.fromhex(body) if body and all(c in "0123456789abcdefABCDEF " for c in body.replace(" ","")) else body.encode()
        except:
            raw = body.encode()
        return jsonify(tcp_send(port, raw))
    
    return jsonify({"ok": False, "error": "Protocolo desconhecido"})

if __name__ == "__main__":
    video.start()
    print(f"\n🔬 Camera Lab iniciado!")
    print(f"📡 Câmera: {CAM_IP} (Jortan JT-8695)")
    print(f"🎬 Stream: {RTSP_URL}")
    print(f"🌐 Acesse: http://localhost:5555\n")
    app.run(host="0.0.0.0", port=5555, debug=False, threaded=True)
