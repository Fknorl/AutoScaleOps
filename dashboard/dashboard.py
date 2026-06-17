"""
AutoScaleOps Professional Dashboard v3.0
Redesigned with Syne + DM Mono — Industrial Terminal Aesthetic
"""

import json, os, shutil, socket, sqlite3, subprocess, threading, time, logging, calendar, io
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════
_log_dir = Path.home() / ".autoscaleops" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(_log_dir / "dashboard.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# INSTANCE CONFIG — load from ~/.autoscaleops/instance.json
# ═══════════════════════════════════════════════════════════════════════════
def _load_instance() -> dict:
    f = Path.home() / ".autoscaleops" / "instance.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {"instance_id": "unknown", "namespace": "autoscaleops-unknown", "minikube_profile": "autoscaleops-unknown"}

_INSTANCE      = _load_instance()
INSTANCE_ID    = _INSTANCE.get("instance_id", "unknown")
NAMESPACE      = _INSTANCE.get("namespace", f"autoscaleops-{INSTANCE_ID}")
KUBE_PROFILE   = _INSTANCE.get("minikube_profile", f"autoscaleops-{INSTANCE_ID}")

def _load_active_project() -> dict:
    """~/.autoscaleops/active_project.json'dan aktif proje bilgisini yükle.
    PyQt6 app'in yazdığı bu dosyayı okuyarak hangi projenin aktif olduğunu öğreniriz."""
    f = Path.home() / ".autoscaleops" / "active_project.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": "autoscaleops-app", "port": 8080, "service_name": "autoscaleops-app-service"}

_ACTIVE_PROJECT = _load_active_project()

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AutoScaleOps",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': "AutoScaleOps v3.0"}
)

# ═══════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM — Syne + DM Mono, lime-on-black terminal aesthetic
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&display=swap');

:root {
  --bg:       #06060f;
  --surface:  rgba(255,255,255,0.035);
  --border:   rgba(255,255,255,0.07);
  --accent:   #a3e635;
  --accent2:  #22d3ee;
  --accent3:  #f97316;
  --text:     #e2e8f0;
  --muted:    #64748b;
  --ok:       #4ade80;
  --warn:     #fbbf24;
  --err:      #f87171;
  --radius:   12px;
}

html, body, .stApp {
  background: var(--bg) !important;
  font-family: 'DM Mono', monospace !important;
  color: var(--text) !important;
}

/* Grid bg */
.stApp::before {
  content: '';
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background-image:
    linear-gradient(rgba(163,230,53,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(163,230,53,0.025) 1px, transparent 1px);
  background-size: 44px 44px;
}

/* Top orb */
.stApp::after {
  content: '';
  position: fixed; top: -300px; right: -200px;
  width: 700px; height: 700px;
  background: radial-gradient(circle, rgba(163,230,53,0.05) 0%, transparent 65%);
  border-radius: 50%; pointer-events: none; z-index: 0;
}

/* ── Typography ── */
.dash-title {
  font-family: 'Syne', sans-serif;
  font-weight: 800;
  font-size: 2.6rem;
  letter-spacing: -1.5px;
  line-height: 1.1;
  color: var(--text);
  margin-bottom: 6px;
}
.dash-title span { color: var(--accent); }
.dash-subtitle {
  font-family: 'DM Mono', monospace;
  font-size: 0.8rem;
  color: var(--muted);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 32px;
}

.section-label {
  font-family: 'Syne', sans-serif;
  font-weight: 700;
  font-size: 0.65rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

.section-title {
  font-family: 'Syne', sans-serif;
  font-weight: 800;
  font-size: 1.4rem;
  letter-spacing: -0.5px;
  color: var(--text);
  margin: 28px 0 14px 0;
}

/* ── Metric Cards ── */
.metric-block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.25s;
}
.metric-block:hover { border-color: rgba(163,230,53,0.25); }
.metric-block::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  opacity: 0.6;
}
.metric-label {
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
  font-family: 'DM Mono', monospace;
}
.metric-value {
  font-family: 'Syne', sans-serif;
  font-weight: 800;
  font-size: 2.4rem;
  letter-spacing: -1px;
  color: var(--accent);
  line-height: 1;
}
.metric-delta {
  font-size: 0.72rem;
  color: var(--muted);
  margin-top: 6px;
}
.metric-delta.up { color: var(--ok); }
.metric-delta.down { color: var(--err); }

/* ── Status Pills ── */
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 99px;
  font-family: 'DM Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  border: 1px solid;
  letter-spacing: 0.04em;
}
.pill-ok   { background: rgba(74,222,128,0.08);  border-color: rgba(74,222,128,0.25);  color: var(--ok); }
.pill-err  { background: rgba(248,113,113,0.08); border-color: rgba(248,113,113,0.25); color: var(--err); }
.pill-warn { background: rgba(251,191,36,0.08);  border-color: rgba(251,191,36,0.25);  color: var(--warn); }
.pill-info { background: rgba(34,211,238,0.08);  border-color: rgba(34,211,238,0.25);  color: var(--accent2); }

/* ── Alert Boxes ── */
.alert {
  border-radius: var(--radius);
  padding: 14px 18px;
  margin: 12px 0;
  font-size: 0.83rem;
  border-left: 3px solid;
  line-height: 1.6;
}
.alert-ok   { background: rgba(74,222,128,0.06);  border-color: var(--ok);   color: #bbf7d0; }
.alert-err  { background: rgba(248,113,113,0.06); border-color: var(--err);  color: #fecaca; }
.alert-warn { background: rgba(251,191,36,0.06);  border-color: var(--warn); color: #fef08a; }
.alert-info { background: rgba(34,211,238,0.06);  border-color: var(--accent2); color: #a5f3fc; }

/* ── Event Cards ── */
.ev-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  margin: 8px 0;
  border-left: 3px solid var(--accent);
  transition: all 0.2s;
}
.ev-card:hover { border-color: var(--accent); background: rgba(163,230,53,0.04); }
.ev-card.special { border-left-color: var(--accent2); }
.ev-card.danger  { border-left-color: var(--err); }
.ev-name { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 1rem; margin-bottom: 4px; }
.ev-meta { font-size: 0.75rem; color: var(--muted); line-height: 1.6; }

/* ── Upcoming events strip ── */
.upcoming-strip {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 12px 0 24px 0;
}
.upcoming-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(163,230,53,0.06);
  border: 1px solid rgba(163,230,53,0.15);
  border-radius: 8px;
  font-size: 0.76rem;
  transition: all 0.2s;
}
.upcoming-chip:hover { background: rgba(163,230,53,0.1); }
.upcoming-chip .days {
  font-family: 'Syne', sans-serif;
  font-weight: 800;
  font-size: 1rem;
  color: var(--accent);
}
.upcoming-chip .name { color: var(--text); }
.upcoming-chip .level { color: var(--muted); font-size: 0.7rem; }

/* ── Buttons ── */
.stButton > button {
  background: rgba(163,230,53,0.08) !important;
  color: var(--accent) !important;
  border: 1px solid rgba(163,230,53,0.25) !important;
  border-radius: var(--radius) !important;
  font-family: 'Syne', sans-serif !important;
  font-weight: 700 !important;
  font-size: 0.82rem !important;
  letter-spacing: 0.04em !important;
  transition: all 0.2s !important;
  padding: 10px 20px !important;
}
.stButton > button:hover {
  background: rgba(163,230,53,0.14) !important;
  border-color: rgba(163,230,53,0.5) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 16px rgba(163,230,53,0.15) !important;
}
.stButton > button[kind="primary"] {
  background: var(--accent) !important;
  color: #0a0a0a !important;
  border-color: var(--accent) !important;
}
.stButton > button[kind="primary"]:hover {
  background: #b5f548 !important;
  box-shadow: 0 4px 20px rgba(163,230,53,0.3) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  gap: 4px !important;
  background: rgba(255,255,255,0.03) !important;
  padding: 6px !important;
  border-radius: var(--radius) !important;
  border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  border-radius: 8px !important;
  padding: 8px 18px !important;
  font-family: 'DM Mono', monospace !important;
  font-size: 0.78rem !important;
  color: var(--muted) !important;
  transition: all 0.2s !important;
  border: 1px solid transparent !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text) !important; }
.stTabs [aria-selected="true"] {
  background: rgba(163,230,53,0.1) !important;
  border-color: rgba(163,230,53,0.25) !important;
  color: var(--accent) !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea textarea,
.stSelectbox > div > div > div {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  color: var(--text) !important;
  font-family: 'DM Mono', monospace !important;
  font-size: 0.85rem !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
  border-color: rgba(163,230,53,0.4) !important;
  box-shadow: 0 0 0 3px rgba(163,230,53,0.08) !important;
}

/* ── Metrics override ── */
[data-testid="stMetricValue"] {
  font-family: 'Syne', sans-serif !important;
  font-weight: 800 !important;
  font-size: 2rem !important;
  color: var(--accent) !important;
}
[data-testid="stMetricLabel"] {
  font-family: 'DM Mono', monospace !important;
  font-size: 0.72rem !important;
  color: var(--muted) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
}

/* ── Divider ── */
hr {
  border: none !important;
  height: 1px !important;
  background: var(--border) !important;
  margin: 24px 0 !important;
}

/* ── Progress ── */
.stProgress > div > div > div {
  background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
  border-radius: 99px !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(163,230,53,0.3); }

/* ── K6 ── */
.k6-card {
  background: rgba(74,222,128,0.05);
  border: 1px solid rgba(74,222,128,0.2);
  border-radius: var(--radius);
  padding: 20px;
  margin: 12px 0;
}
.k6-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 16px;
}
.k6-stat {
  text-align: center;
  background: rgba(0,0,0,0.3);
  border-radius: 8px;
  padding: 12px;
}
.k6-stat-val {
  font-family: 'Syne', sans-serif;
  font-weight: 800;
  font-size: 1.6rem;
  color: var(--ok);
}
.k6-stat-lbl { font-size: 0.68rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }

/* ── Info panels ── */
.info-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  margin: 10px 0;
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--muted);
}
.info-panel strong { color: var(--text); }

/* ── Connection bar ── */
.conn-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 24px;
}
.conn-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.conn-dot.ok   { background: var(--ok);   box-shadow: 0 0 6px var(--ok); }
.conn-dot.err  { background: var(--err);  box-shadow: 0 0 6px var(--err); }
.conn-name { font-size: 0.78rem; color: var(--muted); }

#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
PROMETHEUS_HOST  = os.getenv("PROMETHEUS_HOST",  "127.0.0.1")
PROMETHEUS_PORT  = int(os.getenv("PROMETHEUS_PORT",  "9090"))
PUSHGATEWAY_HOST = os.getenv("PUSHGATEWAY_HOST", "127.0.0.1")
PUSHGATEWAY_PORT = int(os.getenv("PUSHGATEWAY_PORT", "9091"))
APP_HOST         = os.getenv("APP_HOST",         "127.0.0.1")
APP_PORT         = int(os.getenv("APP_PORT", str(_ACTIVE_PROJECT.get("port", 8080))))

SERVICES = {
    "prometheus":  {"host": PROMETHEUS_HOST,  "port": PROMETHEUS_PORT,  "health": "/-/ready"},
    "pushgateway": {"host": PUSHGATEWAY_HOST, "port": PUSHGATEWAY_PORT, "health": "/-/ready"},
    "app":         {"host": APP_HOST,         "port": APP_PORT,         "health": "/health"},
}
URLS = {name: f"http://{cfg['host']}:{cfg['port']}" for name, cfg in SERVICES.items()}
PUSHGATEWAY_TARGET = f"{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}"

STATE_DIR         = Path.home() / ".autoscaleops" / ".dashboard_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
AI_STATE_FILE     = STATE_DIR / "ai_state.json"
EVENTS_FILE       = STATE_DIR / "events.json"
HISTORY_FILE      = STATE_DIR / "metrics_history.json"
GREENOPS_FILE     = STATE_DIR / "greenops_config.json"
SPECIAL_DAYS_FILE = STATE_DIR / "special_days.json"

COST_PER_POD_HOUR  = 0.04
CONNECTION_TIMEOUT = 5
MAX_RETRIES        = 3

TRAFFIC_LEVEL_MAP = {
    "cok_yuksek": ("Cok Yuksek", 1.80, "#f87171"),
    "yuksek":     ("Yuksek",     1.50, "#fbbf24"),
    "orta":       ("Orta",       1.30, "#a3e635"),
    "dusuk":      ("Dusuk",      1.15, "#4ade80"),
    # Turkish variants
    "çok_yüksek": ("Cok Yuksek", 1.80, "#f87171"),
    "yüksek":     ("Yuksek",     1.50, "#fbbf24"),
    "düşük":      ("Dusuk",      1.15, "#4ade80"),
}

SPECIAL_DAYS_DATA = [
    {"date": "02-14", "name": "Sevgililer Gunu",    "traffic_level": "çok_yüksek", "reason": "Hediye, cicek, takim, kampanya"},
    {"date": "03-08", "name": "Dunya Kadinlar Gunu","traffic_level": "yüksek",     "reason": "Hediye, kozmetik kampanyalari"},
    {"date": "05-02", "name": "Anneler Gunu",        "traffic_level": "çok_yüksek", "reason": "Yilin en buyuk hediye donemlerinden"},
    {"date": "06-16", "name": "Babalar Gunu",        "traffic_level": "yüksek",     "reason": "Elektronik, giyim urunleri"},
    {"date": "11-29", "name": "Black Friday",        "traffic_level": "çok_yüksek", "reason": "Yilin en yuksek e-ticaret trafigi"},
    {"date": "11-25", "name": "Cyber Monday",        "traffic_level": "çok_yüksek", "reason": "Online alisveris odakli ekstrem trafik"},
    {"date": "12-12", "name": "12.12 Kampanyasi",    "traffic_level": "yüksek",     "reason": "Pazaryeri agresif kampanyalari"},
    {"date": "01-01", "name": "Yilbasi",             "traffic_level": "çok_yüksek", "reason": "Hediye, dekorasyon, eglence"},
    {"date": "09-01", "name": "Okula Donus",         "traffic_level": "çok_yüksek", "reason": "Kirtasiye, elektronik, giyim"},
    {"date": "11-11", "name": "11.11 Kampanyasi",    "traffic_level": "yüksek",     "reason": "Global indirimler"},
    {"date": "12-25", "name": "Noel",                "traffic_level": "çok_yüksek", "reason": "Global hediye trafigi"},
    {"date": "07-01", "name": "Yaz Indirimleri",     "traffic_level": "yüksek",     "reason": "Sezon indirimi"},
]

# ═══════════════════════════════════════════════════════════════════════════
# CONNECTION MANAGER
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class ConnStatus:
    prometheus: bool  = False
    pushgateway: bool = False
    app: bool         = False
    last_check: datetime = None


class ConnectionManager:
    def __init__(self): self.status = ConnStatus()

    def _tcp(self, host, port, timeout=5):
        try:
            with socket.create_connection((host, int(port)), timeout=timeout): return True
        except: return False

    def _current_app_port(self) -> int:
        """active_project.json'dan güncel portu oku (başlatıldıktan sonra değişebilir)."""
        try:
            ap = _load_active_project()
            return int(ap.get("port", APP_PORT))
        except:
            return APP_PORT

    def check(self, service, timeout=CONNECTION_TIMEOUT):
        if service == "app":
            # APP_PORT modül yüklenirken okundu; güncel değeri her seferinde oku
            port = self._current_app_port()
            url  = f"http://{APP_HOST}:{port}"
            try:
                r = requests.get(f"{url}/health", timeout=timeout)
                if r.status_code < 500: return True
            except: pass
            # /health yoksa kök dizini dene
            try:
                r = requests.get(url, timeout=timeout)
                if r.status_code < 500: return True
            except: pass
            return self._tcp(APP_HOST, port, timeout)
        cfg = SERVICES.get(service)
        if not cfg: return False
        try:
            r = requests.get(f"{URLS[service]}{cfg['health']}", timeout=timeout)
            if r.status_code < 500: return True
        except: pass
        return self._tcp(cfg["host"], cfg["port"], timeout)

    def check_all(self):
        self.status.prometheus  = self.check("prometheus")
        self.status.pushgateway = self.check("pushgateway")
        self.status.app         = self.check("app")
        self.status.last_check  = datetime.now()
        return self.status

    def all_ok(self): return self.status.prometheus and self.status.pushgateway and self.status.app
    def disconnected(self):
        d = []
        if not self.status.prometheus:  d.append("prometheus")
        if not self.status.pushgateway: d.append("pushgateway")
        if not self.status.app:         d.append("app")
        return d

    def retry(self, service, retries=3):
        for _ in range(retries):
            for _ in range(4):
                time.sleep(1)
                if self.check(service): return True
        return False


conn_mgr = ConnectionManager()

# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def run_ps(cmd: str, timeout=15) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout
        )
        return r.stdout.strip()
    except Exception as e:
        logger.error(f"PS error: {e}")
        return ""


def restart_port_forwards() -> None:
    """kubectl port-forward süreçlerini öldürüp yeniden başlat.

    Servis portu (dış) ile container portu farklı olabilir; bu yüzden
    port-forward'u servis adresine yapıyoruz — Kubernetes proxy otomatik yönlendirir.
    """
    ns = NAMESPACE
    # Önce tüm kubectl süreçlerini temizle
    run_ps("Get-Process kubectl -ErrorAction SilentlyContinue | Stop-Process -Force")
    time.sleep(2)
    # Aktif proje bilgisini taze oku
    _ap       = _load_active_project()
    _app_svc  = _ap.get("service_name", "autoscaleops-app-service")
    _app_port = int(_ap.get("port", 8080))  # Kullanıcının belirlediği port (K8s service port)

    # Boş port bul (çakışma önleme)
    def _free(preferred):
        import socket as _s
        for p in [preferred] + list(range(preferred + 1, preferred + 220)):
            try:
                with _s.socket(_s.AF_INET, _s.SOCK_STREAM) as s:
                    s.setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 1)
                    s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
        return preferred

    prom_port = _free(9090)
    pgw_port  = _free(9091)
    app_port  = _free(_app_port)

    forwards = [
        f"port-forward svc/prometheus-kube-prometheus-prometheus {prom_port}:9090 -n monitoring",
        f"port-forward svc/prometheus-pushgateway {pgw_port}:9091 -n monitoring",
        f"port-forward svc/{_app_svc} {app_port}:{_app_port} -n {ns}",
    ]
    for args in forwards:
        run_ps(f"Start-Process kubectl -ArgumentList '{args}' -WindowStyle Hidden")
        time.sleep(1)
    logger.info(f"Port-forwards restarted — app:{app_port}, prom:{prom_port}, pgw:{pgw_port}")


def get_pod_count() -> int:
    try:
        # Aktif projenin adını her seferinde taze oku
        active_name = _load_active_project().get("name", "autoscaleops-app")
        res = run_ps(
            f"kubectl get pods -n {NAMESPACE} -l app={active_name} "
            "--no-headers 2>$null | Measure-Object | Select-Object -ExpandProperty Count"
        )
        return int(res) if res and res.isdigit() else 0
    except: return 0


def get_keda_status() -> Tuple[bool, str]:
    try:
        res = run_ps(f"kubectl get scaledobject -n {NAMESPACE} --no-headers 2>$null")
        if res and "autoscaleops" in res.lower():
            return True, "Active"
        return False, "Inactive"
    except: return False, "Error"


def toggle_autoscaling(enable: bool) -> Tuple[bool, str]:
    try:
        if enable:
            chart = Path("charts") / "autoscaleops" / "templates" / "keda-scaledobject.yaml"
            if chart.exists():
                run_ps(f"kubectl apply -f {chart} -n {NAMESPACE}")
            return True, "KEDA enabled"
        else:
            run_ps(f"kubectl delete scaledobject --all -n {NAMESPACE} --ignore-not-found")
            run_ps(f"kubectl scale deployment autoscaleops-deployment --replicas=1 -n {NAMESPACE}")
            return True, "KEDA disabled"
    except Exception as e: return False, str(e)

# ═══════════════════════════════════════════════════════════════════════════
# PROMETHEUS
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=2)
def fetch_metric(query: str) -> float:
    try:
        r = requests.get(f"{URLS['prometheus']}/api/v1/query",
                         params={"query": query}, timeout=CONNECTION_TIMEOUT)
        if r.status_code == 200:
            d = r.json()
            if d["status"] == "success" and d["data"]["result"]:
                return float(d["data"]["result"][0]["value"][1])
    except Exception as e: logger.warning(f"fetch_metric error: {e}")
    return 0.0


@st.cache_data(ttl=3)
def fetch_timeseries(query: str, minutes: int = 30, step: str = "30s") -> List[Tuple]:
    try:
        end = int(time.time())
        r = requests.get(f"{URLS['prometheus']}/api/v1/query_range",
                         params={"query": query, "start": end - minutes*60, "end": end, "step": step},
                         timeout=CONNECTION_TIMEOUT)
        if r.status_code == 200:
            d = r.json()
            if d["status"] == "success" and d["data"]["result"]:
                return [(float(ts), float(v)) for ts, v in d["data"]["result"][0]["values"]]
    except Exception as e: logger.warning(f"fetch_timeseries error: {e}")
    return []


def get_all_metric_names() -> List[str]:
    """Get all available metric names from Prometheus — helps debug traffic"""
    try:
        r = requests.get(f"{URLS['prometheus']}/api/v1/label/__name__/values",
                         timeout=CONNECTION_TIMEOUT)
        if r.status_code == 200:
            return r.json().get("data", [])
    except: pass
    return []

# ═══════════════════════════════════════════════════════════════════════════
# DATA MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════
def save_history(real: float, pred: float, pods: int, cost: float):
    try:
        hist = []
        if HISTORY_FILE.exists():
            try: hist = json.loads(HISTORY_FILE.read_text())
            except: pass
        if len(hist) >= 1000: hist = hist[-999:]
        hist.append({"timestamp": datetime.now().isoformat(),
                      "real_rps": real, "pred_rps": pred,
                      "pods": pods, "cost_hour": cost})
        HISTORY_FILE.write_text(json.dumps(hist, indent=2))
    except Exception as e: logger.error(f"save_history: {e}")


def get_history(days=7) -> List[Dict]:
    if not HISTORY_FILE.exists(): return []
    try:
        hist = json.loads(HISTORY_FILE.read_text())
        cutoff = datetime.now() - timedelta(days=days)
        return [h for h in hist if datetime.fromisoformat(h["timestamp"]) >= cutoff]
    except: return []


def load_special_days() -> List[Dict]:
    if not SPECIAL_DAYS_FILE.exists():
        SPECIAL_DAYS_FILE.write_text(json.dumps(SPECIAL_DAYS_DATA, indent=2, ensure_ascii=False))
    try: return json.loads(SPECIAL_DAYS_FILE.read_text())
    except: return SPECIAL_DAYS_DATA


def get_upcoming_special(days_ahead=14) -> List[Dict]:
    today = date.today()
    out   = []
    for d in load_special_days():
        try:
            m, dn = map(int, d["date"].split("-"))
            ev    = date(today.year, m, dn)
            if ev < today: ev = date(today.year+1, m, dn)
            diff  = (ev - today).days
            if 0 <= diff <= days_ahead:
                out.append({**d, "days_until": diff, "event_date": ev.isoformat()})
        except: pass
    return sorted(out, key=lambda x: x["days_until"])


def load_events() -> List[Dict]:
    if EVENTS_FILE.exists():
        try: return json.loads(EVENTS_FILE.read_text())
        except: return []
    return []


def save_events(evs): 
    EVENTS_FILE.write_text(json.dumps(evs, indent=2, ensure_ascii=False))


def add_event(ev):    save_events(load_events() + [ev])
def delete_event(i):
    evs = load_events()
    if 0 <= i < len(evs): evs.pop(i); save_events(evs); return True
    return False
def update_event(i, ev):
    evs = load_events()
    if 0 <= i < len(evs): evs[i] = ev; save_events(evs); return True
    return False


def get_upcoming_user_events(days=7) -> List[Dict]:
    today = date.today()
    out   = []
    for ev in load_events():
        try:
            s = datetime.fromisoformat(ev["baslangic"]).date()
            if today < s <= today + timedelta(days=days):
                out.append({**ev, "days_until": (s - today).days})
        except: pass
    return sorted(out, key=lambda x: x["days_until"])


# ── AI Profil Köprüsü ────────────────────────────────────────────────────────
_AI_DB        = Path.home() / ".autoscaleops" / "autoscaleops.db"
_PROFILE_PATH = Path.home() / ".autoscaleops" / "domain_profile.json"

LEVEL_TO_MARGIN = {
    "Low": 0.15, "Medium": 0.30, "High": 0.50, "Very High": 0.80,
    "Dusuk": 0.15, "Orta": 0.30, "Yuksek": 0.50, "Cok Yuksek": 0.80,
    "dusuk": 0.15, "orta": 0.30, "yuksek": 0.50, "cok_yuksek": 0.80,
    "çok_yüksek": 0.80, "yüksek": 0.50, "düşük": 0.15,
}


def _ai_sync_profile(conn) -> None:
    """domain_events → domain_profile.json (predictor.py'nin okuduğu dosya)."""
    try:
        rows = conn.execute(
            "SELECT name, event_date, safety_margin FROM domain_events ORDER BY event_date"
        ).fetchall()
        events = [{"name": r[0], "date": r[1], "margin": r[2]} for r in rows]
        profile: dict = {"hours": {str(h): 1.0 for h in range(24)}, "events": events}
        if _PROFILE_PATH.exists():
            try:
                existing = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
                profile["hours"] = existing.get("hours", profile["hours"])
            except Exception:
                pass
        _PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"_ai_sync_profile hata: {e}")


def ai_get_applied() -> set:
    """domain_events'ten kayıtlı (name, date) çiftlerini döner."""
    if not _AI_DB.exists():
        return set()
    try:
        conn = sqlite3.connect(str(_AI_DB))
        rows = conn.execute("SELECT name, event_date FROM domain_events").fetchall()
        conn.close()
        return {(r[0], r[1]) for r in rows}
    except Exception:
        return set()


def ai_apply_event(name: str, event_date: str, margin: float) -> bool:
    """Etkinliği domain_events tablosuna yazar ve domain_profile.json günceller."""
    if not _AI_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(_AI_DB))
        existing = conn.execute(
            "SELECT id FROM domain_events WHERE name=? AND event_date=?", (name, event_date)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE domain_events SET safety_margin=? WHERE name=? AND event_date=?",
                (margin, name, event_date),
            )
        else:
            conn.execute(
                "INSERT INTO domain_events (name, event_date, safety_margin, notes) VALUES (?,?,?,?)",
                (name, event_date, margin, "Dashboard'dan eklendi"),
            )
        conn.commit()
        _ai_sync_profile(conn)
        conn.close()
        return True
    except Exception as e:
        logger.error(f"ai_apply_event hata: {e}")
        return False


def ai_remove_event(name: str, event_date: str) -> bool:
    """Etkinliği domain_events tablosundan siler ve domain_profile.json günceller."""
    if not _AI_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(_AI_DB))
        conn.execute("DELETE FROM domain_events WHERE name=? AND event_date=?", (name, event_date))
        conn.commit()
        _ai_sync_profile(conn)
        conn.close()
        return True
    except Exception as e:
        logger.error(f"ai_remove_event hata: {e}")
        return False


def load_greenops() -> Dict:
    if GREENOPS_FILE.exists():
        try: return json.loads(GREENOPS_FILE.read_text())
        except: pass
    return {}


def save_greenops(cfg): GREENOPS_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

# ═══════════════════════════════════════════════════════════════════════════
# SESSION INIT
# ═══════════════════════════════════════════════════════════════════════════
def init_session():
    defs = {
        "ai_running": True, "k6_running": False, "k6_status": "",
        "k6_started_at": None, "k6_process": None, "k6_duration": 60,
        "events": [], "insight_result": None, "conn_status": ConnStatus(),
        "last_conn_check": None, "editing_idx": None,
        "started_at": datetime.now(),
        "greenops_enabled": False, "greenops_start": "09:00",
        "greenops_end": "18:00", "greenops_offhour_pods": 1,
        "greenops_weekend_pods": 1, "last_scaled_to": None,
        "auto_refresh": False,
    }
    for k, v in defs.items():
        if k not in st.session_state: st.session_state[k] = v
    cfg = load_greenops()
    for key in ["greenops_enabled","greenops_start","greenops_end",
                "greenops_offhour_pods","greenops_weekend_pods"]:
        if key in cfg: st.session_state[key] = cfg[key]
    if not st.session_state["events"]:
        st.session_state["events"] = load_events()

# ═══════════════════════════════════════════════════════════════════════════
# AI ENGINE
# ═══════════════════════════════════════════════════════════════════════════
def calc_prediction(real: float) -> float:
    try:
        ts = fetch_timeseries("sum(rate(http_requests_total[1m]))", minutes=5, step="15s")
        trend = 1.0
        if len(ts) >= 10:
            r = [v for _,v in ts[-5:]]; o = [v for _,v in ts[:5]]
            if o and sum(o)/len(o) > 0: trend = max(0.8, min(sum(r)/len(r)/(sum(o)/len(o)), 1.5))
        pred = real * 1.2 * trend * 1.15
        return max(pred, real * 1.1)
    except: return real * 1.2


def ai_thread():
    reg = CollectorRegistry()
    g   = Gauge("predicted_rps_30min", "AI Predicted RPS", registry=reg)
    logger.info("AI thread started")
    while True:
        try:
            real = fetch_metric("sum(rate(http_requests_total[1m]))")
            g.set(calc_prediction(real))
            try: push_to_gateway(PUSHGATEWAY_TARGET, job="ai_predictor", registry=reg)
            except Exception as e: logger.error(f"Pushgateway: {e}")
        except Exception as e: logger.error(f"AI thread: {e}")
        time.sleep(3)


def ensure_ai_thread():
    alive = any(t.name == "ai-engine" for t in threading.enumerate())
    if not alive:
        t = threading.Thread(target=ai_thread, daemon=True, name="ai-engine")
        t.start()

# ═══════════════════════════════════════════════════════════════════════════
# GREENOPS
# ═══════════════════════════════════════════════════════════════════════════
def apply_greenops():
    if not st.session_state.greenops_enabled: return
    try:
        now     = datetime.now()
        start_t = datetime.strptime(st.session_state.greenops_start, "%H:%M").time()
        end_t   = datetime.strptime(st.session_state.greenops_end,   "%H:%M").time()
        target  = None
        if now.weekday() >= 5:
            target = st.session_state.greenops_weekend_pods
        elif not (start_t <= now.time() <= end_t):
            target = st.session_state.greenops_offhour_pods
        if target is not None and target != st.session_state.last_scaled_to:
            run_ps(f"kubectl delete scaledobject --all -n {NAMESPACE} --ignore-not-found")
            time.sleep(1)
            run_ps(f"kubectl scale deployment autoscaleops-deployment --replicas={target} -n {NAMESPACE}")
            st.session_state.last_scaled_to = target
    except Exception as e: logger.error(f"GreenOps: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# K6
# ═══════════════════════════════════════════════════════════════════════════
def build_k6(url, vus, duration, sleep_gap):
    return f"""import http from 'k6/http';
import {{ sleep }} from 'k6';
export const options = {{
  vus: {vus}, duration: '{duration}s',
  thresholds: {{ http_req_duration: ['p(95)<500'], http_req_failed: ['rate<0.01'] }},
}};
export default function () {{ http.get('{url}'); sleep({sleep_gap}); }}
"""


def start_k6(url, vus, duration, sleep_gap):
    k6p = shutil.which("k6") or shutil.which("k6.exe")
    if not k6p: return False, "k6 bulunamadi. Lutfen k6 yukleyin: https://k6.io/docs/get-started/installation/"
    try:
        s = STATE_DIR / "k6_temp.js"
        s.write_text(build_k6(url, vus, duration, sleep_gap), encoding="utf-8")
        proc = subprocess.Popen([k6p, "run", str(s)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.5)
        if proc.poll() is not None:
            out, err = proc.communicate()
            return False, f"k6 baslatılamadi: {err or out}"
        return True, json.dumps({"pid": proc.pid, "vus": vus, "duration": duration, "sleep": sleep_gap, "started_at": time.time()})
    except Exception as e: return False, str(e)


def check_k6():
    if st.session_state.k6_running and st.session_state.k6_process:
        if st.session_state.k6_process.poll() is not None:
            return False, "Test tamamlandi"
        elapsed   = time.time() - st.session_state.k6_started_at
        remaining = st.session_state.k6_duration - elapsed
        return True, f"Calisıyor — Kalan: {int(remaining)}s"
    return False, "Beklemede"

# ═══════════════════════════════════════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
def analyze_status(real, pred, pods, cost):
    is_keda, _ = get_keda_status()
    rps_pod    = real / pods if pods else 0
    eff        = (real / (pods * 20)) * 100 if pods else 0
    acc        = 100 - (abs(pred - real) / real * 100) if real > 0 else 0
    r = f"""## System Status Report

**Pods:** {pods} active | **Real Traffic:** {real:.2f} RPS | **AI Prediction:** {pred:.2f} RPS
**KEDA:** {"Active" if is_keda else "Inactive"} | **Efficiency:** {eff:.1f}% | **Prediction Accuracy:** {acc:.1f}%

### Cost
- Hourly: ${cost:.2f} | Daily: ${cost*24:.2f} | Monthly: ${cost*24*30:.2f}

### Recommendations
"""
    if rps_pod > 20: r += "- CRITICAL: RPS per pod too high. Scale up immediately.\n"
    elif rps_pod > 15: r += "- WARNING: RPS per pod elevated. Consider scaling.\n"
    elif rps_pod < 5:  r += "- INFO: Resources underutilized. Consider reducing pods.\n"
    else:              r += "- OK: RPS per pod is in optimal range.\n"
    if eff < 40: r += "- OPTIMIZATION: Low resource efficiency detected.\n"
    upcoming = get_upcoming_special(7) + get_upcoming_user_events(7)
    if upcoming:
        r += "\n### Upcoming Events\n"
        for ev in upcoming[:5]:
            r += f"- **{ev.get('name', ev.get('ad', ''))}** in {ev['days_until']} days\n"
    return r


def analyze_weekly(real, pred, pods):
    hist = get_history(7)
    if not hist: return "No data for last 7 days."
    df = pd.DataFrame(hist)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    r_avg = df['real_rps'].tail(3).mean()
    o_avg = df['real_rps'].head(3).mean()
    trend = ((r_avg - o_avg) / o_avg * 100) if o_avg > 0 else 0
    return f"""### Weekly Trend
- Recent 3-day avg: **{r_avg:.2f} RPS** | Start avg: **{o_avg:.2f} RPS**
- Trend: **{trend:+.1f}%**
- Peak: **{df['real_rps'].max():.2f}** | Min: **{df['real_rps'].min():.2f}** | Avg: **{df['real_rps'].mean():.2f}**"""


def analyze_cost(real, pods, cost_h):
    hist = get_history(7)
    savings = 0
    if hist:
        df = pd.DataFrame(hist)
        idle = df[df['real_rps'] < 5]
        savings = len(idle) * COST_PER_POD_HOUR
    rpp = real / pods if pods else 0
    return f"""### Cost Optimization
- Hourly cost: **${cost_h:.2f}** | Idle savings potential: **${savings:.2f}**
- RPS per pod: **{rpp:.2f}** {'— reduce pods' if rpp < 5 and pods > 1 else '— balanced'}"""


def analyze_accuracy(real, pred):
    hist = get_history(7)
    if not hist: return "Insufficient data."
    df   = pd.DataFrame(hist)
    df   = df[df['real_rps'] > 0]
    mape = (abs(df['pred_rps'] - df['real_rps']) / df['real_rps']).mean() * 100 if len(df) else 0
    last = abs(pred - real) / real * 100 if real > 0 else 0
    return f"""### Prediction Accuracy
- 7-day MAPE: **{100-mape:.1f}% accuracy**
- Current error: **{last:.1f}%**"""


def analyze_forecast(real):
    hist = get_history(7)
    if not hist: return "Insufficient data."
    df   = pd.DataFrame(hist)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    daily = df.groupby(df['timestamp'].dt.date)['real_rps'].mean()
    growth = (daily.iloc[-1]-daily.iloc[0])/daily.iloc[0]*100 if len(daily)>1 and daily.iloc[0]>0 else 0
    forecast = max(real, daily.mean()) * (1 + growth/100) * 1.1
    suggested = max(3, int(forecast//10)+1)
    return f"""### Next Week Forecast
- 7-day avg: **{daily.mean():.2f} RPS** | Growth trend: **{growth:+.1f}%**
- Forecast peak (with buffer): **{forecast:.2f} RPS**
- Recommended KEDA maxReplicaCount: **{suggested}**"""

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    init_session()
    ensure_ai_thread()
    apply_greenops()

    # Connection check every 30s — auto port-forward restart if all down
    if (st.session_state.last_conn_check is None or
        (datetime.now() - st.session_state.last_conn_check).seconds > 10):
        conn_mgr.check_all()
        st.session_state.conn_status = conn_mgr.status
        st.session_state.last_conn_check = datetime.now()
        # Auto-recovery: herhangi bir servis ölüyse port-forward'ları otomatik yeniden başlat
        # (Sadece uygulama yeni başlatıldıysa — ilk 2 dakikada)
        if not conn_mgr.all_ok():
            uptime_s = (datetime.now() - st.session_state.get("started_at", datetime.now())).total_seconds()
            if uptime_s < 120:
                logger.info("Service(s) down in startup window — auto-restarting port-forwards")
                restart_port_forwards()
                time.sleep(5)
                conn_mgr.check_all()
                st.session_state.conn_status = conn_mgr.status

    status = st.session_state.conn_status

    # ── HEADER ──────────────────────────────────────────────────────────────
    col_h1, col_h2 = st.columns([3,1])
    with col_h1:
        st.markdown(f"""
        <div class="dash-title">Auto<span>Scale</span>Ops</div>
        <div class="dash-subtitle">AI-Powered Predictive Autoscaling · Kubernetes KEDA · Instance {INSTANCE_ID}</div>
        """, unsafe_allow_html=True)
    with col_h2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh", key="hdr_refresh"):
            fetch_metric.clear(); fetch_timeseries.clear()
            conn_mgr.check_all(); st.session_state.conn_status = conn_mgr.status
            st.rerun()

    # ── CONNECTION BAR ───────────────────────────────────────────────────────
    services_html = ""
    for name, ok in [("Prometheus", status.prometheus), ("Pushgateway", status.pushgateway), ("Application", status.app)]:
        cls = "ok" if ok else "err"
        services_html += f'<div class="conn-dot {cls}"></div><span class="conn-name">{name}</span>'
        if name != "Application": services_html += '<span style="color:var(--border);margin:0 6px">|</span>'

    st.markdown(f'<div class="conn-bar">{services_html}</div>', unsafe_allow_html=True)

    if not conn_mgr.all_ok():
        disc = conn_mgr.disconnected()
        st.markdown(f"""
        <div class="alert alert-err">
        <strong>Some services unreachable:</strong> {', '.join(disc)}<br>
        Use the <strong>Reconnect All</strong> button to restart port-forwards automatically.
        </div>""", unsafe_allow_html=True)
        if st.button("🔄 Reconnect All", key="reconnect"):
            with st.spinner("Restarting port-forwards… (5s)"):
                restart_port_forwards()
                time.sleep(5)
            conn_mgr.check_all()
            st.session_state.conn_status = conn_mgr.status
            st.rerun()

    # ── UPCOMING EVENTS STRIP ────────────────────────────────────────────────
    upcoming = get_upcoming_special(14)
    user_up  = get_upcoming_user_events(14)

    def _norm_ev(ev, is_special: bool) -> dict:
        if is_special:
            tl = ev.get("traffic_level", "")
            return {**ev, "display_name": ev.get("name", ""), "ai_date": ev.get("event_date", ""),
                    "ai_margin": LEVEL_TO_MARGIN.get(tl, 0.30)}
        else:
            tl = ev.get("seviye", "")
            return {**ev, "name": ev.get("ad", ""), "display_name": ev.get("ad", ""),
                    "traffic_level": tl, "ai_date": ev["baslangic"][:10],
                    "ai_margin": LEVEL_TO_MARGIN.get(tl, 0.30)}

    all_up = sorted(
        [_norm_ev(e, True) for e in upcoming] + [_norm_ev(e, False) for e in user_up],
        key=lambda x: x["days_until"]
    )[:8]

    if all_up:
        st.markdown('<div class="section-label">Upcoming Events</div>', unsafe_allow_html=True)
        chips = ""
        for ev in all_up:
            ti = TRAFFIC_LEVEL_MAP.get(ev.get("traffic_level",""), ("", "", "#64748b"))
            chips += f"""<div class="upcoming-chip">
                <span class="days">{ev['days_until']}d</span>
                <div><div class="name">{ev['display_name']}</div>
                <div class="level">{ti[0] if ti[0] else 'özel'}</div></div>
            </div>"""
        st.markdown(f'<div class="upcoming-strip">{chips}</div>', unsafe_allow_html=True)

        # ── AI Profil Etkinlik Önerileri ─────────────────────────────────
        applied = ai_get_applied()
        st.markdown(
            '<div class="section-label" style="font-size:11px;margin-top:6px;opacity:.7;">'
            'AI Profil — Etkinlik Önerileri</div>',
            unsafe_allow_html=True,
        )
        for ev in all_up:
            ev_name = ev["display_name"]
            ev_date = ev["ai_date"]
            margin  = ev["ai_margin"]
            if not ev_name or not ev_date:
                continue
            is_applied = (ev_name, ev_date) in applied
            c1, c2, c3 = st.columns([7, 1, 1])
            with c1:
                badge = " · **✓ AI aktif**" if is_applied else ""
                st.markdown(
                    f"<span style='font-size:12px;'>{ev_name} — {ev['days_until']}g "
                    f"· +%{int(margin*100)} marj{badge}</span>",
                    unsafe_allow_html=True,
                )
            with c2:
                if not is_applied:
                    if st.button("Uygula", key=f"ap_{ev_name}_{ev_date}",
                                 type="primary", use_container_width=True):
                        if ai_apply_event(ev_name, ev_date, margin):
                            st.toast(f"✓ {ev_name} AI profiline eklendi")
                            st.rerun()
            with c3:
                if is_applied:
                    if st.button("İptal", key=f"ca_{ev_name}_{ev_date}",
                                 use_container_width=True):
                        if ai_remove_event(ev_name, ev_date):
                            st.toast(f"✗ {ev_name} AI profilinden kaldırıldı")
                            st.rerun()

    # ── PROMETHEUS BAĞLANTI KONTROLÜ ─────────────────────────────────────────
    _prom_ok = False
    try:
        _pr = requests.get(f"{URLS['prometheus']}/-/ready", timeout=2)
        _prom_ok = _pr.ok
    except Exception:
        pass

    if not _prom_ok:
        st.error(
            "⚠️ **Prometheus'a bağlanılamıyor** (localhost:9090)  \n\n"
            "Port-forward aktif değil veya kesilmiş.  \n"
            "AutoScaleOps masaüstü uygulamasından **Başlat** butonuna basın  \n"
            "veya Sorun Giderici → **🚀 Tüm Hataları Düzelt** kullanın."
        )

    # ── METRICS ──────────────────────────────────────────────────────────────
    # Farklı framework'ler farklı metrik adları kullanır.
    # Sırayla dene: http_requests_total → flask_http_request_total → nginx
    def _get_app_rps() -> tuple:
        """(rps, metric_name) döndürür. Birden fazla kaynağı dener."""
        # 1. Standart: http_requests_total (kube/apiserver hariç)
        v = fetch_metric(
            'sum(rate(http_requests_total{job!~"kubernetes-apiservers|apiserver|kube-apiserver"'
            ',service!~".*kube.*|.*prometheus.*|.*coredns.*"}[1m]))'
        )
        if v > 0: return v, "http_requests_total"
        # 2. prometheus-flask-exporter varsayılan adı
        v = fetch_metric("sum(rate(flask_http_request_total[1m]))")
        if v > 0: return v, "flask_http_request_total"
        # 3. Geniş sorgu — her http_requests_total (apiserver dahil ama düşük etki)
        v = fetch_metric("sum(rate(http_requests_total[1m]))")
        if v > 0: return v, "http_requests_total (all)"
        # 4. nginx stub_status
        v = fetch_metric("sum(rate(nginx_requests_total[1m]))")
        if v > 0: return v, "nginx_requests_total"
        return 0.0, "none"

    real_rps, _metrics_source = _get_app_rps()
    pred_rps = fetch_metric("predicted_rps_30min")
    if pred_rps <= 0: pred_rps = calc_prediction(real_rps)
    real_rps = max(real_rps, 0.0)
    pred_rps = max(pred_rps, 0.0)
    _has_metrics = _metrics_source != "none"
    pods      = get_pod_count()
    cost_h    = pods * COST_PER_POD_HOUR
    is_keda, keda_lbl = get_keda_status()
    rps_pod   = real_rps / pods if pods else 0.0
    delta_pred = pred_rps - real_rps

    save_history(real_rps, pred_rps, pods, cost_h)

    st.markdown('<div class="section-label">Live Metrics</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    def mcard(col, label, value, delta=None, delta_prefix=""):
        delta_html = ""
        if delta is not None:
            cls = "up" if delta >= 0 else "down"
            sign = "+" if delta >= 0 else ""
            delta_html = f'<div class="metric-delta {cls}">{delta_prefix}{sign}{delta:.2f}</div>'
        col.markdown(f"""
        <div class="metric-block">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
        </div>""", unsafe_allow_html=True)

    mcard(c1, "Real RPS",     f"{real_rps:.2f}")
    mcard(c2, "AI Prediction",f"{pred_rps:.2f}", delta_pred)
    mcard(c3, "Active Pods",  str(pods))
    mcard(c4, "Cost / Hour",  f"${cost_h:.2f}")
    mcard(c5, "RPS / Pod",    f"{rps_pod:.2f}")

    # KEDA toggle row
    st.markdown("<br>", unsafe_allow_html=True)
    kc1, kc2, kc3 = st.columns([2,2,6])
    with kc1:
        pill_cls = "pill-ok" if is_keda else "pill-warn"
        st.markdown(f'<div class="pill {pill_cls}">KEDA: {keda_lbl}</div>', unsafe_allow_html=True)
    with kc2:
        if st.button("Toggle KEDA", key="toggle_keda"):
            ok, msg = toggle_autoscaling(not is_keda)
            st.toast(msg)
            time.sleep(0.4); st.rerun()

    st.divider()

    # ── TRAFFIC GRAPH ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Live Traffic Graph</div>', unsafe_allow_html=True)

    g_col1, g_col2 = st.columns([4,1])
    with g_col2:
        auto_r = st.checkbox("Auto-refresh 3s", value=st.session_state.auto_refresh, key="auto_r_chk")
        st.session_state.auto_refresh = auto_r

    # ── Timeseries: cache'e bağımlı kalmadan tüm kaynakları dene ─────────────
    def _fetch_rps_ts_robust(minutes: int = 30, step: str = "30s"):
        """Tüm RPS metrik kaynaklarını sırayla dener; ilk veri döndüreni kullanır.
        @st.cache_data kullanmıyor — eski 'boş' cache'in sorun çıkarmaması için."""
        _end   = int(time.time())
        _start = _end - minutes * 60
        _candidates = [
            # Önce bilinen aktif kaynak
            ("flask_http_request_total",
             "sum(rate(flask_http_request_total[1m]))"),
            ("http_requests_total (filtered)",
             'sum(rate(http_requests_total{job!~"kubernetes-apiservers|apiserver|kube-apiserver"'
             ',service!~".*kube.*|.*prometheus.*|.*coredns.*"}[1m]))'),
            ("http_requests_total (all)",
             "sum(rate(http_requests_total[1m]))"),
            ("nginx_requests_total",
             "sum(rate(nginx_requests_total[1m]))"),
        ]
        for _src_name, _q in _candidates:
            try:
                _r = requests.get(
                    f"{URLS['prometheus']}/api/v1/query_range",
                    params={"query": _q, "start": _start, "end": _end, "step": step},
                    timeout=CONNECTION_TIMEOUT,
                )
                if _r.ok:
                    _d = _r.json()
                    _result = _d.get("data", {}).get("result", [])
                    if _result:
                        _vals = [(float(_ts), float(_v))
                                 for _ts, _v in _result[0]["values"]]
                        if _vals:
                            return _vals, _src_name
            except Exception:
                continue
        return [], "none"

    ts_real, _ts_source = _fetch_rps_ts_robust(30, "30s")
    ts_pred = fetch_timeseries("predicted_rps_30min", 30, "30s")

    chart_df = pd.DataFrame()
    if ts_real:
        df_r = pd.DataFrame(ts_real, columns=["ts", "Real RPS"])
        df_r["time"] = pd.to_datetime(df_r["ts"], unit="s")
        chart_df = df_r[["time", "Real RPS"]]
    if ts_pred:
        df_p = pd.DataFrame(ts_pred, columns=["ts", "AI Prediction"])
        df_p["time"] = pd.to_datetime(df_p["ts"], unit="s")
        if not chart_df.empty:
            chart_df = chart_df.merge(
                df_p[["time", "AI Prediction"]], on="time", how="outer"
            ).sort_values("time").fillna(0)
        else:
            chart_df = df_p[["time", "AI Prediction"]]

    # Prometheus boş döndürdüyse tarihsel veriye bak
    if chart_df.empty:
        hist1d = get_history(1)
        if hist1d:
            df_h = pd.DataFrame(hist1d)
            df_h["time"] = pd.to_datetime(df_h["timestamp"])
            chart_df = df_h.rename(
                columns={"real_rps": "Real RPS", "pred_rps": "AI Prediction"}
            )[["time", "Real RPS", "AI Prediction"]]

    if not chart_df.empty:
        chart_df = chart_df.set_index("time").replace([float('inf'),float('-inf')], 0).fillna(0)
        _fig = go.Figure()
        if "Real RPS" in chart_df.columns:
            _fig.add_trace(go.Scatter(
                x=chart_df.index, y=chart_df["Real RPS"],
                name="Gerçek RPS",
                line=dict(color="#30D158", width=2, shape="spline", smoothing=1.3),
                fill="tozeroy", fillcolor="rgba(48,209,88,0.08)"
            ))
        if "AI Prediction" in chart_df.columns:
            _fig.add_trace(go.Scatter(
                x=chart_df.index, y=chart_df["AI Prediction"],
                name="AI Tahmin",
                line=dict(color="#0A84FF", width=2, shape="spline", smoothing=1.3, dash="dot")
            ))
        _fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
            margin=dict(l=0, r=0, t=20, b=0), height=320,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            xaxis=dict(showgrid=False, zeroline=False, color="#94a3b8"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)",
                       zeroline=False, color="#94a3b8"),
            hovermode="x unified"
        )
        st.plotly_chart(_fig, use_container_width=True, config={"displayModeBar": False})
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Data Points", len(chart_df))
        if "Real RPS" in chart_df.columns: s2.metric("Avg Real RPS", f"{chart_df['Real RPS'].mean():.3f}")
        if "AI Prediction" in chart_df.columns: s3.metric("Avg AI Pred", f"{chart_df['AI Prediction'].mean():.3f}")
        s4.markdown(
            f'<div style="font-size:10px;color:#64748b;padding-top:8px;">📡 Kaynak: {_ts_source}</div>',
            unsafe_allow_html=True
        )

        if real_rps == 0 and not ts_real:
            st.markdown(f"""<div class="alert alert-warn">
            <b>⚠️  Trafik Verisi Yok (RPS = 0)</b><br><br>
            <b>Olası nedenler ve çözümler:</b><br>
            1. <b>Uygulama /metrics endpoint'i yok</b> — AutoScaleOps'un oluşturduğu
               Dockerfile kullanıyorsanız Flask için <code>prometheus-flask-exporter</code>
               otomatik eklenir. Kendi Dockerfile'ınız varsa uygulamanıza metrics ekleyin.<br>
            2. <b>Uygulama henüz istek almadı</b> — <b>Load Test</b> sekmesinden
               k6 ile test trafiği gönderin.<br>
            3. <b>ServiceMonitor eksik</b> — AutoScaleOps Deploy sekmesinden
               projeyi yeniden deploy edin, ServiceMonitor otomatik oluşturulur.<br>
            4. <b>Port-forward kesilmiş</b> — Ana sayfadan <b>Başlat</b>'a basın.
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="alert alert-info" style="text-align:center; padding: 32px 20px;">
            <div style="font-size:2rem; margin-bottom:12px;">📡</div>
            <b>Trafik verisi bekleniyor…</b><br><br>
            Uygulama henüz istek almadı veya /metrics endpoint'i açık değil.<br><br>
            <b>Hızlı test:</b> <code>Load Test</code> sekmesinden k6 ile trafik gönderin.<br>
            <b>Kalıcı çözüm:</b> Deploy sekmesinden projeyi tekrar deploy edin
            (AutoScaleOps Dockerfile'ı otomatik metrics ekler).
        </div>""", unsafe_allow_html=True)

    if auto_r: time.sleep(3); st.rerun()

    st.divider()

    # ── TABS ─────────────────────────────────────────────────────────────────
    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "Load Test", "Event Calendar", "System Analysis",
        "GreenOps", "History", "Technical", "Settings"
    ])

    # ════ TAB 1: LOAD TEST ════
    with t1:
        st.markdown('<div class="section-title">k6 Load Test</div>', unsafe_allow_html=True)
        running, k6msg = check_k6()

        if running:
            elapsed  = time.time() - st.session_state.k6_started_at
            progress = min(elapsed / max(st.session_state.k6_duration, 1), 1.0)
            remaining = max(0, st.session_state.k6_duration - int(elapsed))

            st.progress(progress)
            st.markdown(f"""<div class="k6-card">
              <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:1rem;color:var(--ok);margin-bottom:12px">Test Running</div>
              <div class="k6-grid">
                <div class="k6-stat"><div class="k6-stat-val">{int(elapsed)}s</div><div class="k6-stat-lbl">Elapsed</div></div>
                <div class="k6-stat"><div class="k6-stat-val">{st.session_state.k6_duration}s</div><div class="k6-stat-lbl">Total</div></div>
                <div class="k6-stat"><div class="k6-stat-val">{remaining}s</div><div class="k6-stat-lbl">Remaining</div></div>
                <div class="k6-stat"><div class="k6-stat-val">{int(progress*100)}%</div><div class="k6-stat-lbl">Progress</div></div>
              </div></div>""", unsafe_allow_html=True)

            ca, cb = st.columns(2)
            with ca:
                if st.button("Stop Test", key="stop_k6"):
                    st.session_state.k6_process.terminate()
                    st.session_state.k6_running = False
                    st.toast("Test stopped"); time.sleep(0.4); st.rerun()
            with cb:
                if st.button("Refresh Status", key="ref_k6"): st.rerun()
            time.sleep(2); st.rerun()

        else:
            st.markdown("""<div class="info-panel">
            Configure test parameters and click <strong>Start Test</strong>.
            k6 will send HTTP requests to your application, generating visible traffic in the graph above.
            </div>""", unsafe_allow_html=True)

            p1, p2, p3 = st.columns(3)
            with p1: vus      = st.number_input("Virtual Users",  1, 1000, 10,  5,  key="k6_vus")
            with p2: duration = st.number_input("Duration (s)",  10, 3600, 60,  10, key="k6_dur")
            with p3: sleep_g  = st.number_input("Sleep (s)",    0.1, 10.0, 1.0, 0.1, key="k6_slp")

            if st.button("Start Test", key="start_k6", type="primary"):
                ok, msg = start_k6(URLS["app"], vus, duration, sleep_g)
                if ok:
                    info = json.loads(msg)
                    st.session_state.k6_running    = True
                    st.session_state.k6_process    = None
                    st.session_state.k6_started_at = info["started_at"]
                    st.session_state.k6_duration   = info["duration"]
                    st.toast("Test started!"); time.sleep(0.8); st.rerun()
                else: st.error(msg)

    # ════ TAB 2: CALENDAR ════
    with t2:
        st.markdown('<div class="section-title">Event Calendar</div>', unsafe_allow_html=True)
        month_names = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
                       7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
        today = date.today()

        if "cal_month" not in st.session_state: st.session_state.cal_month = today.month
        if "cal_year"  not in st.session_state: st.session_state.cal_year  = today.year

        cc1, cc2, cc3 = st.columns([2,2,1])
        with cc1:
            sel_month = st.selectbox("Month", list(month_names.keys()),
                                     format_func=lambda x: month_names[x],
                                     index=st.session_state.cal_month-1, key="cal_m")
            st.session_state.cal_month = sel_month
        with cc2:
            sel_year = st.number_input("Year", 2024, 2030,
                                        st.session_state.cal_year, key="cal_y")
            st.session_state.cal_year = sel_year
        with cc3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Today", key="cal_today"):
                st.session_state.cal_month = today.month
                st.session_state.cal_year  = today.year
                st.rerun()

        st.markdown(f'<div class="section-label">{month_names[sel_month]} {sel_year}</div>', unsafe_allow_html=True)

        user_evs = load_events()
        spec_days = load_special_days()
        month_evs = []

        for ev in user_evs:
            try:
                s = datetime.fromisoformat(ev["baslangic"]).date()
                if s.year == sel_year and s.month == sel_month:
                    month_evs.append({"type":"user","name":ev["ad"],
                                      "start":s,"end":datetime.fromisoformat(ev["bitis"]).date(),
                                      "desc":ev.get("aciklama",""),"level":ev.get("seviye","")})
            except: pass

        for sd in spec_days:
            try:
                m, dn = map(int, sd["date"].split("-"))
                if m == sel_month:
                    ev_date = date(sel_year, m, dn)
                    ti = TRAFFIC_LEVEL_MAP.get(sd.get("traffic_level",""),("","",""))
                    month_evs.append({"type":"special","name":sd["name"],
                                      "start":ev_date,"end":ev_date,
                                      "desc":sd.get("reason",""),"level":ti[0]})
            except: pass

        month_evs.sort(key=lambda x: x["start"])

        if month_evs:
            for ev in month_evs:
                cls = "special" if ev["type"]=="special" else ""
                icon = "★" if ev["type"]=="special" else "◆"
                date_str = str(ev["start"]) + (f" → {ev['end']}" if ev["start"]!=ev["end"] else "")
                st.markdown(f"""<div class="ev-card {cls}">
                  <div class="ev-name">{icon} {ev['name']}</div>
                  <div class="ev-meta">{date_str} · {ev['level']} · {ev['desc'][:80]}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert alert-info">No events in {month_names[sel_month]} {sel_year}.</div>',
                        unsafe_allow_html=True)

        st.divider()
        st.markdown('<div class="section-label">Manage User Events</div>', unsafe_allow_html=True)

        if user_evs:
            for idx, ev in enumerate(user_evs):
                ec1, ec2, ec3 = st.columns([8,1,1])
                with ec1:
                    s = datetime.fromisoformat(ev["baslangic"]).date()
                    e = datetime.fromisoformat(ev["bitis"]).date()
                    st.markdown(f"""<div class="ev-card">
                      <div class="ev-name">{ev['ad']}</div>
                      <div class="ev-meta">{s} → {e} · {ev.get('aciklama','')[:60]}</div>
                    </div>""", unsafe_allow_html=True)
                with ec2:
                    if st.button("Edit", key=f"ed_{idx}"):
                        st.session_state.editing_idx = idx; st.rerun()
                with ec3:
                    if st.button("Del", key=f"del_{idx}"):
                        ev_del = user_evs[idx]
                        ai_remove_event(ev_del.get("ad", ""), ev_del.get("baslangic", "")[:10])
                        delete_event(idx)
                        st.session_state.events = load_events()
                        st.toast("Deleted"); time.sleep(0.3); st.rerun()

        st.markdown('<div class="section-label">Add / Edit Event</div>', unsafe_allow_html=True)
        edit_i   = st.session_state.get("editing_idx")
        edit_ev  = user_evs[edit_i] if (edit_i is not None and 0<=edit_i<len(user_evs)) else None
        if edit_ev: st.markdown(f'<div class="alert alert-info">Editing: <strong>{edit_ev["ad"]}</strong></div>', unsafe_allow_html=True)

        with st.form("ev_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            with fc1:
                ev_name  = st.text_input("Event Name",  value=edit_ev["ad"] if edit_ev else "")
                ev_start = st.date_input("Start Date",  value=datetime.fromisoformat(edit_ev["baslangic"]).date() if edit_ev else today)
            with fc2:
                ev_level = st.selectbox("Traffic Level", ["Low","Medium","High","Very High"],
                                        index=["Low","Medium","High","Very High"].index(edit_ev.get("seviye","Medium")) if edit_ev and edit_ev.get("seviye","Medium") in ["Low","Medium","High","Very High"] else 1)
                ev_end   = st.date_input("End Date",    value=datetime.fromisoformat(edit_ev["bitis"]).date() if edit_ev else today)
            ev_desc = st.text_area("Description", value=edit_ev.get("aciklama","") if edit_ev else "")
            fs1, fs2 = st.columns(2)
            with fs1: submitted = st.form_submit_button("Save", type="primary", use_container_width=True)
            with fs2:
                if edit_ev:
                    if st.form_submit_button("Cancel", use_container_width=True):
                        st.session_state.editing_idx = None; st.rerun()
            if submitted and ev_name:
                new_ev = {"ad":ev_name,"baslangic":ev_start.isoformat(),"bitis":ev_end.isoformat(),
                          "seviye":ev_level,"aciklama":ev_desc}
                if edit_ev:
                    # Eski kayıt varsa AI profilden sil, yenisiyle ekle
                    ai_remove_event(edit_ev.get("ad",""), edit_ev.get("baslangic","")[:10])
                    update_event(edit_i, new_ev)
                    st.session_state.editing_idx = None
                else:
                    add_event(new_ev)
                st.session_state.events = load_events()
                # AI profiline de kaydet (yoğunluk → marj)
                margin = LEVEL_TO_MARGIN.get(ev_level, 0.30)
                ai_apply_event(ev_name, ev_start.isoformat(), margin)
                st.toast("Saved! ✓ AI profiline de eklendi"); time.sleep(0.3); st.rerun()

    # ════ TAB 3: ANALYSIS ════
    with t3:
        st.markdown('<div class="section-title">System Analysis</div>', unsafe_allow_html=True)
        atype = st.selectbox("Analysis Type", [
            "Current Status", "Weekly Trend",
            "Cost Optimization", "Prediction Accuracy", "Next Week Forecast"
        ], key="a_type")
        if st.button("Run Analysis", key="run_a", type="primary"):
            with st.spinner("Analyzing..."):
                time.sleep(0.5)
                r = {
                    "Current Status":      lambda: analyze_status(real_rps, pred_rps, pods, cost_h),
                    "Weekly Trend":        lambda: analyze_weekly(real_rps, pred_rps, pods),
                    "Cost Optimization":   lambda: analyze_cost(real_rps, pods, cost_h),
                    "Prediction Accuracy": lambda: analyze_accuracy(real_rps, pred_rps),
                    "Next Week Forecast":  lambda: analyze_forecast(real_rps),
                }[atype]()
                st.session_state.insight_result = r
        if st.session_state.insight_result: st.markdown(st.session_state.insight_result)

    # ════ TAB 4: GREENOPS ════
    with t4:
        st.markdown('<div class="section-title">GreenOps</div>', unsafe_allow_html=True)
        st.markdown("""<div class="info-panel">
        <strong>GreenOps</strong> automatically reduces pod count during off-hours and weekends,
        saving energy and cost. When active, KEDA is temporarily suspended and the deployment
        is fixed to your specified pod count.
        </div>""", unsafe_allow_html=True)

        go_enabled = st.checkbox("Enable GreenOps Policy", value=st.session_state.greenops_enabled)
        st.session_state.greenops_enabled = go_enabled

        if go_enabled:
            gc1, gc2 = st.columns(2)
            with gc1:
                st_time = st.time_input("Business Hours Start",
                    value=datetime.strptime(st.session_state.greenops_start,"%H:%M").time(), key="go_s")
                st.session_state.greenops_start = st_time.strftime("%H:%M")
                off_pods = st.number_input("Off-Hours Pods", 1, 10, st.session_state.greenops_offhour_pods)
                st.session_state.greenops_offhour_pods = off_pods
            with gc2:
                en_time = st.time_input("Business Hours End",
                    value=datetime.strptime(st.session_state.greenops_end,"%H:%M").time(), key="go_e")
                st.session_state.greenops_end = en_time.strftime("%H:%M")
                we_pods = st.number_input("Weekend Pods", 1, 10, st.session_state.greenops_weekend_pods)
                st.session_state.greenops_weekend_pods = we_pods
            st.markdown('<div class="alert alert-ok">GreenOps Active — auto-scaling to configured pod counts outside business hours.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert alert-info">GreenOps is disabled. Enable above to start saving energy.</div>', unsafe_allow_html=True)

        save_greenops({"greenops_enabled":go_enabled,"greenops_start":st.session_state.greenops_start,
                       "greenops_end":st.session_state.greenops_end,
                       "greenops_offhour_pods":st.session_state.greenops_offhour_pods,
                       "greenops_weekend_pods":st.session_state.greenops_weekend_pods})

    # ════ TAB 5: HISTORY ════
    with t5:
        st.markdown('<div class="section-title">Metrics History</div>', unsafe_allow_html=True)
        hc1, hc2 = st.columns([3,1])
        with hc1: days_s = st.selectbox("Range", [1,3,7,14,30], index=2, format_func=lambda x: f"Last {x} days")
        with hc2:
            st.markdown("<br>", unsafe_allow_html=True)
            export = st.button("Export CSV")

        hist = get_history(days_s)
        if hist:
            df = pd.DataFrame(hist)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            if export:
                buf = io.StringIO(); df.to_csv(buf, index=False)
                st.download_button("Download CSV", buf.getvalue(),
                    f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
            hm1,hm2,hm3,hm4 = st.columns(4)
            hm1.metric("Avg RPS",  f"{df['real_rps'].mean():.2f}")
            hm2.metric("Peak RPS", f"{df['real_rps'].max():.2f}")
            hm3.metric("Min RPS",  f"{df['real_rps'].min():.2f}")
            hm4.metric("Total Cost", f"${df['cost_hour'].sum():.2f}")
            _hfig = go.Figure()
            _hfig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['real_rps'],
                name="Gerçek RPS",
                line=dict(color="#30D158", width=2, shape="spline", smoothing=1.3),
                fill="tozeroy", fillcolor="rgba(48,209,88,0.08)"
            ))
            _hfig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['pred_rps'],
                name="AI Tahmin",
                line=dict(color="#0A84FF", width=2, shape="spline", smoothing=1.3, dash="dot")
            ))
            _hfig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                margin=dict(l=0, r=0, t=10, b=0), height=320,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                xaxis=dict(showgrid=False, zeroline=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False),
                hovermode="x unified"
            )
            st.plotly_chart(_hfig, use_container_width=True, config={"displayModeBar": False})
            with st.expander("Raw Data Table"):
                st.dataframe(df, use_container_width=True)
        else:
            # Seçilen aralıkta veri yok — tüm zamanı dene
            hist_all = get_history(3650)
            if hist_all:
                st.info(
                    f"Seçilen aralıkta ({days_s} gün) veri yok. "
                    f"Toplam {len(hist_all)} geçmiş kayıt mevcut (en eski: {hist_all[-1]['timestamp'][:10]}).  \n"
                    f"Dashboard çalıştıkça yeni veriler birikir — 3 saniyede bir kaydediliyor."
                )
            else:
                st.info(
                    "📊 Henüz geçmiş verisi yok.  \n"
                    "Dashboard açık kaldıkça her 3 saniyede bir veri kaydedilir.  \n"
                    "**Auto-refresh 3s** aktif olduğunda veriler otomatik birikir."
                )

    # ════ TAB 6: TECHNICAL ════
    with t6:
        st.markdown('<div class="section-title">Technical Details</div>', unsafe_allow_html=True)

        if st.button("🔄 Yenile / Refresh", key="tech_refresh"):
            st.rerun()

        # ── Bağlantı Durumu ──────────────────────────────────────────────
        st.markdown('<div class="section-label">Bağlantı Durumu</div>', unsafe_allow_html=True)
        _tc1, _tc2, _tc3 = st.columns(3)
        def _conn_pill(col, label, url, path="/-/ready"):
            try:
                import requests as _req
                _r = _req.get(url + path, timeout=2)
                _ok = _r.ok
            except Exception:
                _ok = False
            col.markdown(
                f'<div class="pill {"pill-ok" if _ok else "pill-warn"}">'
                f'{"✅" if _ok else "❌"} {label}</div>',
                unsafe_allow_html=True
            )
        _conn_pill(_tc1, "Prometheus :9090", f"{URLS['prometheus']}")
        _conn_pill(_tc2, "Pushgateway :9091", f"{URLS['pushgateway']}")
        _conn_pill(_tc3, f"App :{_ACTIVE_PROJECT.get('port',8080)}", f"http://localhost:{_ACTIVE_PROJECT.get('port',8080)}", "/")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Pod Durumu ───────────────────────────────────────────────────
        st.markdown('<div class="section-label">Pod Durumu</div>', unsafe_allow_html=True)
        pod_out = run_ps(f"kubectl get pods -n {NAMESPACE} -o wide 2>$null")
        if pod_out: st.code(pod_out, language="text")
        else: st.warning("Pod verisi alınamadı. kubectl çalışıyor mu?")

        # ── KEDA HPA ────────────────────────────────────────────────────
        st.markdown('<div class="section-label">KEDA / HPA Durumu</div>', unsafe_allow_html=True)
        hpa_out = run_ps(f"kubectl get hpa -n {NAMESPACE} 2>$null")
        if hpa_out: st.code(hpa_out, language="text")
        keda_out = run_ps(f"kubectl get scaledobject -n {NAMESPACE} 2>$null")
        if keda_out: st.code(keda_out, language="text")
        else: st.info("ScaledObject bulunamadı.")

        # ── Servisler ────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Servisler</div>', unsafe_allow_html=True)
        svc_out = run_ps(f"kubectl get svc -n {NAMESPACE} 2>$null")
        if svc_out: st.code(svc_out, language="text")

        # ── Son Olaylar ──────────────────────────────────────────────────
        st.markdown('<div class="section-label">Son Olaylar (20)</div>', unsafe_allow_html=True)
        ev_out = run_ps(
            f"kubectl get events -n {NAMESPACE} --sort-by=.lastTimestamp 2>$null"
            f" | Select-Object -Last 20"
        )
        if ev_out: st.code(ev_out, language="text")
        else: st.info("Olay yok.")

        # ── Prometheus Hedefleri ──────────────────────────────────────────
        st.markdown('<div class="section-label">Prometheus Hedefleri</div>', unsafe_allow_html=True)
        try:
            import requests as _req2
            _tr = _req2.get(f"{URLS['prometheus']}/api/v1/targets", timeout=4)
            if _tr.ok:
                _targets = _tr.json().get("data", {}).get("activeTargets", [])
                _aso = [t for t in _targets if "autoscaleops" in str(t.get("labels", {}))]
                st.success(f"✅ {len(_targets)} aktif hedef, {len(_aso)} autoscaleops hedefi")
                if _aso:
                    for _t in _aso[:5]:
                        st.code(f"Job: {_t['labels'].get('job','?')}  |  State: {_t['health']}  |  {_t.get('lastScrape','?')[:19]}", language="text")
            else:
                st.warning("Prometheus hedefleri alınamadı.")
        except Exception:
            st.warning("Prometheus'a bağlanılamıyor (localhost:9090 kapalı).")

        # ── Dashboard Logs ───────────────────────────────────────────────
        st.markdown('<div class="section-label">Dashboard Log</div>', unsafe_allow_html=True)
        _log_path = Path.home() / ".autoscaleops" / "logs" / "dashboard.log"
        try:
            lines = _log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            st.code("\n".join(lines[-50:]), language="text")
        except Exception:
            try:
                lines = Path("dashboard.log").read_text(encoding="utf-8", errors="replace").splitlines()
                st.code("\n".join(lines[-50:]), language="text")
            except Exception:
                st.info(f"Log dosyası bulunamadı: {_log_path}")

    # ════ TAB 7: SETTINGS ════
    with t7:
        st.markdown('<div class="section-title">Settings</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-label">Cache & Connection</div>', unsafe_allow_html=True)
        if st.button("Force Refresh Cache", key="force_refresh"):
            fetch_metric.clear(); fetch_timeseries.clear()
            conn_mgr.check_all(); st.session_state.conn_status = conn_mgr.status
            st.toast("Cache cleared!"); time.sleep(0.3); st.rerun()

        st.markdown('<div class="section-label">Debug: Available Metrics</div>', unsafe_allow_html=True)
        st.markdown("""<div class="info-panel">
        If traffic is showing as 0, check which metrics are available in Prometheus.
        <code>http_requests_total</code> should appear in the list below.
        </div>""", unsafe_allow_html=True)
        if st.button("Show All Prometheus Metrics", key="show_metrics"):
            names = get_all_metric_names()
            http_metrics = [n for n in names if "http" in n.lower() or "request" in n.lower()]
            if http_metrics:
                st.markdown('<div class="alert alert-ok">HTTP-related metrics found:</div>', unsafe_allow_html=True)
                st.code("\n".join(http_metrics))
            else:
                st.markdown('<div class="alert alert-warn">No HTTP metrics found. Is the app running and being scraped?</div>', unsafe_allow_html=True)
            with st.expander("All metrics"):
                st.code("\n".join(names[:100]))

        st.markdown('<div class="section-label">Data Management</div>', unsafe_allow_html=True)
        dm1, dm2 = st.columns(2)
        with dm1:
            if st.button("Clear History", key="clr_hist"):
                if HISTORY_FILE.exists(): HISTORY_FILE.unlink()
                st.toast("History cleared!"); st.rerun()
        with dm2:
            st.markdown(f'<div class="info-panel">Records: <strong>{len(get_history(365))}</strong></div>', unsafe_allow_html=True)

        st.markdown('<div class="section-label">System Info</div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="info-panel">
        <strong>Dashboard Version:</strong> 3.0<br>
        <strong>Instance ID:</strong> {INSTANCE_ID}<br>
        <strong>Namespace:</strong> {NAMESPACE}<br>
        <strong>Minikube Profile:</strong> {KUBE_PROFILE}<br>
        <strong>AI Engine:</strong> Running<br>
        <strong>GreenOps:</strong> {"Active" if st.session_state.greenops_enabled else "Inactive"}<br>
        <strong>Last Refresh:</strong> {datetime.now().strftime("%H:%M:%S")}<br>
        <strong>Services:</strong> {"All Connected" if conn_mgr.all_ok() else f"Issues: {', '.join(conn_mgr.disconnected())}"}
        </div>""", unsafe_allow_html=True)

    # ── FOOTER ──────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("""<div style="text-align:center;padding:16px;font-size:0.72rem;color:var(--muted);font-family:'DM Mono',monospace">
    AutoScaleOps v3.0 · AI-Powered · Kubernetes KEDA · Made with care
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    try: main()
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
        st.error("Dashboard critical error. Check logs.")