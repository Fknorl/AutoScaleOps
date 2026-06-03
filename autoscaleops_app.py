#!/usr/bin/env python3
"""
AutoScaleOps Desktop Application
Windows Desktop Control Panel for Kubernetes AI Autoscaling
"""

import sys
import os
import json
import sqlite3
import hashlib
import secrets
import subprocess
import threading
import webbrowser
import socket
import uuid
import winreg
import platform
import shutil
import csv
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any

import psutil
import requests
from cryptography.fernet import Fernet

try:
    import matplotlib
    matplotlib.use("QtAgg")
except ImportError:
    pass

from PyQt6.QtCore import (
    Qt, QTimer, QThread, QObject, pyqtSignal, pyqtSlot,
    QSize, QRect, QPropertyAnimation, QEasingCurve, QPoint, QDate
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit, QTextEdit,
    QProgressBar, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QCheckBox, QRadioButton, QButtonGroup,
    QFileDialog, QDialog, QDialogButtonBox, QMessageBox, QSizePolicy,
    QSplitter, QGroupBox, QListWidget, QListWidgetItem, QHeaderView,
    QAbstractItemView, QDateTimeEdit, QTimeEdit, QSystemTrayIcon, QMenu,
    QToolButton, QSlider, QTabWidget, QDoubleSpinBox, QTextBrowser, QDateEdit
)
from PyQt6.QtGui import (
    QFont, QIcon, QPixmap, QColor, QPalette, QBrush, QPainter,
    QPainterPath, QLinearGradient, QAction, QCursor, QMovie,
    QTextCharFormat, QTextCursor, QImage, QRegion, QDesktopServices
)
from PyQt6.QtCore import QUrl

# -------------------------------------------------
#  CONSTANTS
# -------------------------------------------------
APP_NAME = "AutoScaleOps"
APP_VERSION = "2.0.0"
APP_DIR = Path.home() / ".autoscaleops"
DB_PATH = APP_DIR / "autoscaleops.db"
INSTANCE_PATH = APP_DIR / "instance.json"
ACTIVE_PROJECT_PATH = APP_DIR / "active_project.json"
AVATAR_PATH = APP_DIR / "avatar.png"
ASSETS_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / "assets"
NGROK_DIR = APP_DIR / "tools"
NGROK_EXE = NGROK_DIR / "ngrok.exe"
NGROK_URL = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
SETUP_COMPLETE_PATH = APP_DIR / "setup_complete.json"

# ─────────────────────────────────────────────────────────────────────────────
#  DILLER / LANGUAGE  (TR default, EN optional)
# ─────────────────────────────────────────────────────────────────────────────
_APP_LANG: str = "tr"   # "tr" veya "en" — DB yüklendikten sonra güncellenir

_STRINGS: dict[str, dict[str, str]] = {
    # Nav sidebar
    "nav.home":          {"tr": "Ana Sayfa",    "en": "Home"},
    "nav.dashboard":     {"tr": "Dashboard",    "en": "Dashboard"},
    "nav.activity":      {"tr": "Aktivite",     "en": "Activity"},
    "nav.troubleshoot":  {"tr": "Sorun Gider",  "en": "Troubleshoot"},
    "nav.settings":      {"tr": "Ayarlar",      "en": "Settings"},
    "nav.deploy":        {"tr": "Deploy",       "en": "Deploy"},
    "nav.ai_profile":    {"tr": "AI Profil",    "en": "AI Profile"},
    # Settings panel
    "settings.title":           {"tr": "Ayarlar",                      "en": "Settings"},
    "settings.preferences":     {"tr": "Tercihler",                    "en": "Preferences"},
    "settings.startup":         {"tr": "Windows başlangıcında başlat", "en": "Launch on Windows startup"},
    "settings.tray":            {"tr": "Kapatınca sistem tepsisine küçült", "en": "Minimize to tray on close"},
    "settings.refresh":         {"tr": "Otomatik yenileme aralığı:",   "en": "Auto-refresh interval:"},
    "settings.notif":           {"tr": "Ölçekleme olayları için bildirim gönder", "en": "Toast notifications for scale events"},
    "settings.language":        {"tr": "Uygulama dili:",               "en": "App language:"},
    "settings.lang_tr":         {"tr": "Türkçe",                       "en": "Turkish"},
    "settings.lang_en":         {"tr": "İngilizce",                    "en": "English"},
    "settings.about":           {"tr": "Hakkında",                     "en": "About"},
    "settings.docs":            {"tr": "Dokümantasyon",                "en": "Documentation"},
    "settings.open_folder":     {"tr": "Uygulama Klasörünü Aç",       "en": "Open App Folder"},
    "settings.check_updates":   {"tr": "Güncellemeleri Kontrol Et",    "en": "Check for Updates"},
    "settings.restart_notice":  {
        "tr": "Dil değişikliği kaydedildi.\nTam etkisi için uygulamayı yeniden başlatın.",
        "en": "Language preference saved.\nRestart the app to apply fully."
    },
    # Troubleshooter
    "troubleshoot.title":         {"tr": "Sorun Giderici",   "en": "Troubleshooter"},
    "troubleshoot.run_diag":      {"tr": "🔍  Tam Tanı Çalıştır",  "en": "🔍  Run Full Diagnostics"},
    "troubleshoot.export":        {"tr": "📄  Rapor Aktar",         "en": "📄  Export Report"},
    "troubleshoot.running":       {"tr": "⏳  Çalıştırılıyor...",   "en": "⏳  Running..."},
    "troubleshoot.auto_fix":      {"tr": "Otomatik Düzelt",          "en": "Auto Fix"},
    "troubleshoot.no_results":    {"tr": "Tanı sonucu bulunamadı.",  "en": "No diagnostic results found."},
    # Common UI
    "btn.save":     {"tr": "Kaydet",   "en": "Save"},
    "btn.cancel":   {"tr": "İptal",    "en": "Cancel"},
    "btn.close":    {"tr": "Kapat",    "en": "Close"},
    "btn.confirm":  {"tr": "Onayla",   "en": "Confirm"},
    "lbl.loading":  {"tr": "Yükleniyor...", "en": "Loading..."},
    "lbl.error":    {"tr": "Hata",     "en": "Error"},
    "lbl.success":  {"tr": "Başarılı", "en": "Success"},
}


def t(key: str) -> str:
    """Return the translated string for *key* in the current app language.
    Falls back to the key itself if not found."""
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(_APP_LANG) or entry.get("tr") or key


# Color palette — Liquid Glass / Midnight Aurora
C_BG       = "#05050F"   # Liquid void — near-black with blue depth
C_SURFACE  = "#0C0C1E"   # Frosted glass panel
C_SURFACE2 = "#121228"   # Elevated glass layer
C_BORDER   = "#28285A"   # Indigo-tinted border
C_ACCENT   = "#818CF8"   # Soft indigo violet
C_ACCENT2  = "#6366F1"   # Deeper indigo (press state)
C_GREEN    = "#34D399"   # Emerald
C_RED      = "#F87171"   # Coral red
C_YELLOW   = "#FCD34D"   # Warm amber
C_TEXT     = "#F2F4FF"   # Pure cool white
C_TEXT_DIM = "#5A6A8A"   # Blue-gray mist
C_HOVER    = "#181834"   # Deep glass hover
C_SIDEBAR  = "#030308"   # Deepest void
C_GLASS_HI = "rgba(255,255,255,22)"   # Glass top-edge highlight
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}
/* ── Liquid Glass Buttons ── */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(40,40,80,200), stop:1 rgba(18,18,40,220));
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,22);
    border-radius: 14px;
    padding: 9px 20px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(60,60,110,220), stop:1 rgba(28,28,60,230));
    border-color: rgba(129,140,248,160);
}}
QPushButton:pressed {{
    background: {C_ACCENT2};
    color: #fff;
    border-color: {C_ACCENT2};
}}
QPushButton:disabled {{
    color: {C_TEXT_DIM};
    border-color: rgba(255,255,255,8);
    background: rgba(12,12,30,160);
}}
QPushButton#btn_primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #9BA8FA, stop:1 {C_ACCENT});
    color: #fff;
    border: none;
    font-weight: 600;
    border-radius: 14px;
}}
QPushButton#btn_primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ADB7FB, stop:1 #939BFA);
}}
QPushButton#btn_primary:pressed {{ background: {C_ACCENT2}; }}
QPushButton#btn_danger {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FA8585, stop:1 {C_RED});
    color: #fff;
    border: none;
    font-weight: 600;
    border-radius: 14px;
}}
QPushButton#btn_danger:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FC9090, stop:1 #FB8080);
}}
QPushButton#btn_success {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5BDDAA, stop:1 {C_GREEN});
    color: #051A0F;
    border: none;
    font-weight: 600;
    border-radius: 14px;
}}
QPushButton#btn_success:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6EEABB, stop:1 #5BDDAA);
}}
QPushButton#btn_warning {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FCDE65, stop:1 {C_YELLOW});
    color: #1A1200;
    border: none;
    font-weight: 600;
    border-radius: 14px;
}}
QPushButton#btn_launch {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #9BA8FA, stop:1 {C_ACCENT2});
    color: #ffffff;
    border: 1px solid rgba(255,255,255,30);
    border-radius: 22px;
    padding: 14px 52px;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 0.4px;
}}
QPushButton#btn_launch:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ADB7FB, stop:1 #7C80F5);
    border-color: rgba(255,255,255,50);
}}
QPushButton#btn_launch:pressed {{
    background: {C_ACCENT2};
    border-color: {C_ACCENT2};
}}
QPushButton#btn_launch:disabled {{
    background: rgba(18,18,40,200);
    color: {C_TEXT_DIM};
    border: 1px solid rgba(255,255,255,10);
}}
QPushButton#mode_chip {{
    background: rgba(20,20,42,200);
    color: {C_TEXT_DIM};
    border: 1px solid rgba(255,255,255,18);
    border-radius: 22px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#mode_chip:hover {{
    background: rgba(30,30,60,220);
    color: {C_TEXT};
    border-color: rgba(129,140,248,120);
}}
QPushButton#mode_chip[active="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #9BA8FA, stop:1 {C_ACCENT});
    color: #ffffff;
    border: 1px solid rgba(255,255,255,30);
    font-weight: 600;
}}
/* ── Liquid Glass Inputs ── */
QLineEdit {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(20,20,45,220), stop:1 rgba(12,12,30,230));
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,18);
    border-radius: 12px;
    padding: 9px 14px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 1px solid rgba(129,140,248,200);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(30,30,60,230), stop:1 rgba(18,18,40,240));
}}
QTextEdit, QListWidget, QTableWidget {{
    background: rgba(12,12,30,220);
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,14);
    border-radius: 14px;
}}
QTextEdit:focus {{ border-color: rgba(129,140,248,180); }}
QTableWidget {{
    gridline-color: {C_BORDER};
    selection-background-color: {C_HOVER};
}}
QTableWidget::item {{ padding: 5px 10px; }}
QTableWidget::item:selected {{ background-color: {C_HOVER}; }}
QHeaderView::section {{
    background: rgba(10,10,28,200);
    color: {C_TEXT_DIM};
    border: none;
    border-bottom: 1px solid {C_BORDER};
    padding: 7px 10px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
}}
/* ── QSlider — font-size sabitleniyor (QFont::setPointSize uyarısını engeller) ── */
QSlider {{
    font-size: 12px;
}}
/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 5px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(129,140,248,50);
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(129,140,248,180); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 5px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(129,140,248,50);
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: rgba(129,140,248,180); }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
/* ── Combobox ── */
QComboBox {{
    background: rgba(18,18,42,220);
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,18);
    border-radius: 12px;
    padding: 9px 14px;
}}
QComboBox:focus {{ border-color: rgba(129,140,248,180); }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {C_SURFACE2};
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,16);
    border-radius: 12px;
    selection-background-color: {C_HOVER};
}}
/* ── Progress bar ── */
QProgressBar {{
    background: rgba(12,12,30,200);
    border: 1px solid rgba(255,255,255,12);
    border-radius: 6px;
    height: 7px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C_ACCENT}, stop:1 #B5BFFC);
    border-radius: 6px;
}}
/* ── Group box ── */
QGroupBox {{
    border: 1px solid rgba(255,255,255,14);
    border-radius: 18px;
    margin-top: 18px;
    padding-top: 10px;
    font-weight: 600;
    color: {C_TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {C_TEXT_DIM};
    font-size: 11px;
    letter-spacing: 0.6px;
}}
/* ── Checkboxes & Radios ── */
QCheckBox {{ color: {C_TEXT}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 17px; height: 17px;
    border: 1px solid rgba(255,255,255,22);
    border-radius: 6px;
    background: rgba(12,12,30,200);
}}
QCheckBox::indicator:checked {{
    background: {C_ACCENT};
    border-color: {C_ACCENT};
}}
QRadioButton {{ color: {C_TEXT}; spacing: 8px; }}
QRadioButton::indicator {{
    width: 17px; height: 17px;
    border: 1px solid rgba(255,255,255,22);
    border-radius: 9px;
    background: rgba(12,12,30,200);
}}
QRadioButton::indicator:checked {{
    background: {C_ACCENT};
    border-color: {C_ACCENT};
}}
/* ── Tab widget ── */
QTabWidget::pane {{
    border: 1px solid rgba(255,255,255,12);
    border-radius: 16px;
    background: rgba(12,12,30,200);
}}
QTabBar::tab {{
    background: transparent;
    color: {C_TEXT_DIM};
    padding: 10px 20px;
    border: none;
    border-radius: 12px 12px 0 0;
    font-weight: 500;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    color: {C_TEXT};
    background: rgba(20,20,44,200);
    border-bottom: 2px solid {C_ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover {{ color: {C_TEXT}; background: rgba(24,24,52,180); }}
/* ── Menu ── */
QMenu {{
    background-color: {C_SURFACE2};
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,16);
    border-radius: 14px;
    padding: 6px;
}}
QMenu::item {{ padding: 9px 26px 9px 16px; border-radius: 10px; }}
QMenu::item:selected {{ background-color: {C_HOVER}; }}
QMenu::separator {{ height: 1px; background: rgba(255,255,255,12); margin: 4px 10px; }}
/* ── Spin / Time ── */
QSpinBox, QTimeEdit {{
    background-color: {C_SURFACE};
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,18);
    border-radius: 14px;
    padding: 9px 12px;
}}
/* ── Tooltip ── */
QToolTip {{
    background-color: {C_SURFACE2};
    color: {C_TEXT};
    border: 1px solid rgba(255,255,255,18);
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 12px;
}}
"""

# -------------------------------------------------
#  HELPER UTILITIES
# -------------------------------------------------
def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    return base / rel

def make_circular_pixmap(pixmap: QPixmap, size: int) -> QPixmap:
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, size, size, pixmap)
    painter.end()
    return result

def _detect_container_port(folder: str, default: int) -> int:
    """Dockerfile'daki EXPOSE satırından gerçek container portunu oku."""
    import re as _re
    try:
        df = Path(folder) / "Dockerfile"
        if df.exists():
            for line in df.read_text(encoding="utf-8", errors="replace").splitlines():
                m = _re.match(r"^\s*EXPOSE\s+(\d+)", line, _re.IGNORECASE)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return default


def _find_free_port(preferred: int) -> int:
    """Tercih edilen portu dene; doluysa 8081-8300 arasında boş port bul."""
    import socket
    for port in [preferred] + list(range(8081, 8301)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    # Son çare: OS'un verdiği rasgele port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_active_project_json(name: str, port: int, service: str) -> None:
    """Dashboard'un okuyabilmesi için active_project.json yazar.
    Streamlit'in SQLite'a erişimi olmadığından JSON dosya kullanıyoruz."""
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_PROJECT_PATH.write_text(
            json.dumps({"name": name, "port": port, "service_name": service,
                        "updated_at": datetime.now().isoformat()}, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


def _sanitize_docker_name(name: str) -> str:
    """Proje adını Docker image tag formatına dönüştür.
    Docker kuralı: [a-z0-9]+(?:[._-][a-z0-9]+)*
    Türkçe karakterler ASCII karşılıklarına çevrilir.
    """
    import re as _re
    import unicodedata as _ud
    # Unicode normalize → ASCII (ö→o, ü→u, ş→s, ğ→g, ı→i, ç→c)
    nfkd = _ud.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    # Küçük harf, alfanumerik olmayan → tire
    sanitized = _re.sub(r"[^a-z0-9]+", "-", ascii_str.lower()).strip("-")
    return sanitized or "app"


def _auto_dockerfile(folder: str) -> Optional[str]:
    """Klasörü analiz et, uygun Dockerfile içeriği döndür. Dockerfile zaten varsa None.

    Açık kaynak mimarisi için tüm proje tiplerinde otomatik Prometheus metrik
    enjeksiyonu yapılır. Kullanıcı koduna dokunulmaz — framework seviyesinde
    monkey-patch / sidecar script ile http_requests_total otomatik expose edilir.
    """
    import re as _re
    p = Path(folder)
    if (p / "Dockerfile").exists():
        return None  # Zaten var, dokunma

    # ── Python projesi ────────────────────────────────────────────────────────
    if (p / "requirements.txt").exists() or list(p.glob("*.py")):
        candidates = list(p.glob("*.py"))
        if   (p / "app.py").exists():   entry = "app.py"
        elif (p / "main.py").exists():  entry = "main.py"
        elif candidates:                entry = candidates[0].name
        else:                           entry = "app.py"

        # Flask kullanılıyor mu? requirements.txt veya kaynak koda bak
        uses_flask = False
        try:
            req_text = (p / "requirements.txt").read_text(encoding="utf-8", errors="replace").lower()
            uses_flask = "flask" in req_text
        except Exception:
            pass
        if not uses_flask:
            try:
                src = (p / entry).read_text(encoding="utf-8", errors="replace")
                uses_flask = bool(_re.search(r'from\s+flask|import\s+flask|Flask\(', src, _re.I))
            except Exception:
                pass

        if uses_flask:
            # Flask için prometheus-flask-exporter monkey-patch —
            # kullanıcının app.py'sine dokunmadan http_requests_total expose eder.
            metrics_shim = (
                "# AutoScaleOps — otomatik Prometheus metrik shim\\n"
                "# Bu dosya deploy sirasinda olusturulur, silmeyin.\\n"
                "try:\\n"
                "    from prometheus_flask_exporter import PrometheusMetrics as _PM\\n"
                "    import flask as _fl\\n"
                "    _orig = _fl.Flask.__init__\\n"
                "    _patched = []\\n"
                "    def _p(self, *a, **kw):\\n"
                "        _orig(self, *a, **kw)\\n"
                "        if not _patched:\\n"
                "            _PM(self)\\n"
                "            _patched.append(1)\\n"
                "    _fl.Flask.__init__ = _p\\n"
                "except Exception:\\n"
                "    pass\\n"
            )
            return (
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "RUN pip install --no-cache-dir -r requirements.txt "
                "    prometheus-flask-exporter 2>/dev/null || "
                "    pip install --no-cache-dir -r requirements.txt && "
                "    pip install --no-cache-dir prometheus-flask-exporter\n"
                # Shim dosyasını yaz ve entry point'e prepend et
                f"RUN python3 -c \"shim='{metrics_shim}'; "
                f"orig=open('{entry}').read(); "
                f"open('{entry}','w').write(shim+orig)\" 2>/dev/null || true\n"
                "EXPOSE 8080\n"
                f'CMD ["python", "{entry}"]\n'
            )
        else:
            # Genel Python uygulaması — prometheus_client ile basit HTTP sunucu
            return (
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "RUN pip install --no-cache-dir -r requirements.txt "
                "    prometheus-client 2>/dev/null || "
                "    pip install --no-cache-dir -r requirements.txt\n"
                "EXPOSE 8080\n"
                f'CMD ["python", "{entry}"]\n'
            )

    # ── Node.js projesi ───────────────────────────────────────────────────────
    if (p / "package.json").exists():
        entry = "index.js" if (p / "index.js").exists() else "server.js"
        # prom-client ile http_requests_total otomatik inject edilir
        # Kullanıcının koduna dokunmadan Node http modülünü wrap eder.
        node_shim = (
            "// AutoScaleOps Prometheus shim\\n"
            "const client=require('prom-client');\\n"
            "client.collectDefaultMetrics();\\n"
            "const ctr=new client.Counter({name:'http_requests_total',"
            "help:'Total HTTP requests',labelNames:['method','status']});\\n"
            "const _http=require('http');\\n"
            "const _orig=_http.Server.prototype.emit;\\n"
            "_http.Server.prototype.emit=function(ev,...a){"
            "if(ev==='request'){const res=a[1];const origEnd=res.end.bind(res);"
            "res.end=(...b)=>{ctr.labels(a[0].method||'GET',String(res.statusCode)).inc();return origEnd(...b);}}"
            "return _orig.call(this,ev,...a);};\\n"
            "require('http').createServer(async(req,res)=>{"
            "if(req.url==='/metrics'){res.setHeader('Content-Type',client.register.contentType);"
            "res.end(await client.register.metrics());}}).listen(9090);\\n"
        )
        return (
            "FROM node:20-alpine\n"
            "WORKDIR /app\n"
            "COPY package*.json ./\n"
            "RUN npm install --production && npm install prom-client\n"
            "COPY . .\n"
            # Shim'i entry point başına ekle
            f"RUN node -e \"const fs=require('fs');"
            f"const s=fs.readFileSync('{entry}','utf8');"
            f"if(!s.includes('prom-client'))"
            f"{{fs.writeFileSync('{entry}',`{node_shim}`+s);}}\"\n"
            "EXPOSE 8080\n"
            f'CMD ["node", "{entry}"]\n'
        )

    # ── Statik site (nginx) ───────────────────────────────────────────────────
    if (p / "index.html").exists() or list(p.glob("*.html")):
        # nginx:alpine BusyBox sed '\s' desteklemez → printf ile config yaz
        # Aynı zamanda stub_status ile /nginx_status endpoint'i açılır.
        # Not: nginx için http_requests_total Pushgateway üzerinden gelir;
        # stub_status metrikleri predictor.py tarafından okunur.
        nginx_conf = (
            "server {\\n"
            "    listen 8080;\\n"
            "    server_name localhost;\\n"
            "    location / {\\n"
            "        root /usr/share/nginx/html;\\n"
            "        index index.html index.htm;\\n"
            "        try_files \\$uri \\$uri/ /index.html;\\n"
            "    }\\n"
            "    location /nginx_status {\\n"
            "        stub_status on;\\n"
            "        access_log off;\\n"
            "        allow all;\\n"
            "    }\\n"
            "    location /metrics {\\n"
            "        stub_status on;\\n"
            "        access_log off;\\n"
            "    }\\n"
            "}\\n"
        )
        return (
            "FROM nginx:alpine\n"
            "COPY . /usr/share/nginx/html\n"
            f"RUN printf '{nginx_conf}' > /etc/nginx/conf.d/default.conf\n"
            "EXPOSE 8080\n"
        )

    return None  # Tanımlanamadı


def _analyze_project(folder: str) -> Dict[str, Any]:
    """Proje klasörünü derinlemesine analiz eder.

    Döndürür:
        type            : "python" | "node" | "static" | "docker" | "unknown"
        suggested_port  : int
        entry_point     : str
        dockerfile_exists : bool
        dockerfile_auto : bool
        issues          : List[dict]  — her biri {severity, title, detail, fixable}
        file_tree       : List[str]   — bulunan önemli dosyalar
    """
    p = Path(folder)
    issues: List[Dict] = []
    file_tree: List[str] = []

    def issue(severity: str, title: str, detail: str, fixable: bool = False):
        issues.append({"severity": severity, "title": title,
                       "detail": detail, "fixable": fixable})

    # ── Klasör erişim kontrolü ─────────────────────────────────────────────
    if not p.exists():
        issue("error", "Klasör bulunamadı", f"'{folder}' mevcut değil.")
        return {"type": "unknown", "issues": issues, "file_tree": [],
                "dockerfile_exists": False, "dockerfile_auto": False,
                "suggested_port": 8080, "entry_point": ""}

    if not p.is_dir():
        issue("error", "Bu bir klasör değil", "Lütfen bir klasör seçin, dosya değil.")
        return {"type": "unknown", "issues": issues, "file_tree": [],
                "dockerfile_exists": False, "dockerfile_auto": False,
                "suggested_port": 8080, "entry_point": ""}

    # ── Dosya tespiti ──────────────────────────────────────────────────────
    has_dockerfile    = (p / "Dockerfile").exists()
    has_requirements  = (p / "requirements.txt").exists()
    has_package_json  = (p / "package.json").exists()
    has_index_html    = (p / "index.html").exists()
    py_files          = list(p.glob("*.py"))
    html_files        = list(p.glob("*.html"))
    has_gitignore     = (p / ".gitignore").exists()
    has_env           = (p / ".env").exists()
    has_env_example   = (p / ".env.example").exists()
    has_lock_npm      = (p / "package-lock.json").exists()
    has_yarn_lock     = (p / "yarn.lock").exists()

    # Dosya ağacı (kullanıcıya gösterilecek)
    for name in [
        "Dockerfile", "requirements.txt", "package.json", "package-lock.json",
        "yarn.lock", "index.html", "index.js", "server.js", "app.py", "main.py",
        ".env.example", ".gitignore",
    ]:
        if (p / name).exists():
            file_tree.append(name)
    for f in py_files[:3]:
        if f.name not in file_tree:
            file_tree.append(f.name)
    for f in html_files[:2]:
        if f.name not in file_tree:
            file_tree.append(f.name)

    # ── Proje türü tespiti ─────────────────────────────────────────────────
    if has_dockerfile:
        proj_type = "docker"
        entry_point = "Dockerfile"
        suggested_port = 8080
        dockerfile_auto = False
        dockerfile_exists = True
    elif has_requirements or py_files:
        proj_type = "python"
        if (p / "app.py").exists():
            entry_point = "app.py"
        elif (p / "main.py").exists():
            entry_point = "main.py"
        elif py_files:
            entry_point = py_files[0].name
        else:
            entry_point = "app.py"
        suggested_port = 8080
        dockerfile_auto = True
        dockerfile_exists = False

        # Python özgü kontroller
        if not has_requirements:
            issue("warning", "requirements.txt eksik",
                  "Paket bağımlılıkları bulunamadı. Build sırasında hata çıkabilir.",
                  fixable=False)
        else:
            # requirements.txt içeriğini oku, web framework kontrol et
            try:
                reqs = (p / "requirements.txt").read_text(encoding="utf-8", errors="ignore").lower()
                if not any(fw in reqs for fw in ("flask", "fastapi", "uvicorn", "gunicorn",
                                                   "starlette", "tornado", "django", "aiohttp")):
                    issue("warning", "Web framework tespit edilemedi",
                          "requirements.txt içinde Flask/FastAPI/Django gibi bir framework bulunamadı. "
                          "Uygulamanız HTTP sunuyor mu?")
            except Exception:
                pass

        if not py_files:
            issue("error", "Python dosyası bulunamadı",
                  "Klasörde hiç .py dosyası yok. Giriş noktanız eksik olabilir.")

    elif has_package_json:
        proj_type = "node"
        entry_point = "index.js" if (p / "index.js").exists() else "server.js"
        suggested_port = 3000
        dockerfile_auto = True
        dockerfile_exists = False

        # Node özgü kontroller
        if not has_lock_npm and not has_yarn_lock:
            issue("info", "Lock dosyası yok",
                  "package-lock.json veya yarn.lock bulunamadı. "
                  "'npm install' çalıştırarak oluşturabilirsiniz.", fixable=False)

        try:
            import json as _json
            pkg = _json.loads((p / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "start" not in scripts:
                issue("warning", "npm start script yok",
                      "package.json içinde 'start' script tanımlanmamış. "
                      "Container başlatılamayabilir.", fixable=False)
        except Exception:
            pass

    elif has_index_html or html_files:
        proj_type = "static"
        entry_point = "index.html"
        suggested_port = 80
        dockerfile_auto = True
        dockerfile_exists = False

        if not has_index_html:
            issue("warning", "index.html kök dizinde değil",
                  "index.html bulunamadı. nginx root dizinini değiştirmeniz gerekebilir.")
    else:
        proj_type = "unknown"
        entry_point = ""
        suggested_port = 8080
        dockerfile_auto = False
        dockerfile_exists = False
        issue("error", "Proje türü tanımlanamadı",
              "requirements.txt, package.json, index.html veya Dockerfile bulunamadı. "
              "Klasörde bir Dockerfile oluşturarak devam edebilirsiniz.")

    # ── Ortak güvenlik / kalite kontrolleri ───────────────────────────────
    if has_env:
        issue("warning", ".env dosyası mevcut",
              "'.env' dosyası Docker image'a kopyalanacak ve gizli veriler sızabilir. "
              ".dockerignore ile hariç tutun veya .env.example kullanın.", fixable=False)

    # Büyük klasör kontrolü
    try:
        total_size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)
        if size_mb > 500:
            issue("warning", f"Büyük proje ({size_mb:.0f} MB)",
                  "Klasör çok büyük — node_modules, __pycache__ veya .git gibi "
                  "gereksiz dizinleri .dockerignore ile hariç tutun. "
                  "Aksi hâlde build çok yavaş olur.", fixable=False)
    except Exception:
        pass

    # node_modules kontrolü
    if (p / "node_modules").exists():
        issue("warning", "node_modules klasörü mevcut",
              "node_modules Docker image'a kopyalanacak. "
              ".dockerignore dosyasında 'node_modules' satırı ekleyin.", fixable=False)

    # __pycache__ kontrolü
    if list(p.glob("**/__pycache__")):
        issue("info", "__pycache__ dizinleri bulundu",
              ".dockerignore içinde '__pycache__' hariç tutmak build'i hızlandırır.")

    return {
        "type":              proj_type,
        "suggested_port":    suggested_port,
        "entry_point":       entry_point,
        "dockerfile_exists": dockerfile_exists,
        "dockerfile_auto":   dockerfile_auto,
        "issues":            issues,
        "file_tree":         file_tree,
    }


def format_bytes(b: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def run_ps(cmd: str, timeout: int = 30) -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, timeout=timeout
        )
        # bytes → str: önce utf-8, olmadı cp1254 (Türkçe Windows), olmadı latin-1
        def _decode(b: bytes) -> str:
            if not b:
                return ""
            for enc in ("utf-8", "cp1254", "latin-1"):
                try:
                    return b.decode(enc)
                except Exception:
                    continue
            return b.decode("utf-8", errors="replace")
        out = _decode(result.stdout).strip()
        err = _decode(result.stderr).strip()
        if result.returncode == 0:
            return True, out
        return False, err or out
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

# -------------------------------------------------
#  DATABASE LAYER
# -------------------------------------------------
class AppDatabase:
    def __init__(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    pin_hash TEXT,
                    tier TEXT DEFAULT 'free',
                    avatar_path TEXT,
                    created_at TEXT,
                    last_login TEXT,
                    token TEXT,
                    pin_attempts INTEGER DEFAULT 0,
                    pin_locked_until TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT,
                    details TEXT
                );
                CREATE TABLE IF NOT EXISTS hardware_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    memory_used_mb REAL,
                    memory_total_mb REAL,
                    disk_percent REAL,
                    disk_used_gb REAL,
                    disk_total_gb REAL,
                    network_sent_mb REAL,
                    network_recv_mb REAL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    folder TEXT,
                    port INTEGER NOT NULL,
                    service_name TEXT NOT NULL,
                    image TEXT NOT NULL,
                    deployed_at TEXT,
                    is_active INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS traffic_profile (
                    hour INTEGER PRIMARY KEY,
                    weight REAL DEFAULT 1.0,
                    label TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS domain_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    safety_margin REAL DEFAULT 0.3,
                    notes TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS hourly_rps_history (
                    date        TEXT NOT NULL,
                    hour        INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL DEFAULT 0,
                    avg_rps     REAL NOT NULL,
                    PRIMARY KEY (date, hour)
                );
                CREATE TABLE IF NOT EXISTS weekly_pattern (
                    day_of_week  INTEGER NOT NULL,
                    hour         INTEGER NOT NULL,
                    avg_rps      REAL NOT NULL DEFAULT 0.0,
                    sample_count INTEGER NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (day_of_week, hour)
                );
            """)
            self._ensure_default_profile()
            self._ensure_default_project()
            self.conn.commit()

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        h = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}:{h}"

    def _check_password(self, password: str, stored: str) -> bool:
        try:
            salt, h = stored.split(":", 1)
            return hashlib.sha256((salt + password).encode()).hexdigest() == h
        except Exception:
            return False

    def _hash_pin(self, pin: str) -> str:
        salt = secrets.token_hex(8)
        h = hashlib.sha256((salt + pin).encode()).hexdigest()
        return f"{salt}:{h}"

    def _check_pin(self, pin: str, stored: str) -> bool:
        try:
            salt, h = stored.split(":", 1)
            return hashlib.sha256((salt + pin).encode()).hexdigest() == h
        except Exception:
            return False

    def get_user(self) -> Optional[Dict]:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM users ORDER BY id LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None

    def save_user(self, name: str, email: str, password: str, tier: str = "free") -> bool:
        try:
            with self._lock:
                now = datetime.now().isoformat()
                token = secrets.token_urlsafe(32)
                ph = self._hash_password(password)
                self.conn.execute(
                    "INSERT INTO users (name,email,password_hash,tier,created_at,last_login,token) VALUES(?,?,?,?,?,?,?)",
                    (name, email, ph, tier, now, now, token)
                )
                self.conn.commit()
            return True
        except Exception:
            return False

    def verify_password(self, email: str, password: str) -> bool:
        with self._lock:
            cur = self.conn.execute("SELECT password_hash FROM users WHERE email=?", (email,))
            row = cur.fetchone()
            if not row:
                return False
            return self._check_password(password, row[0])

    def set_pin(self, user_id: int, pin: str) -> bool:
        try:
            with self._lock:
                ph = self._hash_pin(pin)
                self.conn.execute(
                    "UPDATE users SET pin_hash=?, pin_attempts=0, pin_locked_until=NULL WHERE id=?",
                    (ph, user_id)
                )
                self.conn.commit()
            return True
        except Exception:
            return False

    def verify_pin(self, user_id: int, pin: str) -> Tuple[bool, Optional[str]]:
        with self._lock:
            cur = self.conn.execute(
                "SELECT pin_hash, pin_attempts, pin_locked_until FROM users WHERE id=?",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return False, "User not found"
            pin_hash, attempts, locked_until = row
            if locked_until:
                try:
                    locked_dt = datetime.fromisoformat(locked_until)
                    if datetime.now() < locked_dt:
                        remaining = int((locked_dt - datetime.now()).total_seconds())
                        mins = remaining // 60
                        secs = remaining % 60
                        return False, f"Locked. Try again in {mins}m {secs}s"
                except Exception:
                    pass
            if not pin_hash:
                return False, "No PIN set"
            if self._check_pin(pin, pin_hash):
                self.conn.execute(
                    "UPDATE users SET pin_attempts=0, pin_locked_until=NULL, last_login=? WHERE id=?",
                    (datetime.now().isoformat(), user_id)
                )
                self.conn.commit()
                return True, None
            else:
                new_attempts = (attempts or 0) + 1
                locked_until_val = None
                if new_attempts >= 10:
                    locked_until_val = (datetime.now() + timedelta(minutes=30)).isoformat()
                elif new_attempts >= 3:
                    locked_until_val = (datetime.now() + timedelta(minutes=5)).isoformat()
                self.conn.execute(
                    "UPDATE users SET pin_attempts=?, pin_locked_until=? WHERE id=?",
                    (new_attempts, locked_until_val, user_id)
                )
                self.conn.commit()
                msg = "Incorrect PIN"
                if locked_until_val:
                    if new_attempts >= 10:
                        msg = "Too many attempts. Locked for 30 minutes."
                    else:
                        msg = "Too many attempts. Locked for 5 minutes."
                return False, msg

    def reset_pin_attempts(self, user_id: int):
        with self._lock:
            self.conn.execute(
                "UPDATE users SET pin_attempts=0, pin_locked_until=NULL WHERE id=?",
                (user_id,)
            )
            self.conn.commit()

    def get_setting(self, key: str, default=None) -> Optional[str]:
        with self._lock:
            cur = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else default

    def set_setting(self, key: str, value: str):
        with self._lock:
            self.conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value))
            )
            self.conn.commit()

    def log_activity(self, event_type: str, description: str, details: Optional[Dict] = None):
        with self._lock:
            self.conn.execute(
                "INSERT INTO activity_log(timestamp,event_type,description,details) VALUES(?,?,?,?)",
                (datetime.now().isoformat(), event_type, description,
                 json.dumps(details) if details else None)
            )
            self.conn.commit()

    def get_activity_log(self, limit: int = 100, event_type: Optional[str] = None,
                          search: Optional[str] = None, from_dt: Optional[str] = None,
                          to_dt: Optional[str] = None) -> List[Dict]:
        with self._lock:
            q = "SELECT * FROM activity_log WHERE 1=1"
            params = []
            if event_type and event_type != "All":
                q += " AND event_type=?"; params.append(event_type)
            if search:
                q += " AND (description LIKE ? OR event_type LIKE ?)"; params += [f"%{search}%", f"%{search}%"]
            if from_dt:
                q += " AND timestamp>=?"; params.append(from_dt)
            if to_dt:
                q += " AND timestamp<=?"; params.append(to_dt)
            q += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            cur = self.conn.execute(q, params)
            return [dict(r) for r in cur.fetchall()]

    def save_hardware_snapshot(self, data: Dict):
        with self._lock:
            self.conn.execute(
                """INSERT INTO hardware_snapshots
                   (timestamp,cpu_percent,memory_percent,memory_used_mb,memory_total_mb,
                    disk_percent,disk_used_gb,disk_total_gb,network_sent_mb,network_recv_mb)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (data.get("timestamp", datetime.now().isoformat()),
                 data.get("cpu_percent"), data.get("memory_percent"),
                 data.get("memory_used_mb"), data.get("memory_total_mb"),
                 data.get("disk_percent"), data.get("disk_used_gb"),
                 data.get("disk_total_gb"), data.get("network_sent_mb"),
                 data.get("network_recv_mb"))
            )
            self.conn.commit()

    def get_hardware_history(self, hours: int = 24) -> List[Dict]:
        with self._lock:
            since = (datetime.now() - timedelta(hours=hours)).isoformat()
            cur = self.conn.execute(
                "SELECT * FROM hardware_snapshots WHERE timestamp>=? ORDER BY timestamp",
                (since,)
            )
            return [dict(r) for r in cur.fetchall()]

    def update_user(self, user_id: int, **kwargs):
        # Whitelist: sadece izin verilen alanlar guncellenebilir (SQL injection onlemi)
        _ALLOWED_USER_FIELDS = {"username", "email", "avatar", "theme", "language", "notifications"}
        with self._lock:
            for k, v in kwargs.items():
                if k not in _ALLOWED_USER_FIELDS:
                    raise ValueError(f"update_user: izin verilmeyen alan: {k!r}")
                self.conn.execute(f"UPDATE users SET {k}=? WHERE id=?", (v, user_id))
            self.conn.commit()

    # ── Domain Profil Yönetimi ───────────────────────────────────────────────

    def _ensure_default_profile(self):
        cur = self.conn.execute("SELECT COUNT(*) FROM traffic_profile")
        if cur.fetchone()[0] == 0:
            self.conn.executemany(
                "INSERT INTO traffic_profile (hour, weight, label) VALUES (?,?,?)",
                [(h, 1.0, "") for h in range(24)]
            )

    def get_traffic_profile(self) -> dict:
        with self._lock:
            cur = self.conn.execute("SELECT hour, weight, label FROM traffic_profile ORDER BY hour")
            return {row[0]: {"weight": row[1], "label": row[2]} for row in cur.fetchall()}

    def set_hour_weight(self, hour: int, weight: float, label: str = "") -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO traffic_profile (hour, weight, label) VALUES (?,?,?)",
                (hour, round(max(0.1, min(3.0, weight)), 2), label)
            )
            self.conn.commit()

    def set_full_profile(self, weights: dict) -> None:
        with self._lock:
            self.conn.executemany(
                "INSERT OR REPLACE INTO traffic_profile (hour, weight, label) VALUES (?,?,?)",
                [(h, round(max(0.1, min(3.0, w.get("weight", 1.0))), 2), w.get("label", ""))
                 for h, w in weights.items()]
            )
            self.conn.commit()

    def get_domain_events(self) -> list:
        with self._lock:
            cur = self.conn.execute(
                "SELECT id, name, event_date, safety_margin, notes FROM domain_events ORDER BY event_date"
            )
            return [dict(zip(["id","name","event_date","safety_margin","notes"], r)) for r in cur.fetchall()]

    def add_domain_event(self, name: str, event_date: str, safety_margin: float = 0.3, notes: str = "") -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO domain_events (name, event_date, safety_margin, notes) VALUES (?,?,?,?)",
                (name, event_date, round(max(0.0, min(1.0, safety_margin)), 2), notes)
            )
            self.conn.commit()
            return cur.lastrowid

    def delete_domain_event(self, event_id: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM domain_events WHERE id=?", (event_id,))
            self.conn.commit()

    def build_profile_json(self) -> dict:
        profile = self.get_traffic_profile()
        events  = self.get_domain_events()
        return {
            "hours": {str(h): v["weight"] for h, v in profile.items()},
            "events": [{"name": e["name"], "date": e["event_date"],
                        "margin": e["safety_margin"]} for e in events]
        }

    # ── Saatlik RPS Geçmişi ─────────────────────────────────────────────────
    def save_hourly_rps(self, date_str: str, hour: int, avg_rps: float) -> None:
        """Prometheus'tan çekilen saatlik RPS ortalamasını DB'ye kaydeder.
        day_of_week: 0=Pazartesi … 6=Pazar
        """
        import datetime as _dt
        try:
            d = _dt.date.fromisoformat(date_str)
            dow = d.weekday()   # 0=Mon … 6=Sun
        except Exception:
            dow = 0
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO hourly_rps_history "
                "(date, hour, day_of_week, avg_rps) VALUES (?,?,?,?)",
                (date_str, hour, dow, round(avg_rps, 4))
            )
            self.conn.commit()

    def get_hourly_rps_history(self, days: int = 7) -> dict:
        """Son N günün saatlik RPS ortalamalarını döner: {hour: avg_rps}"""
        import datetime as _dt
        cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
        with self._lock:
            cur = self.conn.execute(
                "SELECT hour, AVG(avg_rps) FROM hourly_rps_history "
                "WHERE date >= ? GROUP BY hour ORDER BY hour",
                (cutoff,)
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    def rebuild_weekly_pattern(self) -> None:
        """
        Haftalık örüntü tablosunu sıfırdan hesaplar.
        Her (gün, saat) çifti için geçmiş ortalaması → weekly_pattern tablosuna yazar.
        Danışman (ProfileAdvisor) bu tabloyu kullanarak profil ağırlıklarını günceller.
        """
        import datetime as _dt
        now_str = _dt.datetime.now().isoformat(timespec="seconds")
        with self._lock:
            cur = self.conn.execute(
                "SELECT day_of_week, hour, AVG(avg_rps), COUNT(*) "
                "FROM hourly_rps_history GROUP BY day_of_week, hour"
            )
            rows = cur.fetchall()
            if not rows:
                return
            self.conn.executemany(
                "INSERT OR REPLACE INTO weekly_pattern "
                "(day_of_week, hour, avg_rps, sample_count, last_updated) "
                "VALUES (?,?,?,?,?)",
                [(int(r[0]), int(r[1]), round(r[2], 4), int(r[3]), now_str)
                 for r in rows]
            )
            self.conn.commit()

    def get_weekly_pattern(self) -> dict:
        """weekly_pattern tablosunu döner: {(day_of_week, hour): avg_rps}"""
        with self._lock:
            cur = self.conn.execute(
                "SELECT day_of_week, hour, avg_rps, sample_count "
                "FROM weekly_pattern ORDER BY day_of_week, hour"
            )
            return {(r[0], r[1]): {"avg_rps": r[2], "samples": r[3]}
                    for r in cur.fetchall()}

    def compute_auto_weights(self) -> dict:
        """
        Haftalık örüntüden otomatik saat ağırlıkları hesaplar.
        Mantık: bu saatin ortalaması / tüm saatlerin genel ortalaması
        Örnek: Saat 14 genel ortalamanın 1.8 katıysa → weight=1.8
        Sonuç: {hour(0-23): weight(0.1-3.0)}
        """
        pattern = self.get_weekly_pattern()
        if not pattern:
            return {}

        # Tüm (gün, saat) çiftlerinin RPS ortalamasını saat bazında grupla
        hour_totals: dict[int, list] = {h: [] for h in range(24)}
        for (dow, hour), info in pattern.items():
            if info["samples"] >= 2:   # En az 2 örnek şartı
                hour_totals[hour].append(info["avg_rps"])

        hour_avgs = {h: sum(vals)/len(vals)
                     for h, vals in hour_totals.items() if vals}
        if not hour_avgs:
            return {}

        overall_avg = sum(hour_avgs.values()) / len(hour_avgs)
        if overall_avg < 0.01:
            return {}

        weights = {}
        for hour, avg in hour_avgs.items():
            raw = avg / overall_avg
            weights[hour] = round(max(0.1, min(3.0, raw)), 2)
        return weights

    # ── Proje Yönetimi ──────────────────────────────────────────────────────

    def _ensure_default_project(self):
        """Projects tablosu boşsa, varsayılan autoscaleops-app projesini ekle."""
        cur = self.conn.execute("SELECT COUNT(*) FROM projects")
        if cur.fetchone()[0] == 0:
            now = datetime.now().isoformat()
            self.conn.execute(
                "INSERT OR IGNORE INTO projects "
                "(name, folder, port, service_name, image, deployed_at, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("autoscaleops-app", None, 8080,
                 "autoscaleops-app-service", "autoscaleops-app:latest", now, 1)
            )
            for k, v in [
                ("active_project_name",    "autoscaleops-app"),
                ("active_project_port",    "8080"),
                ("active_project_service", "autoscaleops-app-service"),
            ]:
                self.conn.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO NOTHING", (k, v)
                )
            # Dashboard için JSON yaz
            _write_active_project_json("autoscaleops-app", 8080, "autoscaleops-app-service")

    def get_all_projects(self) -> list:
        """Deploy edilmiş tüm projeleri döndür (aktif önce)."""
        with self._lock:
            cur = self.conn.execute(
                "SELECT * FROM projects ORDER BY is_active DESC, deployed_at DESC"
            )
            return [dict(r) for r in cur.fetchall()]

    def add_project(self, name: str, folder: str, port: int,
                    service_name: str, image: str) -> bool:
        """Yeni projeyi DB'ye kaydet. Zaten varsa güncelle."""
        try:
            with self._lock:
                now = datetime.now().isoformat()
                self.conn.execute(
                    "INSERT INTO projects "
                    "(name, folder, port, service_name, image, deployed_at, is_active) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0) "
                    "ON CONFLICT(name) DO UPDATE SET "
                    "folder=excluded.folder, port=excluded.port, "
                    "service_name=excluded.service_name, image=excluded.image, "
                    "deployed_at=excluded.deployed_at",
                    (name, folder, port, service_name, image, now)
                )
                self.conn.commit()
            return True
        except Exception:
            return False

    def set_active_project(self, name: str) -> bool:
        """Verilen projeyi aktif yap; settings tablosunu güncelle."""
        try:
            with self._lock:
                # Önce proje var mı?
                cur = self.conn.execute(
                    "SELECT port, service_name FROM projects WHERE name=?", (name,)
                )
                row = cur.fetchone()
                if not row:
                    return False
                port, service = row
                # Hepsini pasif yap, sonra seçileni aktif yap
                self.conn.execute("UPDATE projects SET is_active=0")
                self.conn.execute(
                    "UPDATE projects SET is_active=1 WHERE name=?", (name,)
                )
                # Settings güncelle
                for k, v in [
                    ("active_project_name",    name),
                    ("active_project_port",    str(port)),
                    ("active_project_service", service),
                ]:
                    self.conn.execute(
                        "INSERT INTO settings(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (k, v)
                    )
                self.conn.commit()
            return True
        except Exception:
            return False

    def delete_project(self, name: str) -> bool:
        """Projeyi DB'den sil. Aktif projeyi silmeye izin verme."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    "SELECT is_active FROM projects WHERE name=?", (name,)
                )
                row = cur.fetchone()
                if not row or row[0] == 1:
                    return False  # Aktif proje silinemez
                self.conn.execute("DELETE FROM projects WHERE name=?", (name,))
                self.conn.commit()
            return True
        except Exception:
            return False

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

# -------------------------------------------------
#  SYSTEM OPERATIONS LAYER
# -------------------------------------------------
class SystemOps:
    def __init__(self, db: 'AppDatabase'):
        self.db = db
        self._port_forward_procs: Dict[str, subprocess.Popen] = {}
        self._dashboard_proc: Optional[subprocess.Popen] = None
        self._tunnel_proc: Optional[subprocess.Popen] = None
        self._tunnel_url: Optional[str] = None

    # -- Instance ----------------------------------
    def get_instance(self) -> Optional[Dict]:
        try:
            if INSTANCE_PATH.exists():
                data = json.loads(INSTANCE_PATH.read_text(encoding="utf-8"))
                # Eski hash-tabanlı profilleri normalize et
                changed = False
                if data.get("minikube_profile", "autoscaleops") != "autoscaleops":
                    data["minikube_profile"] = "autoscaleops"
                    changed = True
                if data.get("namespace", "autoscaleops") != "autoscaleops":
                    data["namespace"] = "autoscaleops"
                    changed = True
                if changed:
                    INSTANCE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return data
        except Exception:
            pass
        return None

    def ensure_instance(self) -> Dict:
        existing = self.get_instance()
        if existing:
            return existing
        try:
            mac = hex(uuid.getnode()).replace("0x", "")
            hostname = socket.gethostname()
            raw = f"{hostname}-{mac}"
            instance_id = hashlib.sha256(raw.encode()).hexdigest()[:8]
            data = {
                "instance_id": instance_id,
                "namespace": "autoscaleops",
                "minikube_profile": "autoscaleops",
                "created_at": datetime.now().isoformat()
            }
            APP_DIR.mkdir(parents=True, exist_ok=True)
            INSTANCE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return data
        except Exception:
            fallback_id = secrets.token_hex(4)
            data = {
                "instance_id": fallback_id,
                "namespace": "autoscaleops",
                "minikube_profile": "autoscaleops",
                "created_at": datetime.now().isoformat()
            }
            APP_DIR.mkdir(parents=True, exist_ok=True)
            INSTANCE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return data

    # -- Prerequisite checks ----------------------
    def check_docker(self) -> Dict:
        ok, out = run_ps("docker --version 2>&1")
        return {"ok": ok, "version": out.strip() if ok else None, "name": "Docker Desktop"}

    def check_docker_running(self) -> Dict:
        # "docker info" returns exit code 0 only when daemon is reachable.
        # Pipe to Select-String can swallow the exit code, so check directly.
        ok, out = run_ps("docker info 2>&1; exit $LASTEXITCODE")
        running = ok and "ERROR" not in out.upper() and "error during connect" not in out.lower()
        # Extract server version for display if available
        ver = None
        for line in out.splitlines():
            if "Server Version" in line:
                ver = line.strip()
                break
        return {"ok": running, "version": ver if running else None, "name": "Docker Running"}

    def check_minikube(self) -> Dict:
        ok, out = run_ps("minikube version --short 2>&1")
        return {"ok": ok, "version": out.strip() if ok else None, "name": "Minikube"}

    def check_kubectl(self) -> Dict:
        # --short is deprecated since kubectl 1.28+, use plain --client instead
        ok, out = run_ps("kubectl version --client 2>&1")
        ver = None
        if ok:
            for line in out.splitlines():
                if "Client Version" in line or "clientVersion" in line:
                    ver = line.strip()
                    break
            if not ver:
                ver = out.splitlines()[0].strip() if out.strip() else "OK"
        return {"ok": ok, "version": ver, "name": "kubectl"}

    def check_helm(self) -> Dict:
        ok, out = run_ps("helm version --short 2>&1")
        return {"ok": ok, "version": out.strip() if ok else None, "name": "Helm"}

    def check_python(self) -> Dict:
        ok, out = run_ps("python --version 2>&1")
        ver = out.strip() if ok else None
        return {"ok": ok, "version": ver, "name": "Python Paketleri"}

    def all_prereq_checks(self) -> List[Dict]:
        return [
            self.check_docker(),
            self.check_docker_running(),
            self.check_minikube(),
            self.check_kubectl(),
            self.check_helm(),
            self.check_python(),
        ]

    # -- Cluster operations -----------------------
    def get_cluster_status(self) -> Dict:
        instance = self.get_instance()
        if not instance:
            return {"running": False, "node_count": 0, "pod_count": 0, "namespace": "unknown"}
        profile = instance.get("minikube_profile", "autoscaleops")
        namespace = instance.get("namespace", "autoscaleops")
        ok, status_out = run_ps(f"minikube status -p {profile} 2>&1")
        running = ok and "Running" in status_out
        node_count = 0
        pod_count = 0
        if running:
            _, node_out = run_ps(
                f"kubectl get nodes --context={profile} --no-headers 2>&1 | Measure-Object -Line | Select-Object -ExpandProperty Lines"
            )
            try:
                node_count = int(node_out.strip())
            except Exception:
                node_count = 1
            _, pod_out = run_ps(
                f"kubectl get pods -n {namespace} --no-headers 2>&1 | Measure-Object -Line | Select-Object -ExpandProperty Lines"
            )
            try:
                pod_count = int(pod_out.strip())
            except Exception:
                pod_count = 0
        return {"running": running, "node_count": node_count, "pod_count": pod_count, "namespace": namespace}

    def start_cluster(self, progress_cb=None):
        def emit(msg, level="info"):
            if progress_cb:
                progress_cb(msg, level)

        emit("Docker Desktop kontrol ediliyor...", "info")
        if not self.check_docker_running().get("ok", False):
            return False, (
                "Docker Desktop çalışmıyor!\n\n"
                "Minikube, Docker sürücüsüne ihtiyaç duyuyor. "
                "Docker Desktop'u başlatın, sistem tepsisinde balina ikonu "
                "görününce tekrar deneyin."
            )

        instance = self.ensure_instance()
        profile = instance["minikube_profile"]
        namespace = instance["namespace"]

        emit("Minikube durumu kontrol ediliyor...", "info")
        ok, out = run_ps(f"minikube status -p {profile} 2>&1")
        if ok and "Running" in out:
            emit("Minikube zaten çalışıyor.", "ok")
        else:
            # Profil mevcut mu kontrol et — mevcutsa kaynak flagleri değiştirme
            _, profile_list = run_ps("minikube profile list 2>&1")
            profile_exists = profile in (profile_list or "")

            # $ErrorActionPreference=Continue → PowerShell NativeCommandError bastırılır
            ps_prefix = '$ErrorActionPreference="Continue"; '
            if profile_exists:
                emit(f"Mevcut cluster başlatılıyor: {profile} …", "info")
                ok, out = run_ps(
                    ps_prefix + f"minikube start -p {profile} --driver=docker 2>&1; exit $LASTEXITCODE",
                    timeout=300
                )
            else:
                emit(f"Yeni cluster oluşturuluyor: {profile} (CPU:4, RAM:6 GB) …", "info")
                ok, out = run_ps(
                    ps_prefix + f"minikube start -p {profile} --driver=docker --cpus=4 --memory=6144 2>&1; exit $LASTEXITCODE",
                    timeout=300
                )

            if not ok:
                # NativeCommandError veya "cannot change" olsa bile cluster başlamış olabilir
                _, st2 = run_ps(f"minikube status -p {profile} 2>&1", timeout=20)
                if "Running" in st2:
                    emit("Cluster başlatıldı (uyarılar yoksayıldı).", "ok")
                    ok = True
                if not ok:
                    emit(f"Cluster başlatılamadı: {out}", "error")
                    return False, out
            emit("Cluster hazır.", "ok")

        emit("Setting kubectl context...", "info")
        run_ps(f"kubectl config use-context {profile} 2>&1")

        emit(f"Ensuring namespace {namespace}...", "info")
        run_ps(f"kubectl create namespace {namespace} --dry-run=client -o yaml | kubectl apply -f - 2>&1")

        emit("Checking KEDA...", "info")
        ok, out = run_ps("helm list -n keda 2>&1")
        if "keda" not in out:
            emit("Installing KEDA via Helm...", "info")
            run_ps(
                "helm repo add kedacore https://kedacore.github.io/charts 2>&1; helm repo update 2>&1; "
                "helm install keda kedacore/keda --namespace keda --create-namespace 2>&1",
                timeout=180
            )
        else:
            emit("KEDA already installed.", "ok")

        emit("Checking Prometheus stack...", "info")
        ok, out = run_ps("helm list -n monitoring 2>&1")
        if "prometheus" not in out:
            emit("Installing Prometheus stack via Helm...", "info")
            run_ps(
                "helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>&1; "
                "helm repo update 2>&1; "
                "helm install prometheus prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace 2>&1",
                timeout=300
            )
            emit("Installing Prometheus Pushgateway...", "info")
            run_ps(
                "helm install prometheus-pushgateway prometheus-community/prometheus-pushgateway "
                "--namespace monitoring 2>&1",
                timeout=120
            )
        else:
            emit("Prometheus already installed.", "ok")

        emit("Deploying AutoScaleOps application...", "info")
        charts_dir = Path(__file__).parent / "charts" / "autoscaleops"
        if charts_dir.exists():
            # Önce namespace'de bu release zaten kurulu mu kontrol et
            dep_ok, dep_out = run_ps(f"helm list -n {namespace} 2>&1")
            if dep_ok and namespace in dep_out:
                emit("Application already deployed.", "ok")
            else:
                ok, out = run_ps(
                    f"helm upgrade --install {namespace} {str(charts_dir)} "
                    f"--namespace {namespace} 2>&1",
                    timeout=180
                )
                if ok:
                    emit("Application deployed.", "ok")
                else:
                    emit(f"Helm deploy warning: {out[:200]}", "warn")
        else:
            emit("Helm chart not found, skipping app deploy.", "warn")

        emit("Applying Prometheus scrape config...", "info")
        self.apply_scrape_config(namespace)

        emit("Starting port forwards...", "info")
        self.start_port_forwards(namespace)

        emit("Starting Streamlit dashboard...", "info")
        self.start_dashboard()
        emit("Waiting for dashboard to be ready...", "info")
        self._wait_for_dashboard(timeout=30)

        emit("Cluster startup complete!", "ok")
        return True, "Cluster started successfully"

    def stop_cluster(self, progress_cb=None):
        """Sadece Minikube'u durdurur.

        Port-forward / dashboard / tunnel kapatma işlemleri StopWorker
        tarafından doğru sırayla yapılır; burada tekrar çağrılmaz.
        """
        def emit(msg, level="info"):
            if progress_cb:
                progress_cb(msg, level)

        instance = self.get_instance()
        if instance:
            profile = instance.get("minikube_profile", "autoscaleops")
            emit(f"Minikube durduruluyor ({profile})…", "info")
            ok, out = run_ps(f"minikube stop -p {profile} 2>&1", timeout=120)
            if ok:
                emit("Minikube durduruldu.", "ok")
            else:
                emit(f"Uyarı: {out[:200]}", "warn")
        else:
            emit("Cluster instance bulunamadı, atlanıyor.", "warn")
        return True, "Cluster stopped"

    def restart_cluster(self, progress_cb=None):
        self.stop_cluster(progress_cb)
        time.sleep(2)
        return self.start_cluster(progress_cb)

    # -- Service checks ---------------------------
    def _http_ok(self, url: str, timeout: int = 3) -> bool:
        try:
            r = requests.get(url, timeout=timeout)
            return r.status_code < 400
        except Exception:
            return False

    def check_prometheus(self) -> bool:
        return self._http_ok("http://localhost:9090/-/ready")

    def check_pushgateway(self) -> bool:
        return self._http_ok("http://localhost:9091/-/ready")

    def check_app(self) -> bool:
        port = int(self.db.get_setting("active_project_port", "8080"))
        return self._http_ok(f"http://localhost:{port}/health") or self._http_ok(f"http://localhost:{port}/")

    def check_dashboard(self) -> bool:
        return self._http_ok("http://localhost:8501/")

    def check_all_services(self) -> Dict[str, bool]:
        return {
            "prometheus": self.check_prometheus(),
            "pushgateway": self.check_pushgateway(),
            "app": self.check_app(),
            "dashboard": self.check_dashboard(),
        }

    # -- Port helpers ------------------------------
    def _is_port_open(self, port: int) -> bool:
        """Verilen port'ta bir şeyin dinleyip dinlemediğini TCP ile test eder."""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            return False

    # -- Port forwards ----------------------------
    def start_port_forwards(self, namespace: str):
        """Port-forward başlat. Portlar doluysa otomatik boş port seçer.

        Her servis için:
        1. Mevcut proc canlıysa ve port açıksa → dokunma
        2. Değilse → proc'u kapat, boş port bul, yeniden başlat
        Uygulama portu değişirse DB + JSON güncellenir.
        """
        active_svc      = self.db.get_setting("active_project_service", "autoscaleops-app-service")
        active_svc_port = int(self.db.get_setting("active_project_port", "8080"))
        active_name     = self.db.get_setting("active_project_name", "")

        # Servisin gerçek K8s portunu otomatik oku (DB'deki local port ile farklı olabilir)
        app_k8s_port = active_svc_port  # varsayılan
        if active_svc:
            _, svc_out = run_ps(
                f"kubectl get svc {active_svc} -n {namespace} "
                f"--no-headers -o custom-columns=PORT:.spec.ports[0].port 2>&1",
                timeout=8
            )
            svc_out = svc_out.strip()
            if svc_out.isdigit():
                app_k8s_port = int(svc_out)

        # Servis tanımları: (key, tercih_local_port, k8s_svc_adı, k8s_svc_port, namespace)
        SERVICES = [
            ("prometheus",  9090, "prometheus-kube-prometheus-prometheus", 9090, "monitoring"),
            ("pushgateway", 9091, "pushgateway-prometheus-pushgateway",     9091, "monitoring"),
            ("app",         active_svc_port, active_svc, app_k8s_port, namespace),
        ]

        used_ports: set = set()

        for key, preferred, svc, svc_port, ns in SERVICES:
            existing = self._port_forward_procs.get(key)

            # Proc canlı ve port açık → HTTP seviyesinde de doğrula
            # (Pod restart sonrası TCP open ama HTTP broken olabilir — tüm servisler için kontrol)
            if existing and existing.poll() is None and self._is_port_open(preferred):
                if key == "app":
                    _base = f"http://localhost:{preferred}"
                    _ok = self._http_ok(f"{_base}/") or self._http_ok(f"{_base}/health")
                elif key == "prometheus":
                    _ok = self._http_ok(f"http://localhost:{preferred}/-/ready")
                elif key == "pushgateway":
                    _ok = (self._http_ok(f"http://localhost:{preferred}/-/ready") or
                           self._http_ok(f"http://localhost:{preferred}/"))
                else:
                    _ok = True  # Bilinmeyen servis için TCP yeterli

                if _ok:
                    used_ports.add(preferred)
                    continue
                # HTTP çalışmıyor → kırık process'i zorla öldür, yeniden başlat
                try:
                    existing.terminate()
                except Exception:
                    pass

            # Proc'u temizle
            if existing:
                try:
                    existing.terminate()
                except Exception:
                    pass

            # Boş port bul — zaten kullandıklarımızı atla
            # _is_port_open=True → dolu (birileri dinliyor), False → boş (bind edebiliriz)
            local_port = preferred
            if self._is_port_open(local_port) or local_port in used_ports:
                for candidate in [preferred] + list(range(preferred + 1, preferred + 220)):
                    if candidate not in used_ports:
                        try:
                            import socket as _sock
                            with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
                                s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                                s.bind(("127.0.0.1", candidate))
                            local_port = candidate
                            break
                        except OSError:
                            continue

            used_ports.add(local_port)

            # Uygulama portu değiştiyse DB + JSON güncelle
            if key == "app" and local_port != active_svc_port:
                self.db.set_setting("active_project_port", str(local_port))
                _write_active_project_json(active_name, local_port, active_svc)

            cmd = f"kubectl port-forward svc/{svc} {local_port}:{svc_port} -n {ns}"
            try:
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                self._port_forward_procs[key] = proc
            except Exception:
                pass

    def _is_port_open_for_bind(self, port: int) -> bool:
        """Porta bind edebiliyor muyuz? (Port boş mu?)"""
        import socket as _sock
        try:
            with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
                s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False

    def stop_port_forwards(self):
        for name, proc in list(self._port_forward_procs.items()):
            try:
                proc.terminate()
            except Exception:
                pass
        self._port_forward_procs.clear()
        run_ps("Get-Process -Name kubectl -ErrorAction SilentlyContinue | Stop-Process -Force 2>&1")

    def _wait_for_port(self, port: int, timeout: int = 10) -> bool:
        """Port TCP seviyesinde dinlenene kadar bekle (max timeout saniye).
        Port-forward process başlatıldıktan sonra hazır olması için kullanılır.
        """
        import time as _t
        deadline = _t.time() + timeout
        while _t.time() < deadline:
            if self._is_port_open(port):
                return True
            _t.sleep(0.4)
        return False

    def get_port_forward_status(self) -> Dict[str, bool]:
        result = {}
        for name, proc in self._port_forward_procs.items():
            result[name] = proc.poll() is None
        return result

    # -- Dashboard --------------------------------
    def start_dashboard(self) -> Tuple[bool, str]:
        # plotly kurulu değilse sessizce yükle
        try:
            import importlib
            if importlib.util.find_spec("plotly") is None:
                subprocess.run(
                    ["python", "-m", "pip", "install", "plotly>=5.18.0", "-q"],
                    timeout=120, capture_output=True
                )
        except Exception:
            pass

        # Zaten HTTP cevap veriyorsa dokunma
        if self.check_dashboard():
            return True, "Dashboard zaten çalışıyor"
        # Ölü proc'u temizle; canlı bir proc varsa bırak
        if self._dashboard_proc and self._dashboard_proc.poll() is not None:
            self._dashboard_proc = None
        # Sadece proc yoksa yeni process başlat
        if self._dashboard_proc is None:
            # Farklı kurulum konumlarını sırayla dene (worktree, ana proje, vs.)
            candidates = [
                Path(__file__).parent / "dashboard" / "dashboard.py",
                Path(__file__).parent.parent.parent / "dashboard" / "dashboard.py",
                Path(__file__).parent.parent / "dashboard" / "dashboard.py",
            ]
            dashboard_py = next((p for p in candidates if p.exists()), None)
            if not dashboard_py:
                return False, "dashboard/dashboard.py bulunamadı"
            try:
                log_dir = APP_DIR / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_path = log_dir / "streamlit.log"
                log_f = open(log_path, "a", encoding="utf-8")
                self._dashboard_proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     f'streamlit run "{dashboard_py}" --server.port 8501 --server.headless true 2>&1'],
                    stdout=log_f, stderr=log_f
                )
            except Exception as e:
                return False, str(e)
        return True, "Dashboard başlatıldı"

    def _wait_for_dashboard(self, timeout: int = 30):
        """Port 8501'in TCP olarak dinlemeye başlamasını bekler (maks timeout saniye).
        ClusterWorker thread'inde güvenle çağrılabilir — UI donmaz."""
        for _ in range(timeout):
            if self._is_port_open(8501):
                time.sleep(1)  # Streamlit HTTP handler'ının hazır olması için 1 sn daha
                return
            time.sleep(1)
        # timeout doldu — devam et

    def stop_dashboard(self):
        if self._dashboard_proc:
            try:
                self._dashboard_proc.terminate()
            except Exception:
                pass
            self._dashboard_proc = None
        run_ps("Get-Process -Name streamlit -ErrorAction SilentlyContinue | Stop-Process -Force 2>&1")

    def is_dashboard_running(self) -> bool:
        if self._dashboard_proc and self._dashboard_proc.poll() is None:
            return True
        return self.check_dashboard()

    def open_dashboard_browser(self):
        webbrowser.open("http://localhost:8501")

    # -- Prometheus metrics -----------------------
    def get_current_rps(self) -> float:
        try:
            r = requests.get(
                "http://localhost:9090/api/v1/query",
                params={"query": "sum(rate(http_requests_total[1m]))"},
                timeout=3
            )
            data = r.json()
            result = data.get("data", {}).get("result", [])
            if result:
                return float(result[0]["value"][1])
        except Exception:
            pass
        return 0.0

    def get_pod_count(self) -> int:
        instance = self.get_instance()
        if not instance:
            return 0
        namespace = instance.get("namespace", "autoscaleops")
        ok, out = run_ps(
            f"kubectl get pods -n {namespace} --no-headers 2>&1 | "
            "Where-Object { $_ -match 'Running' } | Measure-Object -Line | Select-Object -ExpandProperty Lines"
        )
        try:
            return int(out.strip())
        except Exception:
            return 0

    def get_keda_status(self) -> bool:
        instance = self.get_instance()
        if not instance:
            return False
        namespace = instance.get("namespace", "autoscaleops")
        ok, out = run_ps(f"kubectl get scaledobject -n {namespace} 2>&1")
        return ok and "autoscaleops" in out.lower()

    def get_predicted_rps(self) -> Optional[float]:
        try:
            r = requests.get(
                "http://localhost:9090/api/v1/query",
                params={"query": "predicted_rps_30min"},
                timeout=3
            )
            data = r.json()
            result = data.get("data", {}).get("result", [])
            if result:
                return float(result[0]["value"][1])
        except Exception:
            pass
        return None

    # -- Tunnel -----------------------------------
    def ensure_ngrok(self, progress_cb=None) -> Tuple[bool, str]:
        """ngrok PATH'te ya da ~/.autoscaleops/tools/ altında yoksa otomatik indir.
        Döner: (True, ngrok_cmd) başarılı, (False, hata_mesajı) başarısız."""
        def emit(m):
            if progress_cb:
                progress_cb(m, "info")

        # 1. PATH'te mi?
        ok, out = run_ps("where.exe ngrok 2>$null")
        if ok and out.strip():
            return True, "ngrok"

        # 2. Daha önce indirdik mi?
        if NGROK_EXE.exists():
            return True, str(NGROK_EXE)

        # 3. İndir
        emit("ngrok bulunamadı, otomatik indiriliyor (~15 MB)…")
        try:
            import urllib.request
            import zipfile
            import io as _io
            NGROK_DIR.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(NGROK_URL, timeout=60) as resp:
                data = resp.read()
            with zipfile.ZipFile(_io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith("ngrok.exe"):
                        zf.extract(name, NGROK_DIR)
                        extracted = NGROK_DIR / name
                        if extracted != NGROK_EXE:
                            extracted.rename(NGROK_EXE)
                        break
            if NGROK_EXE.exists():
                emit("ngrok indirildi ve hazır.")
                return True, str(NGROK_EXE)
            return False, "ZIP içinde ngrok.exe bulunamadı"
        except Exception as e:
            return False, f"ngrok indirilemedi: {e}"

    def start_ngrok(self, token: Optional[str] = None, progress_cb=None) -> Tuple[bool, str]:
        self.stop_tunnel()
        ok, ngrok_cmd = self.ensure_ngrok(progress_cb)
        if not ok:
            return False, ngrok_cmd
        if token:
            run_ps(f'"{ngrok_cmd}" config add-authtoken {token} 2>&1')
        self.db.set_setting("tunnel_type", "ngrok")
        active_port = int(self.db.get_setting("active_project_port", "8080"))
        try:
            self._tunnel_proc = subprocess.Popen(
                [ngrok_cmd, "http", str(active_port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(3)
            url = self.get_tunnel_url()
            if url:
                self._tunnel_url = url
                return True, url
            # Birkaç saniye daha dene
            for _ in range(5):
                time.sleep(2)
                url = self.get_tunnel_url()
                if url:
                    self._tunnel_url = url
                    return True, url
            return False, "ngrok başlatıldı ancak URL alınamadı — birkaç saniye bekleyip tekrar deneyin"
        except Exception as e:
            return False, str(e)

    # ── Domain Profil Senkronizasyonu ────────────────────────────────────────

    def sync_domain_profile(self) -> Tuple[bool, str]:
        """
        SQLite'taki traffic_profile ve domain_events verilerini iki yere yazar:
        1. Kubernetes ConfigMap 'domain-profile' (pod ortamı için)
        2. ~/.autoscaleops/domain_profile.json (local predictor.py için)
        Predictor otomatik olarak yeni profili okur (TTL: 60s).
        """
        import json as _json

        profile_data = self.db.build_profile_json()
        profile_json = _json.dumps(profile_data, ensure_ascii=False, indent=2)

        # ── 1. Local dosyaya yaz (predictor.py local çalışırken okur)
        local_path = APP_DIR / "domain_profile.json"
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            local_path.write_text(profile_json, encoding="utf-8")
        except Exception as e:
            return False, f"Local profil yazma hatasi: {e}"

        # ── 2. Kubernetes ConfigMap (K8s pod ortamı için)
        try:
            instance = self.db.get_instance()
            if not instance:
                # Cluster yok ama local yazma başarılı
                return True, "Profil yerel olarak kaydedildi (cluster yok)"
            ns = instance.get("namespace", "")
            if not ns:
                return True, "Profil yerel olarak kaydedildi (namespace yok)"

            cmd = (
                f"kubectl create configmap domain-profile "
                f"--from-literal=profile.json='{profile_json}' "
                f"-n {ns} --dry-run=client -o yaml | "
                f"kubectl apply -f - -n {ns}"
            )
            ok, out = run_ps(cmd, timeout=30)
            if ok:
                return True, "Domain profil senkronize edildi (local + K8s)"
            # K8s başarısız olsa bile local kaydedildi
            return True, f"Profil yerel kaydedildi (K8s: {out or 'hata'})"
        except Exception as e:
            return True, f"Profil yerel kaydedildi (K8s hatasi: {e})"

    def start_cloudflare_tunnel(self, domain: str = "") -> Tuple[bool, str]:
        self.stop_tunnel()
        self.db.set_setting("tunnel_type", "cloudflare")
        if domain:
            self.db.set_setting("cf_domain", domain)
        active_port = int(self.db.get_setting("active_project_port", "8080"))
        try:
            # stdout'u pipe et — URL'yi regex ile parse edeceğiz
            self._tunnel_proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{active_port}", "--no-autoupdate"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )
            import re as _re
            start_time = time.time()
            url = None
            while time.time() - start_time < 15:
                line = self._tunnel_proc.stdout.readline()
                if not line:
                    break
                m = _re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
                if m:
                    url = m.group(0)
                    break
            if url:
                self._tunnel_url = f"https://{domain}" if domain else url
                return True, self._tunnel_url
            return False, "cloudflared başlatıldı ancak URL algılanamadı — birkaç saniye bekleyip tekrar deneyin"
        except FileNotFoundError:
            return False, "cloudflared bulunamadı — lütfen önce kurun: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup"
        except Exception as e:
            return False, str(e)

    def stop_tunnel(self):
        if self._tunnel_proc:
            try:
                self._tunnel_proc.terminate()
            except Exception:
                pass
            self._tunnel_proc = None
        self._tunnel_url = None
        run_ps("Get-Process -Name ngrok -ErrorAction SilentlyContinue | Stop-Process -Force 2>&1")
        run_ps("Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force 2>&1")

    def get_tunnel_url(self) -> Optional[str]:
        try:
            r = requests.get("http://localhost:4040/api/tunnels", timeout=3)
            data = r.json()
            tunnels = data.get("tunnels", [])
            for t in tunnels:
                if "public_url" in t:
                    return t["public_url"]
        except Exception:
            pass
        return self._tunnel_url

    # -- Custom App Deploy ------------------------
    def deploy_app(self, folder: str, name: str, port: int, cb=None) -> Tuple[bool, str]:
        """Kullanıcının seçtiği klasörden Docker image build edip Kubernetes'e deploy eder.

        Aşamalar (tamamen self-contained — HomePanel'e gerek yok):
          1. Dockerfile + .dockerignore hazırlama
          2. Docker Desktop + Minikube cluster otomatik başlatma
          3. Docker image build (minikube docker-env üzerinde)
          4. Kubernetes Deployment + Service YAML oluşturma & uygulama
          5. Pod readiness bekleme (kubectl rollout status, timeout=180s)
          6. KEDA ScaledObject uygulama (Prometheus RPS tetikleyicisi)
          7. Port-forward başlatma
        """
        def emit(msg, lvl="info"):
            if cb:
                cb(msg, lvl)

        instance   = self.ensure_instance()
        namespace  = instance["namespace"]
        profile    = instance["minikube_profile"]
        safe_name  = _sanitize_docker_name(name)   # Docker-uyumlu tag
        if safe_name != name:
            emit(f"       ℹ️  Proje adı Docker formatına dönüştürüldü: '{name}' → '{safe_name}'", "info")
            name = safe_name

        # ── Adım 1: Dockerfile + .dockerignore ───────────────────────────
        emit("[1/7]  Dockerfile hazırlanıyor…", "info")
        dockerfile_content = _auto_dockerfile(folder)
        if dockerfile_content is not None:
            try:
                (Path(folder) / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")
                emit("       ✅  Dockerfile otomatik oluşturuldu.", "ok")
            except Exception as exc:
                emit(f"       ⚠️  Dockerfile oluşturulamadı: {exc}", "warn")
        else:
            emit("       ✅  Dockerfile mevcut.", "ok")

        di_path = Path(folder) / ".dockerignore"
        if not di_path.exists():
            try:
                di_path.write_text(
                    "node_modules\n__pycache__\n*.pyc\n.git\n.env\n*.log\n.DS_Store\n",
                    encoding="utf-8"
                )
                emit("       ℹ️  .dockerignore oluşturuldu.", "info")
            except Exception:
                pass

        # ── Adım 2: Docker Desktop + Minikube Cluster ─────────────────────
        emit("[2/7]  Altyapı hazırlanıyor…", "info")

        # Docker Desktop çalışıyor mu?
        if not self.check_docker_running().get("ok", False):
            emit("       ⚠️  Docker Desktop çalışmıyor — başlatılıyor…", "warn")
            emit("       Lütfen sistem tepsisinde Docker balina ikonunun görünmesini bekleyin.", "info")
            # Otomatik başlatma girişimi
            docker_paths = [
                r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
                str(Path.home() / "AppData" / "Local" / "Docker" / "Docker Desktop.exe"),
            ]
            for dp in docker_paths:
                if Path(dp).exists():
                    try:
                        subprocess.Popen([dp])
                        break
                    except Exception:
                        pass
            # Docker hazır olana kadar bekle (maks 60 s)
            for _ in range(12):
                time.sleep(5)
                if self.check_docker_running().get("ok", False):
                    emit("       ✅  Docker Desktop hazır.", "ok")
                    break
            else:
                return False, (
                    "Docker Desktop başlatılamadı. Lütfen Docker Desktop'u manuel olarak açın, "
                    "sistem tepsisinde balina ikonu görününce tekrar deneyin."
                )

        # Minikube cluster çalışıyor mu?
        _, status_out = run_ps(f"minikube status -p {profile} 2>&1", timeout=20)
        if "Running" not in status_out:
            emit("       Cluster başlatılıyor (1-3 dakika sürebilir)…", "info")
            _, profile_list = run_ps("minikube profile list 2>&1", timeout=15)
            profile_exists  = profile in (profile_list or "")
            start_cmd = (
                f"minikube start -p {profile} --driver=docker 2>&1"
                if profile_exists else
                f"minikube start -p {profile} --driver=docker --cpus=4 --memory=6144 2>&1"
            )
            ok_s, start_out = run_ps(start_cmd, timeout=300)
            if not ok_s and "cannot change" not in start_out.lower():
                _, st2 = run_ps(f"minikube status -p {profile} 2>&1", timeout=15)
                if "Running" not in st2:
                    return False, f"Cluster başlatılamadı:\n{start_out[:500]}"
            emit("       ✅  Cluster hazır.", "ok")
        else:
            emit("       ✅  Docker ve Cluster çalışıyor.", "ok")

        # kubeconfig'i şu an gerçekte çalışan porta güncelle
        run_ps(f"minikube update-context -p {profile} 2>&1", timeout=15)
        run_ps(f"kubectl config use-context {profile} 2>&1", timeout=10)

        # Önceki AutoScaleOps deployment'larını sıfırla (yeni proje aktif olacak)
        _, old_deps = run_ps(
            f"kubectl get deployment -n {namespace} -l managed-by=autoscaleops "
            f"-o jsonpath='{{.items[*].metadata.name}}' 2>&1",
            timeout=15
        )
        for dep in (old_deps or "").split():
            dep_base = dep.replace("-deployment", "")
            if dep_base != name:
                run_ps(
                    f"kubectl scale deployment {dep} --replicas=0 -n {namespace} 2>&1",
                    timeout=15
                )
                emit(f"       ℹ️  Eski deployment durduruldu: {dep}", "info")

        # ── Adım 3: Docker image build ────────────────────────────────────
        emit(f"[3/7]  Docker image build ediliyor: {name}:latest …", "info")
        emit("       Bu işlem birkaç dakika sürebilir.", "info")
        ok, out = run_ps(
            f'$ErrorActionPreference="Continue"; '
            f'& minikube -p {profile} docker-env --shell powershell | Invoke-Expression; '
            f'docker build -t {name}:latest "{folder}" 2>&1; '
            f'exit $LASTEXITCODE',
            timeout=480
        )
        if not ok:
            if f"naming to docker.io/library/{name}:latest done" in out:
                ok = True
            else:
                return False, f"Docker build hatası:\n{out[-1500:] if len(out) > 1500 else out}"
        emit("       ✅  Image başarıyla build edildi.", "ok")

        # ── Adım 4: Kubernetes Deployment + Service ───────────────────────
        emit("[4/7]  Kubernetes manifests uygulanıyor…", "info")
        # Namespace'i garantile — zaten varsa hata vermez
        run_ps(
            f"kubectl create namespace {namespace} --dry-run=client -o yaml "
            f"| kubectl apply -f - 2>&1",
            timeout=15
        )
        # Dockerfile'dan gerçek EXPOSE portunu oku (nginx=80, python/node=port)
        container_port = _detect_container_port(folder, port)
        if container_port != port:
            emit(f"       ℹ️  Container portu {container_port} (servis: {port})", "info")
        deploy_yaml = f"""\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}-deployment
  namespace: {namespace}
  labels:
    app: {name}
    managed-by: autoscaleops
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: {name}:latest
        imagePullPolicy: Never
        ports:
        - containerPort: {container_port}
          protocol: TCP
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        startupProbe:
          tcpSocket:
            port: {container_port}
          initialDelaySeconds: 10
          periodSeconds: 10
          failureThreshold: 60
        readinessProbe:
          tcpSocket:
            port: {container_port}
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 6
        livenessProbe:
          tcpSocket:
            port: {container_port}
          initialDelaySeconds: 30
          periodSeconds: 30
          failureThreshold: 3
---
apiVersion: v1
kind: Service
metadata:
  name: {name}-service
  namespace: {namespace}
  labels:
    app: {name}
    managed-by: autoscaleops
spec:
  selector:
    app: {name}
  ports:
  - name: http
    protocol: TCP
    port: {port}
    targetPort: {container_port}
  type: ClusterIP
"""
        yaml_path = APP_DIR / f"{name}-deploy.yaml"
        yaml_path.write_text(deploy_yaml, encoding="utf-8")

        ok, out = run_ps(
            f'$ErrorActionPreference="Continue"; '
            f"kubectl apply -f '{yaml_path}' --validate=false 2>&1; "
            f"exit $LASTEXITCODE",
            timeout=60
        )
        if not ok:
            # NativeCommandError workaround: çıktıda "created"/"configured"/"unchanged" varsa başarılı
            if any(kw in out for kw in ("created", "configured", "unchanged")):
                ok = True
            else:
                return False, f"kubectl apply hatası: {out}"
        emit("       ✅  Deployment ve Service oluşturuldu.", "ok")

        # ── Adım 4.5: Image güncelleme zorla ─────────────────────────────
        # kubectl apply sadece spec değişince pod restart eder.
        # Aynı tag (latest) ile build edilmiş yeni image için set image gerekli.
        run_ps(
            f"kubectl set image deployment/{name}-deployment "
            f"{name}={name}:latest -n {namespace} 2>&1",
            timeout=30
        )

        # ── Adım 5: Pod Readiness ─────────────────────────────────────────
        emit("[5/7]  Pod'lar hazır olana kadar bekleniyor (maks. 3 dk)…", "info")
        ok, out = run_ps(
            f'$ErrorActionPreference="Continue"; '
            f"kubectl rollout status deployment/{name}-deployment "
            f"-n {namespace} --timeout=180s 2>&1; "
            f"exit $LASTEXITCODE",
            timeout=200
        )
        rollout_ok = ok or "successfully rolled out" in out
        if rollout_ok:
            emit("       ✅  Tüm pod'lar hazır.", "ok")
        else:
            emit(f"       ⚠️  Rollout uyarısı: {out[:300]}", "warn")
            emit("       Devam ediliyor — pod'lar geç hazır olabilir.", "info")

        # ── Adım 5.5: /metrics endpoint kontrol ──────────────────────────
        # Port-forward henüz aktif olmayabilir; geçici bir pf başlatarak kontrol et
        metrics_ok = False
        try:
            pf_check = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 f"kubectl port-forward svc/{name}-service 18765:{port} -n {namespace} 2>&1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(3)
            try:
                import urllib.request as _ur
                _ur.urlopen("http://127.0.0.1:18765/metrics", timeout=3)
                metrics_ok = True
            except Exception:
                metrics_ok = False
            finally:
                pf_check.terminate()
        except Exception:
            pass
        if metrics_ok:
            emit("       ✅  /metrics endpoint aktif — Prometheus metrikleri toplanacak.", "ok")
        else:
            emit("       ⚠️  /metrics endpoint bulunamadı.", "warn")
            emit("          Dashboard'da trafik görmek için uygulamanızın /metrics", "warn")
            emit("          endpoint'i açması gerekir (prometheus-flask-exporter vb.).", "warn")
            emit("          AutoScaleOps'un oluşturduğu Dockerfile'larda bu otomatik yapılır.", "info")

        # ── Adım 6: KEDA ScaledObject ─────────────────────────────────────
        emit("[6/7]  KEDA hibrit ölçekleme kuralı uygulanıyor…", "info")
        name_safe = name.replace('-', '_')
        # KEDA eşiği: DB'den al (kullanıcı SettingsPanel'den ayarlayabilir)
        keda_threshold = self.db.get_setting("keda_rps_threshold", "50")
        keda_min_pods  = self.db.get_setting("keda_min_pods", "1")
        keda_max_pods  = self.db.get_setting("keda_max_pods", "10")

        keda_yaml = f"""\
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: {name}-scaledobject
  namespace: {namespace}
spec:
  scaleTargetRef:
    name: {name}-deployment
  minReplicaCount: {keda_min_pods}
  maxReplicaCount: {keda_max_pods}
  cooldownPeriod: 60
  pollingInterval: 15
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090
      metricName: predicted_rps_30min
      query: predicted_rps_30min
      threshold: "{keda_threshold}"
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090
      metricName: http_requests_total_{name_safe}
      threshold: "{keda_threshold}"
      query: >-
        sum(rate(http_requests_total{{kubernetes_pod_name=~"{name}-.*"}}[2m]))
"""
        keda_path = APP_DIR / f"{name}-keda.yaml"
        keda_path.write_text(keda_yaml, encoding="utf-8")
        ok_k, out_k = run_ps(f"kubectl apply -f '{keda_path}' 2>&1", timeout=30)
        if ok_k:
            emit("       ✅  KEDA hibrit ScaledObject aktif (proaktif + reaktif).", "ok")
        else:
            emit("       ⚠️  KEDA kurulamadı (KEDA yüklü değil olabilir) — devam ediliyor.", "warn")

        # ── Adım 6.5: Prometheus ServiceMonitor oluştur ──────────────────────
        # kube-prometheus-stack annotation tabanlı discovery KULLANMAZ.
        # ServiceMonitor CRD (release: prometheus label) gereklidir.
        emit("       Prometheus ServiceMonitor olusturuluyor…", "info")
        ok_sm, sm_out = self.apply_scrape_config(namespace, app_name=name)
        if ok_sm:
            emit("       OK  ServiceMonitor aktif — Prometheus metrikleri toplayacak.", "ok")
        else:
            emit(f"       WARN  ServiceMonitor: {sm_out[:150]}", "warn")

        # ── Adım 7: Port-forward ──────────────────────────────────────────
        emit(f"[7/7]  Port forward başlatılıyor → localhost:{port} …", "info")
        # KRITIK: hem settings hem projects tablosunu güncelle (is_active=1)
        # Sadece set_setting() çağrılırsa projects tablosu eski projeyi
        # active=1 göstermeye devam eder → proje yönetimi UI'sında yanlış proje
        self.db.set_active_project(name)   # projects.is_active + settings günceller
        _write_active_project_json(name, port, f"{name}-service")
        self.stop_port_forwards()
        time.sleep(2)   # OS'un eski kubectl bağlantılarını kapatması için bekle
        self.start_port_forwards(namespace)
        emit("       ✅  Port forward aktif.", "ok")

        emit(f"\n🎉  '{name}' başarıyla deploy edildi!", "ok")
        emit(f"     Adres: http://localhost:{port}", "ok")
        return True, f"http://localhost:{port}"

    def redeploy_app(self, image: str, port: int, replicas: int, cb=None) -> Tuple[bool, str]:
        """Mevcut uygulamayı yeni image/port/replica ayarları ile yeniden deploy eder."""
        def emit(msg, lvl="info"):
            if cb:
                cb(msg, lvl)
        instance = self.get_instance()
        if not instance:
            return False, "Instance bulunamadı"
        namespace = instance["namespace"]

        # Helm chart konumunu bul
        charts_dir = Path(__file__).parent / "charts" / "autoscaleops"
        if not charts_dir.exists():
            charts_dir = Path(__file__).parent.parent.parent / "charts" / "autoscaleops"

        if charts_dir.exists() and image:
            set_args = f"--set app.image={image} --set app.port={port} --set app.replicas={replicas}"
            emit("Helm upgrade ile yeniden deploy ediliyor...", "info")
            ok, out = run_ps(
                f"helm upgrade --install {namespace} {str(charts_dir)} "
                f"--namespace {namespace} {set_args} 2>&1",
                timeout=180
            )
        else:
            emit("kubectl ile güncelleniyor...", "info")
            cmds = []
            if image:
                cmds.append(
                    f"kubectl set image deployment/autoscaleops-app-deployment "
                    f"autoscaleops-app={image} -n {namespace} 2>&1"
                )
            cmds.append(
                f"kubectl scale deployment autoscaleops-app-deployment "
                f"--replicas={replicas} -n {namespace} 2>&1"
            )
            ok, out = run_ps("; ".join(cmds), timeout=60)

        if not ok:
            return False, out
        emit("Güncelleme tamamlandı.", "ok")
        return True, "OK"

    def redeploy_active_project(self, active_name: str, image: str,
                                 port: int, replicas: int, cb=None) -> Tuple[bool, str]:
        """DB'den gelen aktif proje adına göre doğru deployment'ı günceller."""
        def emit(msg, lvl="info"):
            if cb: cb(msg, lvl)
        instance = self.get_instance()
        if not instance:
            return False, "Instance bulunamadı"
        namespace = instance["namespace"]
        charts_dir = Path(__file__).parent / "charts" / "autoscaleops"

        if active_name == "autoscaleops-app" and charts_dir.exists() and image:
            set_args = (f"--set app.image={image} --set app.port={port} "
                        f"--set app.replicas={replicas}")
            emit("Helm upgrade ile yeniden deploy ediliyor...", "info")
            ok, out = run_ps(
                f"helm upgrade --install {namespace} {str(charts_dir)} "
                f"--namespace {namespace} {set_args} 2>&1",
                timeout=180
            )
        else:
            emit("kubectl ile güncelleniyor...", "info")
            deployment_name = f"{active_name}-deployment"
            cmds = []
            if image:
                cmds.append(
                    f"kubectl set image deployment/{deployment_name} "
                    f"{active_name}={image} -n {namespace} 2>&1"
                )
            cmds.append(
                f"kubectl scale deployment {deployment_name} "
                f"--replicas={replicas} -n {namespace} 2>&1"
            )
            ok, out = run_ps("; ".join(cmds), timeout=60)

        if not ok:
            return False, out
        emit("Güncelleme tamamlandı.", "ok")
        return True, "OK"

    def switch_active_project(self, name: str, port: int, service: str,
                               namespace: str) -> Tuple[bool, str]:
        """Aktif projeyi değiştir: eski port-forward'u kapat, yeni olanı aç.
        Tunnel aktifse yeni porta yönlendir."""
        # 1. Eski "app" port-forward proc'unu kapat
        old_proc = self._port_forward_procs.get("app")
        if old_proc:
            try:
                old_proc.terminate()
            except Exception:
                pass
            self._port_forward_procs.pop("app", None)

        # 2. Eski portun üzerindeki kubectl'i OS seviyesinde temizle (çakışma önleme)
        old_port = int(self.db.get_setting("active_project_port", "8080"))
        run_ps(
            f"Get-NetTCPConnection -LocalPort {old_port} -State Listen "
            f"-ErrorAction SilentlyContinue | "
            f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force "
            f"-ErrorAction SilentlyContinue }}"
        )
        time.sleep(2)  # OS'un portu serbest bırakması için bekle

        # 3. Yeni port-forward'u başlat (servis gerçek portunu otomatik oku)
        k8s_port = port
        _, sp_out = run_ps(
            f"kubectl get svc {service} -n {namespace} "
            f"--no-headers -o custom-columns=PORT:.spec.ports[0].port 2>&1",
            timeout=8
        )
        sp_out = sp_out.strip()
        if sp_out.isdigit():
            k8s_port = int(sp_out)
        try:
            cmd = (f"kubectl port-forward svc/{service} "
                   f"{port}:{k8s_port} -n {namespace}")
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._port_forward_procs["app"] = proc
        except Exception as e:
            return False, f"Port-forward başlatılamadı: {e}"

        # 4. Tunnel aktifse yeni porta yönlendir
        if self._tunnel_proc and self._tunnel_proc.poll() is None:
            tunnel_type = self.db.get_setting("tunnel_type", "none")
            self.stop_tunnel()
            time.sleep(1)
            if tunnel_type == "ngrok":
                token = self.db.get_setting("ngrok_token", "")
                self.start_ngrok(token if token else None)
            elif tunnel_type == "cloudflare":
                domain = self.db.get_setting("cf_domain", "")
                self.start_cloudflare_tunnel(domain)

        return True, f"Aktif proje değiştirildi: {name} (port {port})"

    # -- Prometheus scrape config (ServiceMonitor yaklaşımı) -----------------
    def apply_scrape_config(self, namespace: str, app_name: str = "") -> Tuple[bool, str]:
        """
        kube-prometheus-stack ile uyumlu ServiceMonitor'lar oluşturur.
        Annotation tabanlı discovery çalışmaz; ServiceMonitor CRD gereklidir.
        Prometheus, 'release: prometheus' label'ına sahip ServiceMonitor'ları izler.
        """
        import tempfile, os as _os

        # Uygulama adını belirle (deploy sırasında geçilir, yoksa DB'den al)
        if not app_name:
            app_name = self.db.get_setting("active_project_name", "")

        app_label = app_name if app_name else namespace

        # 1. Uygulama ServiceMonitor (yeni deploy'da /metrics scrape)
        app_sm_yaml = f"""apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {app_label}-app-metrics
  namespace: {namespace}
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: {app_label}
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
"""
        # 2. Pushgateway ServiceMonitor (predicted_rps_30min için)
        pgw_sm_yaml = """apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: pushgateway
  namespace: monitoring
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: prometheus-pushgateway
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
  namespaceSelector:
    matchNames:
      - monitoring
"""
        msgs = []
        success = True

        for yaml_content, label in [(app_sm_yaml, "App ServiceMonitor"),
                                     (pgw_sm_yaml, "Pushgateway ServiceMonitor")]:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False, encoding="utf-8"
            ) as f:
                f.write(yaml_content)
                tmp = f.name
            try:
                ok, out = run_ps(f"kubectl apply -f '{tmp}' 2>&1", timeout=30)
                msgs.append(f"{label}: {'OK' if ok else 'FAIL'} — {out.strip()}")
                if not ok:
                    success = False
            finally:
                try:
                    _os.unlink(tmp)
                except Exception:
                    pass

        return success, "\n".join(msgs)

    # -- Diagnostics ------------------------------
    def run_diagnostics(self) -> List[Dict]:
        results = []
        instance = self.get_instance()
        namespace = instance.get("namespace", "unknown") if instance else "unknown"
        profile = instance.get("minikube_profile", "unknown") if instance else "unknown"

        def chk(name, ok, msg, fix=None):
            results.append({
                "check": name,
                "status": "ok" if ok else "error",
                "message": msg,
                "fix": fix
            })

        # 1. Docker running
        d = self.check_docker_running()
        chk("Docker Desktop Running", d["ok"], "Docker is running" if d["ok"] else "Docker Desktop is not running",
            "Start Docker Desktop from the Start Menu" if not d["ok"] else None)

        # 2. Minikube status
        ok, out = run_ps(f"minikube status -p {profile} 2>&1")
        running = ok and "Running" in out
        chk("Minikube Cluster", running, f"Profile {profile}: {'Running' if running else 'Stopped'}",
            f"minikube start -p {profile} --driver=docker" if not running else None)

        # 3. kubectl context
        ok, ctx = run_ps("kubectl config current-context 2>&1")
        matches = profile in (ctx or "")
        chk("kubectl Context", matches, f"Context: {ctx.strip()}",
            f"kubectl config use-context {profile}" if not matches else None)

        # 4. Pods running
        ok, out = run_ps(f"kubectl get pods -n {namespace} --no-headers 2>&1")
        all_running = ok and out.strip() and all("Running" in l for l in out.strip().splitlines() if l)
        chk("Pods Running", all_running, f"Pods in {namespace}: {'All running' if all_running else out[:120] if out else 'None found'}",
            f"kubectl get pods -n {namespace} -o wide" if not all_running else None)

        # 5. Prometheus
        prom = self.check_prometheus()
        chk("Prometheus (localhost:9090)", prom, "Prometheus reachable" if prom else "Cannot reach Prometheus",
            "kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring" if not prom else None)

        # 6. Pushgateway
        pg = self.check_pushgateway()
        chk("Pushgateway (localhost:9091)", pg, "Pushgateway reachable" if pg else "Cannot reach Pushgateway",
            "kubectl port-forward svc/prometheus-pushgateway 9091:9091 -n monitoring" if not pg else None)

        # 7. App — servis adı aktif projeden alınır (dinamik)
        app_ok = self.check_app()
        try:
            _proj = self.db.get_active_project()
            svc_name = f"{_proj['name']}-service" if _proj and _proj.get("name") else "autoscaleops-app-service"
        except Exception:
            svc_name = "autoscaleops-app-service"
        chk("App (localhost:8080)", app_ok, "App reachable" if app_ok else "Cannot reach app",
            f"kubectl port-forward svc/{svc_name} 8080:8080 -n {namespace}" if not app_ok else None)

        # 8. Dashboard
        dash_ok = self.check_dashboard()
        chk("Dashboard (localhost:8501)", dash_ok, "Dashboard reachable" if dash_ok else "Streamlit dashboard not running",
            "streamlit run dashboard/dashboard.py --server.port 8501" if not dash_ok else None)

        # 9. Prometheus targets
        try:
            r = requests.get("http://localhost:9090/api/v1/targets", timeout=3)
            targets = r.json().get("data", {}).get("activeTargets", [])
            as_targets = [t for t in targets if "autoscaleops" in str(t.get("labels", {}))]
            chk("Prometheus Scraping App", len(as_targets) > 0,
                f"Found {len(as_targets)} autoscaleops target(s)",
                "Apply scrape config from Cluster Management panel" if not as_targets else None)
        except Exception:
            chk("Prometheus Scraping App", False, "Cannot check — Prometheus unreachable", None)

        # 10. Metrik kontrolü — http_requests_total VEYA flask_http_request_total
        try:
            _metric_ok = False
            _metric_msg = "Metric not found — is app running?"
            for _mq in ["http_requests_total", "flask_http_request_total"]:
                _r = requests.get("http://localhost:9090/api/v1/query",
                                  params={"query": _mq}, timeout=3)
                if _r.ok and _r.json().get("data", {}).get("result"):
                    _metric_ok = True
                    _metric_msg = f"Metric found: {_mq}"
                    break
            chk("http_requests_total metric", _metric_ok, _metric_msg,
                f"kubectl apply -f charts/autoscaleops/templates/ -n {namespace}" if not _metric_ok else None)
        except Exception:
            chk("http_requests_total metric", False, "Cannot check — Prometheus unreachable", None)

        # 11. KEDA ScaledObject
        keda = self.get_keda_status()
        chk("KEDA ScaledObject", keda, "ScaledObject found" if keda else "ScaledObject not found",
            f"helm upgrade --install {namespace} charts/autoscaleops --namespace {namespace}" if not keda else None)

        # 12. Port forward processes alive
        pf_status = self.get_port_forward_status()
        all_pf = all(pf_status.values()) if pf_status else False
        chk("Port Forwards Alive", all_pf,
            f"Active: {', '.join(k for k, v in pf_status.items() if v) or 'none'}",
            "Use 'Start Port Forwards' from Cluster Management" if not all_pf else None)

        # 13. Disk space
        disk = psutil.disk_usage(str(Path.home()))
        free_gb = disk.free / (1024**3)
        chk("Disk Space", free_gb >= 5,
            f"{free_gb:.1f} GB free",
            "Free up disk space — at least 5 GB recommended" if free_gb < 5 else None)
        if free_gb >= 5:
            results[-1]["status"] = "ok"
        elif free_gb >= 2:
            results[-1]["status"] = "warn"

        # 14. Memory available
        mem = psutil.virtual_memory()
        avail_gb = mem.available / (1024**3)
        chk("Memory Available", avail_gb >= 2,
            f"{avail_gb:.1f} GB available",
            "Close other applications to free memory" if avail_gb < 2 else None)
        if 1 <= avail_gb < 2:
            results[-1]["status"] = "warn"

        # 15. instance.json valid
        inst = self.get_instance()
        valid = inst is not None and all(k in inst for k in ["instance_id", "namespace", "minikube_profile"])
        chk("Instance Config", valid, f"instance.json: {'Valid' if valid else 'Missing or invalid'}",
            "Run setup wizard to create instance config" if not valid else None)

        return results

    # -- Kubectl raw commands ---------------------
    def run_kubectl(self, subcommand: str) -> Tuple[bool, str]:
        instance = self.get_instance()
        namespace = instance.get("namespace", "autoscaleops") if instance else "autoscaleops"
        cmd_map = {
            "get pods":        f"kubectl get pods -n {namespace} -o wide 2>&1",
            "get services":    f"kubectl get svc -n {namespace} 2>&1",
            "get events":      f"kubectl get events -n {namespace} --sort-by=.lastTimestamp 2>&1",
            "get scaledobject": f"kubectl get scaledobject -n {namespace} 2>&1",
            "get deployments": f"kubectl get deployments -n {namespace} 2>&1",
        }
        cmd = cmd_map.get(subcommand, f"kubectl {subcommand} -n {namespace} 2>&1")
        return run_ps(cmd)

    def scale_deployment(self, replicas: int) -> Tuple[bool, str]:
        instance = self.get_instance()
        if not instance:
            return False, "No instance found"
        namespace = instance.get("namespace", "autoscaleops")
        ok, out = run_ps(
            f"kubectl scale deployment autoscaleops-app-deployment --replicas={replicas} -n {namespace} 2>&1"
        )
        return ok, out

    def toggle_keda(self, enable: bool) -> Tuple[bool, str]:
        instance = self.get_instance()
        if not instance:
            return False, "No instance found"
        namespace = instance.get("namespace", "autoscaleops")
        if enable:
            ok, out = run_ps(f"kubectl apply -f charts/autoscaleops/templates/keda-scaledobject.yaml -n {namespace} 2>&1")
        else:
            ok, out = run_ps(f"kubectl delete scaledobject --all -n {namespace} 2>&1")
        return ok, out


    # -- Windows Startup --------------------------
    def set_windows_startup(self, enable: bool) -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            if enable:
                exe = sys.executable
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" "{Path(__file__)}"')
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def get_windows_startup(self) -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, APP_NAME)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    def cleanup(self):
        self.stop_port_forwards()
        self.stop_dashboard()
        self.stop_tunnel()


# ─────────────────────────────────────────────
#  BACKGROUND WORKERS
# ─────────────────────────────────────────────
class ClusterWorker(QObject):
    progress = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str)
    status_update = pyqtSignal(dict)

    def __init__(self, ops, action: str):
        super().__init__()
        self.ops = ops
        self.action = action

    @pyqtSlot()
    def run(self):
        def cb(msg, lvl="info"):
            self.progress.emit(msg, lvl)
        try:
            if self.action == "start":
                ok, msg = self.ops.start_cluster(cb)
            elif self.action == "stop":
                ok, msg = self.ops.stop_cluster(cb)
            elif self.action == "restart":
                ok, msg = self.ops.restart_cluster(cb)
            else:
                ok, msg = False, "Unknown action"
        except Exception as e:
            ok, msg = False, str(e)
        self.finished.emit(ok, msg)


class LaunchWorker(QThread):
    """HomePanel'deki tek-tuş başlatma akışını yönetir.

    Adımlar (Yerel mod):  Docker → Cluster → Port-forward → Dashboard
    Ek adım (Canlı mod):  → ngrok → URL
    """
    step_update = pyqtSignal(str, str)        # (step_key, status: idle/running/ok/error)
    error_signal = pyqtSignal(str, str, str)  # (step_key, title, description)
    url_ready   = pyqtSignal(str)             # ngrok public URL
    finished    = pyqtSignal(bool)            # overall success

    def __init__(self, ops, mode: str, parent=None):
        super().__init__(parent)
        self.ops  = ops
        self.mode = mode  # "local" | "live"

    def run(self):
        # 1 — Docker  (kapalıysa otomatik başlat)
        self.step_update.emit("docker", "running")
        if not self.ops.check_docker_running().get("ok", False):
            # Otomatik başlatma girişimi
            docker_paths = [
                r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
                str(Path.home() / "AppData" / "Local" / "Docker" / "Docker Desktop.exe"),
            ]
            started = False
            for dp in docker_paths:
                if Path(dp).exists():
                    try:
                        subprocess.Popen([dp])
                        started = True
                        break
                    except Exception:
                        pass

            if not started:
                self.error_signal.emit(
                    "docker",
                    "Docker Desktop Bulunamadı",
                    "Docker Desktop kurulu değil veya başlatılamadı. "
                    "Lütfen Docker Desktop'u kurun ve manuel başlatın."
                )
                self.step_update.emit("docker", "error")
                self.finished.emit(False)
                return

            # Docker hazır olana kadar bekle (maks 60 s)
            docker_ready = False
            for _ in range(12):
                time.sleep(5)
                if self.ops.check_docker_running().get("ok", False):
                    docker_ready = True
                    break

            if not docker_ready:
                self.error_signal.emit(
                    "docker",
                    "Docker Desktop Başlatılamadı",
                    "Docker Desktop açıldı ancak 60 saniye içinde hazır olmadı. "
                    "Sistem tepsisinde balina ikonunu bekleyin, sonra tekrar deneyin."
                )
                self.step_update.emit("docker", "error")
                self.finished.emit(False)
                return

        self.step_update.emit("docker", "ok")

        # 2 — Cluster
        self.step_update.emit("cluster", "running")
        ok, msg = self.ops.start_cluster()
        if not ok:
            self.error_signal.emit(
                "cluster",
                "Cluster Başlatılamadı",
                msg or "Minikube başlatılamadı. Activity Log sekmesine bakın."
            )
            self.step_update.emit("cluster", "error")
            self.finished.emit(False)
            return
        self.step_update.emit("cluster", "ok")

        # 3 — Port-forward & Dashboard
        self.step_update.emit("dashboard", "running")
        instance = self.ops.ensure_instance()
        namespace = instance.get("namespace", "autoscaleops")

        # ── 3a. DB ↔ K8s gerçeği doğrulaması (open-source için kritik) ──────
        # DB'deki active_project_service K8s'te var mı? Yoksa otomatik düzelt.
        active_svc  = self.ops.db.get_setting("active_project_service", "")
        active_port = int(self.ops.db.get_setting("active_project_port", "8080"))
        active_name = self.ops.db.get_setting("active_project_name", "")

        _, svc_list_out = run_ps(
            f"kubectl get svc -n {namespace} --no-headers "
            f"-o custom-columns=NAME:.metadata.name 2>&1",
            timeout=10
        )
        k8s_svcs = [s.strip() for s in svc_list_out.splitlines() if s.strip()]

        if active_svc and k8s_svcs and active_svc not in k8s_svcs:
            # DB'deki servis K8s'te yok — gerçek servisi bul ve DB'yi düzelt
            app_svcs = [s for s in k8s_svcs
                        if s.endswith("-service") and not s.startswith("kubernetes")]
            if app_svcs:
                fixed_svc  = app_svcs[-1]                    # en son deploy edilen
                fixed_name = fixed_svc.replace("-service", "")
                self.ops.db.set_setting("active_project_service", fixed_svc)
                self.ops.db.set_setting("active_project_name",    fixed_name)
                _write_active_project_json(fixed_name, active_port, fixed_svc)
                active_svc  = fixed_svc
                active_name = fixed_name

        # ── 3b. Port-forward başlat ──────────────────────────────────────────
        try:
            self.ops.stop_port_forwards()
            time.sleep(1)
            self.ops.start_port_forwards(namespace)
        except Exception:
            pass

        # ── 3c. Bekleme döngüsü — aktif yeniden deneme ile (maks 2 dk) ───────
        # Her 5s TCP kontrol; her 30s HTTP kontrol + port-forward yeniden başlat
        # TCP yerine HTTP kullan → kırık ama "canlı" processlerden etkilenmez
        active_port = int(self.ops.db.get_setting("active_project_port", "8080"))
        pf_ok   = False
        _MAX    = 120    # 2 dakika (eski: 10 dk)
        _STEP   = 5
        _waited = 0

        while _waited < _MAX:
            time.sleep(_STEP)
            _waited += _STEP

            # HTTP seviyesinde doğrula
            if self.ops.check_app():
                pf_ok = True
                break

            if _waited % 30 == 0:
                # 30 saniyede bir: port-forward'ı yeniden başlat (pasif bekleme yok)
                try:
                    self.ops.stop_port_forwards()
                    time.sleep(1)
                    self.ops.start_port_forwards(namespace)
                    active_port = int(self.ops.db.get_setting("active_project_port", "8080"))
                except Exception:
                    pass
                self.error_signal.emit(
                    "dashboard",
                    f"Uygulama Bağlantısı Kuruluyor… ({_waited}s / {_MAX}s)",
                    f"Servis: {active_svc}  |  Port: {active_port}\n"
                    "Port-forward yeniden deneniyor. Pod çalışıyorsa birkaç saniye içinde bağlanır."
                )

        if not pf_ok:
            # Servis K8s'te gerçekten var mı?
            _, svc_check = run_ps(
                f"kubectl get svc -n {namespace} --no-headers 2>&1", timeout=8
            )
            has_svc = active_svc and active_svc in svc_check

            if not has_svc:
                self.error_signal.emit(
                    "dashboard",
                    "Henüz Deploy Edilmiş Uygulama Yok",
                    "Dashboard açılıyor. Deploy sekmesinden projenizi deploy ettiğinizde "
                    "uygulama otomatik olarak buraya bağlanır."
                )
            else:
                self.error_signal.emit(
                    "dashboard",
                    f"Uygulama Port {active_port} Yanıt Vermiyor",
                    f"Servis '{active_svc}' K8s'te mevcut ama HTTP yanıtı alınamıyor.\n"
                    "Pod log'larını kontrol edin: kubectl logs -n autoscaleops -l app="
                    f"{active_name} --tail=20"
                )
            self.step_update.emit("dashboard", "warning")

        ok, msg = self.ops.start_dashboard()
        if not ok:
            self.error_signal.emit(
                "dashboard",
                "Dashboard Açılamadı",
                msg or "Streamlit kurulu mu? pip install streamlit"
            )
            self.step_update.emit("dashboard", "error")
            self.finished.emit(False)
            return
        self.step_update.emit("dashboard", "ok")

        # 4 — Tunnel (sadece "live" modunda)
        if self.mode == "live":
            self.step_update.emit("tunnel", "running")

            # start_port_forwards port'u değiştirmiş olabilir → güncel değeri oku
            active_port = int(self.ops.db.get_setting("active_project_port", "8080"))

            # Port kontrolü — yukarıdaki 10 dakikalık bekleme zaten geçti
            # Hâlâ kapalıysa deploy edilmemiş proje olabilir; devam et
            if not self.ops._is_port_open(active_port):
                self.error_signal.emit(
                    "tunnel",
                    f"Port {active_port} Açık Değil",
                    "Pod yoksa Deploy sekmesinden projeyi deploy edin. "
                    "Deploy sonrası tünel otomatik bağlanır."
                )
                self.step_update.emit("tunnel", "warning")

            token = self.ops.db.get_setting("ngrok_token") or None
            ok, result = self.ops.start_ngrok(
                token=token,
                progress_cb=lambda m, _: self.step_update.emit("tunnel", "running")
            )
            if ok:
                self.step_update.emit("tunnel", "ok")
                self.url_ready.emit(result)
            else:
                self.error_signal.emit(
                    "tunnel",
                    "Tünel Başlatılamadı",
                    result or "ngrok indirilemedi veya başlatılamadı. "
                    "İnternet bağlantınızı kontrol edin."
                )
                self.step_update.emit("tunnel", "error")
                self.finished.emit(False)
                return

        self.finished.emit(True)


class StopWorker(QThread):
    """Doğru sırayla kapat: Tünel → Dashboard → Port-forward → Minikube → [Docker]

    Bu sıra kritik:
      - Tünel önce → dış trafik kesilir
      - Dashboard → Streamlit serbest bırakılır
      - Port-forward → kubectl proc'ları temizlenir
      - Minikube → Docker sürücüsü hâlâ ayaktayken durdurulur
      - Docker (opsiyonel) → en son
    """
    done     = pyqtSignal()
    progress = pyqtSignal(str)   # UI'ya durum mesajı

    def __init__(self, ops, choice: str, parent=None):
        super().__init__(parent)
        self.ops    = ops
        self.choice = choice  # "services" | "full"

    def run(self):
        # 1 — Tünel
        self.progress.emit("Tünel kapatılıyor…")
        self.ops.stop_tunnel()

        # 2 — Dashboard
        self.progress.emit("Dashboard kapatılıyor…")
        self.ops.stop_dashboard()

        # 3 — Port-forward'lar
        self.progress.emit("Port-forward'lar temizleniyor…")
        self.ops.stop_port_forwards()

        # 4 — Minikube  (~30-60 s)
        self.progress.emit("Cluster durduruluyor (30-60 sn)…")
        self.ops.stop_cluster()

        # 5 — Docker (sadece "full" seçeneğinde)
        if self.choice == "full":
            self.progress.emit("Docker Desktop kapatılıyor…")
            run_ps(
                "Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue "
                "| Stop-Process -Force 2>&1; "
                "Get-Process -Name 'dockerd' -ErrorAction SilentlyContinue "
                "| Stop-Process -Force 2>&1"
            )

        self.progress.emit("Tamamlandı.")
        self.done.emit()


class HardwareMonitor(QObject):
    snapshot = pyqtSignal(dict)

    def __init__(self, db):
        super().__init__()
        self.db = db
        self._net_last = None
        self._net_time = None

    @pyqtSlot()
    def collect(self):
        try:
            cpu = psutil.cpu_percent(interval=0.3)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(str(Path.home()))
            net_now = psutil.net_io_counters()
            now = time.time()
            sent_mb = recv_mb = 0.0
            if self._net_last and self._net_time:
                dt = now - self._net_time
                if dt > 0:
                    sent_mb = (net_now.bytes_sent - self._net_last.bytes_sent) / (1024*1024) / dt
                    recv_mb = (net_now.bytes_recv - self._net_last.bytes_recv) / (1024*1024) / dt
            self._net_last = net_now
            self._net_time = now
            data = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "memory_used_mb": mem.used / (1024*1024),
                "memory_total_mb": mem.total / (1024*1024),
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used / (1024**3),
                "disk_total_gb": disk.total / (1024**3),
                "network_sent_mb": sent_mb,
                "network_recv_mb": recv_mb,
            }
            self.db.save_hardware_snapshot(data)
            self.snapshot.emit(data)
        except Exception:
            pass


class MetricsPoller(QObject):
    metrics = pyqtSignal(dict)

    def __init__(self, ops):
        super().__init__()
        self.ops = ops

    @pyqtSlot()
    def poll(self):
        try:
            rps = self.ops.get_current_rps()
            pods = self.ops.get_pod_count()
            keda = self.ops.get_keda_status()
            svcs = self.ops.check_all_services()
            predicted = self.ops.get_predicted_rps()
            self.metrics.emit({"rps": rps, "pod_count": pods, "keda_active": keda,
                               "services": svcs, "predicted_rps": predicted})
        except Exception:
            pass


class ServiceWatcher(QObject):
    service_status = pyqtSignal(str, bool)

    def __init__(self, ops):
        super().__init__()
        self.ops = ops

    @pyqtSlot()
    def check(self):
        try:
            for name, up in self.ops.check_all_services().items():
                self.service_status.emit(name, up)
        except Exception:
            pass



# ─────────────────────────────────────────────
#  REUSABLE WIDGETS
# ─────────────────────────────────────────────
class StatusDot(QLabel):
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._color = color or "#555"
        self._update()

    def set_color(self, color: str):
        self._color = color
        self._update()

    def _update(self):
        self.setStyleSheet(f"background-color: {self._color}; border-radius: 5px;")


class NotificationBanner(QWidget):
    """
    Ekranın üstünde beliren, X ile kapatılabilen bildirim banner'ı.
    Kullanım: banner.show_message("Mesaj", level="info"|"warning"|"success"|"error")
    """
    COLORS = {
        "info":    {"bg": "rgba(99,102,241,0.18)",  "border": "#6366F1", "icon": "ℹ"},
        "warning": {"bg": "rgba(251,191,36,0.15)",  "border": "#FBBF24", "icon": "⚠"},
        "success": {"bg": "rgba(52,211,153,0.15)",  "border": "#34D399", "icon": "✓"},
        "error":   {"bg": "rgba(248,113,113,0.15)", "border": "#F87171", "icon": "✕"},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setFixedHeight(46)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 12, 0)
        lay.setSpacing(10)

        self._icon_lbl = QLabel("ℹ")
        self._icon_lbl.setFixedWidth(20)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background:transparent; border:none; font-size:15px;")

        self._msg_lbl = QLabel("")
        self._msg_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:13px; background:transparent; border:none;")
        self._msg_lbl.setWordWrap(False)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C_TEXT_DIM};
                border: none;
                font-size: 13px;
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,10);
                color: {C_TEXT};
            }}
        """)
        self._close_btn.clicked.connect(self.dismiss)

        lay.addWidget(self._icon_lbl)
        lay.addWidget(self._msg_lbl, 1)
        lay.addWidget(self._close_btn)

    def show_message(self, message: str, level: str = "info", auto_dismiss_ms: int = 0):
        """Banner'ı göster. auto_dismiss_ms > 0 ise o süre sonra kapanır."""
        cfg = self.COLORS.get(level, self.COLORS["info"])
        self._icon_lbl.setText(cfg["icon"])
        self._icon_lbl.setStyleSheet(
            f"background:transparent; border:none; font-size:15px; color:{cfg['border']};"
        )
        self._msg_lbl.setText(message)
        self.setStyleSheet(f"""
            NotificationBanner {{
                background: {cfg['bg']};
                border-bottom: 1px solid {cfg['border']};
            }}
        """)
        self.setVisible(True)
        if auto_dismiss_ms > 0:
            QTimer.singleShot(auto_dismiss_ms, self.dismiss)

    def dismiss(self):
        self.setVisible(False)


def _add_shadow(widget: QWidget, blur: int = 20, offset_y: int = 4, alpha: int = 80):
    """Widget'a iOS-style yumuşak drop shadow ekle."""
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset_y)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)


class Card(QFrame):
    def __init__(self, title: str = "", parent=None, shadow: bool = True):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ "
            f"background-color: {C_SURFACE}; "
            f"border: 1px solid rgba(255,255,255,0.08); "
            f"border-radius: 16px; }}"
        )
        if shadow:
            _add_shadow(self)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(12)
        if title:
            lbl = QLabel(title.upper())
            lbl.setStyleSheet(
                f"color: {C_TEXT_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;"
            )
            self._layout.addWidget(lbl)

    def body(self) -> QVBoxLayout:
        return self._layout


class _DashMetricCard(QFrame):
    """Dashboard'da kullanılan küçük metrik kartı — value/sub alanı güncellenebilir."""
    def __init__(self, title: str, value: str = "—", accent: str = None, parent=None):
        super().__init__(parent)
        accent = accent or C_ACCENT
        self.setStyleSheet(
            f"QFrame {{ "
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {C_SURFACE2}, stop:1 {C_SURFACE}); "
            f"border: 1px solid rgba(255,255,255,0.07); "
            f"border-radius: 16px; }}"
        )
        _add_shadow(self, blur=18, offset_y=4, alpha=55)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        # Üst: renkli ince çizgi (accent rengi)
        bar = QFrame()
        bar.setFixedHeight(2)
        bar.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {accent}, stop:1 transparent); "
            f"border:none; border-radius:1px;"
        )
        lay.addWidget(bar)
        lay.addSpacing(2)

        t = QLabel(title.upper())
        t.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:9px; font-weight:700; "
            f"letter-spacing:1px; background:transparent; border:none;"
        )
        self._val_lbl = QLabel(value)
        self._val_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self._val_lbl.setStyleSheet(f"color:{accent}; background:transparent; border:none;")
        self._sub_lbl = QLabel("")
        self._sub_lbl.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:10px; background:transparent; border:none;"
        )
        lay.addWidget(t)
        lay.addWidget(self._val_lbl)
        lay.addWidget(self._sub_lbl)

    def set_value(self, value: str, sub: str = ""):
        self._val_lbl.setText(value)
        self._sub_lbl.setText(sub)


class SectionTitle(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"color: {C_TEXT}; font-size: 16px; font-weight: bold; margin-bottom: 4px;")


class LogWidget(QTextEdit):
    # Worker thread'lerden güvenli çağrı için internal sinyal
    _line_signal = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:6px;")
        self._line_signal.connect(self._do_append, Qt.ConnectionType.QueuedConnection)

    def append_line(self, text: str, level: str = "info"):
        """Thread-safe: her thread'den çağrılabilir."""
        self._line_signal.emit(text, level)

    @pyqtSlot(str, str)
    def _do_append(self, text: str, level: str):
        """Her zaman main thread'de çalışır."""
        colors = {"info": C_TEXT, "ok": C_GREEN, "warn": C_YELLOW, "error": C_RED}
        color = colors.get(level, C_TEXT)
        ts = datetime.now().strftime("%H:%M:%S")
        self.append(f"<span style='color:{C_TEXT_DIM}'>[{ts}]</span> <span style='color:{color}'>{text}</span>")
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class StepWidget(QFrame):
    """Tek bir başlatma adımını gösteren widget: ikon + isim + durum."""
    _ICONS  = {"idle": "○", "running": "◌", "ok": "●", "error": "✕", "warning": "⚠"}
    _COLORS = {"idle": C_TEXT_DIM, "running": C_YELLOW, "ok": C_GREEN, "error": C_RED, "warning": C_YELLOW}

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setFixedWidth(130)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 14, 12, 14)
        root.setSpacing(4)
        root.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._icon_lbl = QLabel("○")
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 22px;")

        self._name_lbl = QLabel(label)
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 12px; font-weight: 600;")

        self._sub_lbl = QLabel("")
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")

        root.addWidget(self._icon_lbl)
        root.addWidget(self._name_lbl)
        root.addWidget(self._sub_lbl)

    def set_status(self, status: str, sub_text: str = ""):
        icon  = self._ICONS.get(status, "○")
        color = self._COLORS.get(status, C_TEXT_DIM)
        self._icon_lbl.setText(icon)
        self._icon_lbl.setStyleSheet(f"color: {color}; font-size: 22px;")
        name_color = color if status != "idle" else C_TEXT
        self._name_lbl.setStyleSheet(f"color: {name_color}; font-size: 12px; font-weight: 600;")
        self._sub_lbl.setText(sub_text)
        self._sub_lbl.setStyleSheet(f"color: {color if status != 'idle' else C_TEXT_DIM}; font-size: 11px;")


class ErrorCard(QFrame):
    """Hata gösterici: başlık + açıklama + opsiyonel düzelt butonu."""
    fix_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: rgba(255,69,58,0.10); border: 1px solid rgba(255,69,58,0.40); border-radius: 16px; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(6)

        self._title = QLabel()
        self._title.setStyleSheet(f"color: {C_RED}; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        self._title.setWordWrap(True)

        self._desc = QLabel()
        self._desc.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 13px; background: transparent; border: none;")
        self._desc.setWordWrap(True)

        self._fix_btn = QPushButton()
        self._fix_btn.setObjectName("btn_primary")
        self._fix_btn.clicked.connect(self.fix_clicked)
        self._fix_btn.setVisible(False)
        self._fix_btn.setFixedWidth(200)

        root.addWidget(self._title)
        root.addWidget(self._desc)
        root.addWidget(self._fix_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.hide()

    def show_error(self, title: str, desc: str, fix_label: str = "", warning: bool = False):
        if warning:
            self.setStyleSheet(
                "QFrame { background: rgba(251,191,36,0.10); border: 1px solid rgba(251,191,36,0.40); border-radius: 16px; }"
            )
            self._title.setStyleSheet(f"color:{C_YELLOW}; font-size:14px; font-weight:700; background:transparent; border:none;")
            self._title.setText(f"⚠️  {title}")
        else:
            self.setStyleSheet(
                "QFrame { background: rgba(255,69,58,0.10); border: 1px solid rgba(255,69,58,0.40); border-radius: 16px; }"
            )
            self._title.setStyleSheet(f"color:{C_RED}; font-size:14px; font-weight:700; background:transparent; border:none;")
            self._title.setText(f"❌  {title}")
        self._desc.setText(desc)
        if fix_label:
            self._fix_btn.setText(fix_label)
            self._fix_btn.setVisible(True)
        else:
            self._fix_btn.setVisible(False)
        self.show()

    def hide_error(self):
        self.hide()


class PreflightDialog(QDialog):
    """Profesyonel deploy ön-kontrol dialogu.

    Proje analiz sonucunu görsel olarak gösterir:
      - Proje türü + tespit edilen dosyalar
      - Sorun listesi (error / warning / info)
      - "Deploy Et" veya (hata varsa) "Yine de Deploy Et" + İptal
    """

    SEVERITY_META = {
        "error":   ("❌", C_RED,     "Kritik Sorun"),
        "warning": ("⚠️",  C_YELLOW, "Uyarı"),
        "info":    ("ℹ️",  C_TEXT_DIM, "Bilgi"),
    }
    TYPE_META = {
        "python": ("🐍", "Python"),
        "node":   ("📦", "Node.js"),
        "static": ("🌐", "Statik HTML"),
        "docker": ("🐳", "Özel Docker"),
        "unknown":("❓", "Tanımlanamadı"),
    }

    #: True  → kullanıcı "Deploy Et" / "Yine de Deploy Et" seçti
    confirmed: bool = False

    def __init__(self, analysis: Dict[str, Any], project_name: str, parent=None):
        super().__init__(parent)
        self.analysis = analysis
        self.setWindowTitle("Deploy Ön Kontrolü")
        self.setMinimumWidth(560)
        self.setMaximumWidth(680)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui(project_name)

    def _build_ui(self, project_name: str):
        a = self.analysis
        has_errors   = any(i["severity"] == "error"   for i in a["issues"])
        has_warnings = any(i["severity"] == "warning" for i in a["issues"])
        type_icon, type_label = self.TYPE_META.get(a["type"], ("❓", "Bilinmiyor"))

        # ── Outer card ────────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.10); "
            f"border-radius:20px; }}"
        )
        _add_shadow(card, blur=40, offset_y=10, alpha=120)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(28, 24, 28, 24)
        card_lay.setSpacing(0)
        outer.addWidget(card)

        # ── Başlık ────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(10)
        type_lbl = QLabel(type_icon)
        type_lbl.setFont(QFont("Segoe UI", 28))
        type_lbl.setStyleSheet("background:transparent; border:none;")

        hdr_text = QVBoxLayout()
        hdr_text.setSpacing(2)
        proj_lbl = QLabel(project_name)
        proj_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        proj_lbl.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        sub_lbl  = QLabel(f"{type_label} projesi tespit edildi")
        sub_lbl.setFont(QFont("Segoe UI", 11))
        sub_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        hdr_text.addWidget(proj_lbl)
        hdr_text.addWidget(sub_lbl)

        hdr_row.addWidget(type_lbl)
        hdr_row.addLayout(hdr_text, 1)

        # Durum rozetleri
        if has_errors:
            badge_color, badge_text = C_RED,    "Kritik Sorun"
        elif has_warnings:
            badge_color, badge_text = C_YELLOW, "Uyarı Var"
        else:
            badge_color, badge_text = C_GREEN,  "Hazır"
        badge = QLabel(f"  {badge_text}  ")
        badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        badge.setStyleSheet(
            f"color:#000; background:{badge_color}; border-radius:8px; "
            f"padding:2px 6px;"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        card_lay.addLayout(hdr_row)
        card_lay.addSpacing(16)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:rgba(255,255,255,0.07); border:none;")
        card_lay.addWidget(sep)
        card_lay.addSpacing(14)

        # ── Tespit edilen dosyalar ─────────────────────────────────────────
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMaximumHeight(320)
        scroll_area.setStyleSheet("background:transparent;")
        inner_w = QWidget()
        inner_lay = QVBoxLayout(inner_w)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(10)

        # Dosya listesi
        if a["file_tree"]:
            ftree_label = QLabel("📁  Tespit Edilen Dosyalar")
            ftree_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            ftree_label.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
            inner_lay.addWidget(ftree_label)

            files_frame = QFrame()
            files_frame.setStyleSheet(
                f"QFrame {{ background:{C_BG}; border:1px solid rgba(255,255,255,0.06); "
                f"border-radius:10px; }}"
            )
            ff_lay = QVBoxLayout(files_frame)
            ff_lay.setContentsMargins(12, 10, 12, 10)
            ff_lay.setSpacing(4)
            for fname in a["file_tree"]:
                row = QHBoxLayout()
                row.setSpacing(8)
                dot = QLabel("●")
                dot.setFixedWidth(12)
                dot.setStyleSheet(f"color:{C_ACCENT}; font-size:8px; background:transparent; border:none;")
                fl = QLabel(fname)
                fl.setFont(QFont("Courier New", 11))
                fl.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
                row.addWidget(dot)
                row.addWidget(fl, 1)
                ff_lay.addLayout(row)

            # dockerfile durumu
            if a["dockerfile_exists"]:
                self._add_file_row(ff_lay, "Dockerfile", C_GREEN, "(mevcut — kullanılacak)")
            elif a["dockerfile_auto"]:
                self._add_file_row(ff_lay, "Dockerfile", C_YELLOW, "(otomatik oluşturulacak)")
            else:
                self._add_file_row(ff_lay, "Dockerfile", C_RED, "(YOK — oluşturulamıyor)")

            inner_lay.addWidget(files_frame)
            inner_lay.addSpacing(10)

        # Sorunlar listesi
        if a["issues"]:
            issues_label = QLabel("🔍  Kontrol Sonuçları")
            issues_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            issues_label.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
            inner_lay.addWidget(issues_label)

            for iss in a["issues"]:
                sev = iss["severity"]
                icon, color, _ = self.SEVERITY_META.get(sev, ("ℹ️", C_TEXT_DIM, ""))
                iss_frame = QFrame()
                iss_frame.setStyleSheet(
                    f"QFrame {{ background:{C_BG}; border-left:3px solid {color}; "
                    f"border-radius:0px 8px 8px 0px; }}"
                )
                iss_lay = QHBoxLayout(iss_frame)
                iss_lay.setContentsMargins(10, 8, 10, 8)
                iss_lay.setSpacing(10)

                icon_l = QLabel(icon)
                icon_l.setFont(QFont("Segoe UI", 14))
                icon_l.setStyleSheet("background:transparent; border:none;")
                icon_l.setFixedWidth(22)

                text_col = QVBoxLayout()
                text_col.setSpacing(2)
                title_l = QLabel(iss["title"])
                title_l.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                title_l.setStyleSheet(f"color:{color}; background:transparent; border:none;")
                detail_l = QLabel(iss["detail"])
                detail_l.setFont(QFont("Segoe UI", 10))
                detail_l.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
                detail_l.setWordWrap(True)
                text_col.addWidget(title_l)
                text_col.addWidget(detail_l)

                iss_lay.addWidget(icon_l)
                iss_lay.addLayout(text_col, 1)
                inner_lay.addWidget(iss_frame)
        else:
            ok_frame = QFrame()
            ok_frame.setStyleSheet(
                f"QFrame {{ background:{C_BG}; border-left:3px solid {C_GREEN}; "
                f"border-radius:0px 8px 8px 0px; }}"
            )
            ok_l = QHBoxLayout(ok_frame)
            ok_l.setContentsMargins(10, 10, 10, 10)
            ok_icon = QLabel("✅")
            ok_icon.setFont(QFont("Segoe UI", 14))
            ok_icon.setStyleSheet("background:transparent; border:none;")
            ok_text = QLabel("Tüm kontroller geçildi — deploy'a hazır!")
            ok_text.setFont(QFont("Segoe UI", 11))
            ok_text.setStyleSheet(f"color:{C_GREEN}; background:transparent; border:none;")
            ok_l.addWidget(ok_icon)
            ok_l.addWidget(ok_text, 1)
            inner_lay.addWidget(ok_frame)

        inner_lay.addStretch()
        scroll_area.setWidget(inner_w)
        card_lay.addWidget(scroll_area)
        card_lay.addSpacing(18)

        # ── Butonlar ──────────────────────────────────────────────────────
        sep2 = QFrame(); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:rgba(255,255,255,0.07); border:none;")
        card_lay.addWidget(sep2)
        card_lay.addSpacing(14)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("İptal")
        cancel_btn.setFixedHeight(44)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)

        if has_errors and not a["dockerfile_auto"] and a["type"] == "unknown":
            # Hiç deploy edemeyiz
            deploy_btn = QPushButton("Deploy Edilemiyor")
            deploy_btn.setObjectName("btn_primary")
            deploy_btn.setFixedHeight(44)
            deploy_btn.setEnabled(False)
        elif has_errors:
            deploy_btn = QPushButton("⚠️   Yine de Deploy Et")
            deploy_btn.setObjectName("btn_danger")
            deploy_btn.setFixedHeight(44)
            deploy_btn.setToolTip("Kritik sorunlar var ama yine de deploy deneyebilirsiniz.")
            deploy_btn.clicked.connect(self._confirm)
        else:
            label = "▶   Deploy Et" if not has_warnings else "▶   Deploy Et  (uyarılarla)"
            deploy_btn = QPushButton(label)
            deploy_btn.setObjectName("btn_primary")
            deploy_btn.setFixedHeight(44)
            deploy_btn.clicked.connect(self._confirm)

        deploy_btn.setMinimumWidth(200)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(deploy_btn)
        card_lay.addLayout(btn_row)

    def _add_file_row(self, layout, name: str, color: str, note: str):
        row = QHBoxLayout()
        dot = QLabel("●")
        dot.setFixedWidth(12)
        dot.setStyleSheet(f"color:{color}; font-size:8px; background:transparent; border:none;")
        fl  = QLabel(name)
        fl.setFont(QFont("Courier New", 11))
        fl.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        nl  = QLabel(note)
        nl.setFont(QFont("Segoe UI", 10))
        nl.setStyleSheet(f"color:{color}; background:transparent; border:none;")
        row.addWidget(dot)
        row.addWidget(fl)
        row.addWidget(nl, 1)
        layout.addLayout(row)

    def _confirm(self):
        self.confirmed = True
        self.accept()


class ShutdownDialog(QDialog):
    """iOS-style kapatma seçenekleri dialogu.

    Üç seçenek:
      - Servisleri Durdur  (cluster + tunnel + dashboard; Docker kalır)
      - Sistemi Kapat      (+ Docker Desktop)
      - İptal
    """
    # Seçilen aksiyon: "services" | "full" | None (iptal)
    choice: Optional[str] = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sistemi Kapat")
        self.setModal(True)
        self.setFixedWidth(420)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Ana kart çerçevesi
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("shutdown_card")
        card.setStyleSheet(
            f"QFrame#shutdown_card {{"
            f"  background: {C_SURFACE};"
            f"  border: 1px solid rgba(255,255,255,0.10);"
            f"  border-radius: 20px;"
            f"}}"
        )
        _add_shadow(card, blur=40, offset_y=12, alpha=120)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(14)

        # Başlık
        icon_lbl = QLabel("⏹")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI", 28))
        icon_lbl.setStyleSheet("color: #FFFFFF; background: transparent;")

        title = QLabel("Sistemi Kapat")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C_TEXT}; background: transparent;")

        subtitle = QLabel("Ne yapmak istersiniz?")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet(f"color:{C_TEXT_DIM}; background: transparent;")

        lay.addWidget(icon_lbl)
        lay.addWidget(title)
        lay.addWidget(subtitle)
        lay.addSpacing(6)

        # Seçenek 1: Servisleri Durdur
        svc_frame = self._option_frame(
            "⏹  Servisleri Durdur",
            "Cluster, dashboard ve tunnel durdurulur.\nDocker Desktop çalışmaya devam eder.",
            C_ACCENT
        )
        svc_frame.mousePressEvent = lambda _: self._choose("services")
        lay.addWidget(svc_frame)

        # Seçenek 2: Sistemi Tamamen Kapat
        full_frame = self._option_frame(
            "🔴  Sistemi Tamamen Kapat",
            "Tüm servisler durdurulur.\nDocker Desktop da kapatılır.",
            C_RED
        )
        full_frame.mousePressEvent = lambda _: self._choose("full")
        lay.addWidget(full_frame)

        # İptal
        lay.addSpacing(4)
        cancel_btn = QPushButton("İptal")
        cancel_btn.setObjectName("btn_primary")
        cancel_btn.setFixedHeight(44)
        cancel_btn.clicked.connect(self.reject)
        lay.addWidget(cancel_btn)

        outer.addWidget(card)

    def _option_frame(self, title: str, desc: str, accent: str) -> QFrame:
        f = QFrame()
        f.setCursor(Qt.CursorShape.PointingHandCursor)
        f.setStyleSheet(
            f"QFrame {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; }}"
            f"QFrame:hover {{ background: rgba(255,255,255,0.08); border-color: {accent}; }}"
        )
        fl = QHBoxLayout(f)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        t_lbl.setStyleSheet(f"color:{C_TEXT}; background: transparent; border: none;")
        d_lbl = QLabel(desc)
        d_lbl.setFont(QFont("Segoe UI", 11))
        d_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background: transparent; border: none;")
        d_lbl.setWordWrap(True)
        text_col.addWidget(t_lbl)
        text_col.addWidget(d_lbl)

        arr = QLabel("›")
        arr.setFont(QFont("Segoe UI", 20))
        arr.setStyleSheet(f"color:{C_TEXT_DIM}; background: transparent; border: none;")

        fl.addLayout(text_col, 1)
        fl.addWidget(arr)
        return f

    def _choose(self, action: str):
        self.choice = action
        self.accept()


# ─────────────────────────────────────────────
#  SCREEN 0 — SPLASH SCREEN
# ─────────────────────────────────────────────
class SplashScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(24)
        title = QLabel("AutoScaleOps")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{C_TEXT}; font-size:36px; font-weight:bold; letter-spacing:2px;")
        sub = QLabel("AI-Powered Kubernetes Autoscaling")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:14px;")
        self._status = QLabel("Initializing...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"color:{C_ACCENT}; font-size:13px;")
        pb = QProgressBar()
        pb.setRange(0, 0)
        pb.setFixedWidth(300)
        pb.setFixedHeight(4)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(16)
        lay.addWidget(self._status)
        lay.addWidget(pb, 0, Qt.AlignmentFlag.AlignCenter)

    def set_status(self, msg: str):
        self._status.setText(msg)




# ─────────────────────────────────────────────
#  KURULUM YARDIMCILARI
# ─────────────────────────────────────────────
class _InstallWorker(QThread):
    progress  = pyqtSignal(str, str)
    tool_done = pyqtSignal(str, bool)
    all_done  = pyqtSignal(bool)

    TOOLS = [
        ("Python Paketleri", None, ["PyQt6","matplotlib","psutil","requests",
                                    "cryptography","pyyaml","click","rich","jinja2",
                                    "pmdarima","statsmodels","pandas","numpy"]),
        ("Docker Desktop", "Docker.DockerDesktop",  []),
        ("Minikube",       "Kubernetes.minikube",   []),
        ("kubectl",        "Kubernetes.kubectl",    []),
        ("Helm",           "Helm.Helm",             []),
    ]

    def __init__(self, missing: list, parent=None):
        super().__init__(parent)
        self._missing = set(missing)

    def run(self):
        overall_ok = True
        no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for name, winget_id, pip_pkgs in self.TOOLS:
            if name not in self._missing:
                continue
            self.progress.emit(f"Kuruluyor: {name}...", "info")
            ok = False
            try:
                if pip_pkgs:
                    cmd = [sys.executable, "-m", "pip", "install",
                           "--upgrade", "--quiet"] + pip_pkgs
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, errors="replace"
                    )
                    for line in iter(proc.stdout.readline, ""):
                        line = line.strip()
                        if line and "already" not in line.lower() and "warning" not in line.lower():
                            self.progress.emit(f"   {line}", "info")
                    proc.wait()
                    ok = proc.returncode == 0
                elif winget_id:
                    cmd = ["winget", "install", "--id", winget_id, "-e",
                           "--silent", "--accept-package-agreements",
                           "--accept-source-agreements"]
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, errors="replace", creationflags=no_win
                    )
                    for line in iter(proc.stdout.readline, ""):
                        line = line.strip()
                        if line:
                            self.progress.emit(f"   {line}", "info")
                    proc.wait()
                    ok = proc.returncode in (0, -1978335189)
            except Exception as e:
                self.progress.emit(f"Hata: {e}", "error")
                ok = False
            lv = "ok" if ok else "warn"
            msg = f"OK {name} kuruldu." if ok else f"UYARI {name} kurulamadi - elle kurun."
            self.progress.emit(msg, lv)
            if not ok:
                overall_ok = False
            self.tool_done.emit(name, ok)
        self.all_done.emit(overall_ok)


class _HelmWorker(QThread):
    progress = pyqtSignal(str, str)
    finished = pyqtSignal(bool, str)

    HELM_STEPS = [
        (["helm","repo","add","prometheus-community",
          "https://prometheus-community.github.io/helm-charts"],
         "Prometheus repo ekleniyor..."),
        (["helm","repo","add","kedacore","https://kedacore.github.io/charts"],
         "KEDA repo ekleniyor..."),
        (["helm","repo","update"], "Repolar guncelleniyor..."),
        (["helm","upgrade","--install","prometheus",
          "prometheus-community/kube-prometheus-stack",
          "-n","monitoring","--create-namespace",
          "--set","grafana.enabled=false",
          "--set","alertmanager.enabled=false",
          "--wait","--timeout=5m"],
         "Prometheus kuruluyor (1-3 dk)..."),
        (["helm","upgrade","--install","pushgateway",
          "prometheus-community/prometheus-pushgateway",
          "-n","monitoring","--wait","--timeout=2m"],
         "Pushgateway kuruluyor..."),
        (["helm","upgrade","--install","keda","kedacore/keda",
          "-n","keda","--create-namespace","--wait","--timeout=3m"],
         "KEDA kuruluyor..."),
    ]

    def run(self):
        no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for cmd, label in self.HELM_STEPS:
            self.progress.emit(label, "info")
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors="replace", creationflags=no_win
                )
                for line in iter(proc.stdout.readline, ""):
                    line = line.strip()
                    if line:
                        self.progress.emit(f"   {line}", "info")
                proc.wait()
                if proc.returncode != 0:
                    self.progress.emit(f"Uyari: adim basarisiz oldu.", "warn")
            except FileNotFoundError:
                self.finished.emit(False, "helm bulunamadi.")
                return
            except Exception as e:
                self.progress.emit(f"Hata: {e}", "error")
        self.progress.emit("Tum Helm chartlar kuruldu!", "ok")
        self.finished.emit(True, "Helm kurulumlari tamamlandi.")


# ─────────────────────────────────────────────
#  SCREEN 1 — SETUP WIZARD
# ─────────────────────────────────────────────
class SetupWizard(QWidget):
    wizard_done = pyqtSignal()
    STEP_NAMES  = ["Hos Geldin","Sistem Tespiti","Kurulum","Cluster","Helm","Hazir!"]

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db  = db
        self.ops = ops
        self._missing_tools: list = []
        self._tool_rows: dict = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._step_bar = self._build_step_bar()
        root.addWidget(self._step_bar)
        self._pages = QStackedWidget()
        root.addWidget(self._pages)
        self._pages.addWidget(self._build_welcome())
        self._pages.addWidget(self._build_detect())
        self._pages.addWidget(self._build_install_page())
        self._pages.addWidget(self._build_cluster_page())
        self._pages.addWidget(self._build_helm_page())
        self._pages.addWidget(self._build_done())
        self._go_to(0)

    def _build_step_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background:{C_SURFACE}; border-bottom:1px solid {C_BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(28, 0, 28, 0)
        lay.setSpacing(0)
        self._step_nums = []
        self._step_lbls = []
        for i, name in enumerate(self.STEP_NAMES):
            col = QVBoxLayout()
            col.setSpacing(1)
            num = QLabel(str(i + 1))
            num.setFixedSize(22, 22)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(
                f"background:{C_BORDER}; color:{C_TEXT_DIM}; border-radius:11px; "
                f"font-weight:700; font-size:10px;"
            )
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:9px;")
            col.addWidget(num, 0, Qt.AlignmentFlag.AlignCenter)
            col.addWidget(lbl, 0, Qt.AlignmentFlag.AlignCenter)
            self._step_nums.append(num)
            self._step_lbls.append(lbl)
            lay.addLayout(col)
            if i < len(self.STEP_NAMES) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedHeight(1)
                sep.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                sep.setStyleSheet(f"background:{C_BORDER}; border:none; margin:0 4px;")
                lay.addWidget(sep)
        return w

    def _go_to(self, step: int):
        for i, (num, lbl) in enumerate(zip(self._step_nums, self._step_lbls)):
            if i < step:
                num.setStyleSheet(f"background:{C_GREEN}; color:#fff; border-radius:11px; font-weight:700; font-size:10px;")
                lbl.setStyleSheet(f"color:{C_GREEN}; font-size:9px;")
            elif i == step:
                num.setStyleSheet(f"background:{C_ACCENT}; color:#fff; border-radius:11px; font-weight:700; font-size:10px;")
                lbl.setStyleSheet(f"color:{C_ACCENT}; font-size:9px; font-weight:700;")
            else:
                num.setStyleSheet(f"background:{C_BORDER}; color:{C_TEXT_DIM}; border-radius:11px; font-weight:700; font-size:10px;")
                lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:9px;")
        self._pages.setCurrentIndex(step)

    def _build_welcome(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(0)
        lay.setContentsMargins(100, 50, 100, 50)

        icon_lbl = QLabel("A")
        icon_lbl.setFixedSize(68, 68)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #9BA8FA,stop:1 {C_ACCENT2});"
            f"color:#fff; font-size:30px; font-weight:700; border-radius:20px;"
        )
        lay.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(22)

        t = QLabel("AutoScaleOps'a Hos Geldiniz")
        t.setStyleSheet(f"color:{C_TEXT}; font-size:24px; font-weight:700;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("AI destekli Kubernetes otomatik olcekleme platformu")
        sub.setStyleSheet(f"color:{C_ACCENT}; font-size:13px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        lay.addSpacing(4)
        lay.addWidget(sub)
        lay.addSpacing(28)

        feat_w = QFrame()
        feat_w.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); border-radius:14px; }}"
        )
        feat_lay = QVBoxLayout(feat_w)
        feat_lay.setContentsMargins(24, 16, 24, 16)
        feat_lay.setSpacing(10)
        for arrow, text in [
            ("->", "Prometheus ile trafik izleme"),
            ("->", "ARIMA ile trafik pigi tahmini"),
            ("->", "KEDA ile otomatik pod olcekleme"),
            ("->", "Tamamen yerel, bulut maliyeti yok"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(12)
            ico = QLabel(arrow)
            ico.setFixedWidth(18)
            ico.setStyleSheet(f"color:{C_ACCENT}; font-size:11px; background:transparent; border:none;")
            txt = QLabel(text)
            txt.setStyleSheet(f"color:{C_TEXT}; font-size:13px; background:transparent; border:none;")
            row.addWidget(ico)
            row.addWidget(txt)
            row.addStretch()
            feat_lay.addLayout(row)
        lay.addWidget(feat_w)
        lay.addSpacing(30)

        btn_start = QPushButton("  Kuruluma Basla  ->")
        btn_start.setObjectName("btn_primary")
        btn_start.setFixedHeight(46)
        btn_start.setFixedWidth(220)
        btn_start.clicked.connect(self._start_detection)
        lay.addWidget(btn_start, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(10)

        skip_btn = QPushButton("Zaten kurulu, atla ->")
        skip_btn.setStyleSheet(
            f"color:{C_TEXT_DIM}; background:transparent; border:none; font-size:12px;"
        )
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.clicked.connect(self._skip_all)
        lay.addWidget(skip_btn, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _build_detect(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(60, 32, 60, 32)
        lay.setSpacing(10)
        t = QLabel("Sistem Tespiti")
        t.setStyleSheet(f"color:{C_TEXT}; font-size:20px; font-weight:700;")
        sub = QLabel("Gerekli araclar kontrol ediliyor, lutfen bekleyin...")
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        lay.addWidget(t)
        lay.addWidget(sub)
        lay.addSpacing(6)

        self._tool_rows = {}
        for name, desc in [
            ("Python Paketleri", "PyQt6, matplotlib, psutil, requests ve digerleri"),
            ("Docker Desktop",   "Konteyner calisma ortami"),
            ("Minikube",         "Yerel Kubernetes cluster"),
            ("kubectl",          "Kubernetes komut satiri araci"),
            ("Helm",             "Kubernetes paket yoneticisi"),
        ]:
            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background:{C_SURFACE2}; border:1px solid rgba(255,255,255,0.07); border-radius:10px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(16, 10, 16, 10)
            rl.setSpacing(10)
            dot = StatusDot(C_TEXT_DIM)
            name_col = QVBoxLayout()
            name_col.setSpacing(1)
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:13px; background:transparent; border:none;")
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; background:transparent; border:none;")
            name_col.addWidget(name_lbl)
            name_col.addWidget(desc_lbl)
            ver_lbl = QLabel("Bekleniyor...")
            ver_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;")
            ver_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rl.addWidget(dot)
            rl.addSpacing(4)
            rl.addLayout(name_col, 1)
            rl.addWidget(ver_lbl)
            self._tool_rows[name] = {"dot": dot, "ver": ver_lbl}
            lay.addWidget(row)

        lay.addStretch()
        btn_row = QHBoxLayout()
        self._btn_recheck = QPushButton("Tekrar Kontrol")
        self._btn_recheck.clicked.connect(self._start_detection)
        self._btn_detect_next = QPushButton("Devam ->")
        self._btn_detect_next.setObjectName("btn_primary")
        self._btn_detect_next.setEnabled(False)
        self._btn_detect_next.clicked.connect(self._after_detection)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_recheck)
        btn_row.addWidget(self._btn_detect_next)
        lay.addLayout(btn_row)
        return w

    def _build_install_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(48, 28, 48, 28)
        lay.setSpacing(10)
        t = QLabel("Otomatik Kurulum")
        t.setStyleSheet(f"color:{C_TEXT}; font-size:20px; font-weight:700;")
        sub = QLabel("Eksik araclar otomatik kuruluyor. Bu islem 5-10 dakika surebilir.")
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        sub.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(sub)
        lay.addSpacing(4)
        self._install_pb = QProgressBar()
        self._install_pb.setRange(0, 0)
        self._install_pb.setFixedHeight(5)
        lay.addWidget(self._install_pb)
        self._install_status = QLabel("Basliyor...")
        self._install_status.setStyleSheet(f"color:{C_ACCENT}; font-size:12px;")
        lay.addWidget(self._install_status)
        self._install_log = LogWidget()
        self._install_log.setMinimumHeight(260)
        lay.addWidget(self._install_log)
        btn_row = QHBoxLayout()
        self._btn_install_retry = QPushButton("Tekrar Dene")
        self._btn_install_retry.setVisible(False)
        self._btn_install_retry.clicked.connect(self._run_install)
        self._btn_install_next = QPushButton("Devam ->")
        self._btn_install_next.setObjectName("btn_primary")
        self._btn_install_next.setEnabled(False)
        self._btn_install_next.clicked.connect(
            lambda: (self._go_to(3), QTimer.singleShot(300, self._run_cluster_setup))
        )
        btn_row.addStretch()
        btn_row.addWidget(self._btn_install_retry)
        btn_row.addWidget(self._btn_install_next)
        lay.addLayout(btn_row)
        return w

    def _build_cluster_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(48, 28, 48, 28)
        lay.setSpacing(10)
        t = QLabel("Cluster Kurulumu")
        t.setStyleSheet(f"color:{C_TEXT}; font-size:20px; font-weight:700;")
        sub = QLabel(
            "Minikube cluster baslatiliyor. Ilk kurulumda 2-5 dakika surebilir. "
            "Docker Desktop acik olmalidir."
        )
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        sub.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(sub)
        lay.addSpacing(4)
        self._cluster_pb = QProgressBar()
        self._cluster_pb.setRange(0, 0)
        self._cluster_pb.setFixedHeight(5)
        lay.addWidget(self._cluster_pb)
        self._cluster_status_lbl = QLabel("Cluster bekleniyor...")
        self._cluster_status_lbl.setStyleSheet(f"color:{C_ACCENT}; font-size:12px;")
        lay.addWidget(self._cluster_status_lbl)
        self._cluster_log = LogWidget()
        self._cluster_log.setMinimumHeight(260)
        lay.addWidget(self._cluster_log)
        btn_row = QHBoxLayout()
        self._btn_cluster_retry = QPushButton("Tekrar Dene")
        self._btn_cluster_retry.setVisible(False)
        self._btn_cluster_retry.clicked.connect(self._run_cluster_setup)
        self._btn_cluster_next = QPushButton("Devam ->")
        self._btn_cluster_next.setObjectName("btn_primary")
        self._btn_cluster_next.setEnabled(False)
        self._btn_cluster_next.clicked.connect(
            lambda: (self._go_to(4), QTimer.singleShot(300, self._run_helm))
        )
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cluster_retry)
        btn_row.addWidget(self._btn_cluster_next)
        lay.addLayout(btn_row)
        return w

    def _build_helm_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(48, 28, 48, 28)
        lay.setSpacing(10)
        t = QLabel("Helm Chart Kurulumu")
        t.setStyleSheet(f"color:{C_TEXT}; font-size:20px; font-weight:700;")
        sub = QLabel("Prometheus, Pushgateway ve KEDA kuruluyor (5-10 dk).")
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        lay.addWidget(t)
        lay.addWidget(sub)
        lay.addSpacing(4)
        self._helm_pb = QProgressBar()
        self._helm_pb.setRange(0, 0)
        self._helm_pb.setFixedHeight(5)
        lay.addWidget(self._helm_pb)
        self._helm_status_lbl = QLabel("Basliyor...")
        self._helm_status_lbl.setStyleSheet(f"color:{C_ACCENT}; font-size:12px;")
        lay.addWidget(self._helm_status_lbl)
        self._helm_log = LogWidget()
        self._helm_log.setMinimumHeight(260)
        lay.addWidget(self._helm_log)
        btn_row = QHBoxLayout()
        self._btn_helm_retry = QPushButton("Tekrar Dene")
        self._btn_helm_retry.setVisible(False)
        self._btn_helm_retry.clicked.connect(self._run_helm)
        self._btn_helm_next = QPushButton("Tamamla ->")
        self._btn_helm_next.setObjectName("btn_success")
        self._btn_helm_next.setEnabled(False)
        self._btn_helm_next.clicked.connect(lambda: self._go_to(5))
        btn_row.addStretch()
        btn_row.addWidget(self._btn_helm_retry)
        btn_row.addWidget(self._btn_helm_next)
        lay.addLayout(btn_row)
        return w

    def _build_done(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(16)
        lay.setContentsMargins(100, 60, 100, 60)
        check = QLabel("OK!")
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check.setStyleSheet(
            f"color:{C_GREEN}; font-size:48px; font-weight:700; "
            f"background:transparent; border:none;"
        )
        lay.addWidget(check)
        t = QLabel("Kurulum Tamamlandi!")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{C_TEXT}; font-size:24px; font-weight:700;")
        sub = QLabel("AutoScaleOps kullanima hazir.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        lay.addWidget(t)
        lay.addWidget(sub)
        lay.addSpacing(32)
        btn = QPushButton("  Uygulamayi Ac  ->")
        btn.setObjectName("btn_success")
        btn.setFixedHeight(48)
        btn.setFixedWidth(220)
        btn.clicked.connect(self._finish_setup)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _start_detection(self):
        self._go_to(1)
        self._btn_detect_next.setEnabled(False)
        for row in self._tool_rows.values():
            row["dot"].set_color(C_YELLOW)
            row["ver"].setText("Kontrol ediliyor...")

        def _detect():
            results = self.ops.all_prereq_checks()
            self._missing_tools = []
            for res in results:
                name = res["name"]
                if name not in self._tool_rows:
                    continue
                ok  = res["ok"]
                ver = res.get("version") or ("OK" if ok else "Bulunamadi")
                col = C_GREEN if ok else C_RED
                _n, _v, _c = name, ver, col
                QTimer.singleShot(0, lambda n=_n, v=_v, c=_c: self._update_tool_row(n, v, c))
                if not ok:
                    self._missing_tools.append(name)
            QTimer.singleShot(200, self._on_detection_done)

        import threading
        threading.Thread(target=_detect, daemon=True).start()

    def _update_tool_row(self, name: str, ver: str, color: str):
        if name in self._tool_rows:
            self._tool_rows[name]["dot"].set_color(color)
            self._tool_rows[name]["ver"].setText(ver)

    def _on_detection_done(self):
        self._btn_detect_next.setEnabled(True)

    def _after_detection(self):
        if self._missing_tools:
            self._go_to(2)
            QTimer.singleShot(300, self._run_install)
        else:
            self._go_to(3)
            QTimer.singleShot(300, self._run_cluster_setup)

    def _run_install(self):
        self._install_log.clear()
        self._install_status.setText("Kurulum basliyor...")
        self._btn_install_retry.setVisible(False)
        self._btn_install_next.setEnabled(False)
        self._install_pb.setRange(0, 0)
        self._install_worker = _InstallWorker(self._missing_tools)
        self._install_worker.progress.connect(self._on_install_progress)
        self._install_worker.tool_done.connect(self._on_install_tool_done)
        self._install_worker.all_done.connect(self._on_install_all_done)
        self._install_worker.start()

    @pyqtSlot(str, str)
    def _on_install_progress(self, msg: str, level: str):
        self._install_log.append_line(msg, level)
        self._install_status.setText(msg[:90])

    @pyqtSlot(str, bool)
    def _on_install_tool_done(self, name: str, ok: bool):
        if name in self._tool_rows:
            self._tool_rows[name]["dot"].set_color(C_GREEN if ok else C_RED)

    @pyqtSlot(bool)
    def _on_install_all_done(self, ok: bool):
        self._install_pb.setRange(0, 1)
        self._install_pb.setValue(1)
        if ok:
            self._install_status.setText("Tum araclar kuruldu!")
            self._btn_install_next.setEnabled(True)
            QTimer.singleShot(800, lambda: self._go_to(3))
            QTimer.singleShot(1200, self._run_cluster_setup)
        else:
            self._install_status.setText("Bazi araclar kurulamadi, elle kurulum gerekebilir.")
            self._btn_install_retry.setVisible(True)
            self._btn_install_next.setEnabled(True)

    def _run_cluster_setup(self):
        self._cluster_log.clear()
        self._cluster_status_lbl.setText("Cluster baslatiliyor...")
        self._btn_cluster_retry.setVisible(False)
        self._btn_cluster_next.setEnabled(False)
        self._cluster_pb.setRange(0, 0)
        self._cluster_thread = QThread(self)
        self._cluster_worker_wiz = ClusterWorker(self.ops, "start")
        self._cluster_worker_wiz.moveToThread(self._cluster_thread)
        self._cluster_thread.started.connect(self._cluster_worker_wiz.run)
        self._cluster_worker_wiz.progress.connect(self._on_cluster_progress)
        self._cluster_worker_wiz.finished.connect(self._on_cluster_done)
        self._cluster_worker_wiz.finished.connect(self._cluster_thread.quit)
        self._cluster_thread.start()

    @pyqtSlot(str, str)
    def _on_cluster_progress(self, msg: str, level: str):
        self._cluster_log.append_line(msg, level)
        self._cluster_status_lbl.setText(msg[:90])

    @pyqtSlot(bool, str)
    def _on_cluster_done(self, ok: bool, msg: str):
        self._cluster_pb.setRange(0, 1)
        self._cluster_pb.setValue(1)
        if ok:
            self._cluster_status_lbl.setText("Cluster hazir!")
            self._btn_cluster_next.setEnabled(True)
            QTimer.singleShot(800, lambda: self._go_to(4))
            QTimer.singleShot(1200, self._run_helm)
        else:
            self._cluster_status_lbl.setText(f"Cluster baslatılamadi: {msg}")
            self._btn_cluster_retry.setVisible(True)
            self._btn_cluster_next.setEnabled(True)

    def _run_helm(self):
        self._helm_log.clear()
        self._helm_status_lbl.setText("Helm chartlar kuruluyor...")
        self._btn_helm_retry.setVisible(False)
        self._btn_helm_next.setEnabled(False)
        self._helm_pb.setRange(0, 0)
        self._helm_worker = _HelmWorker()
        self._helm_worker.progress.connect(self._on_helm_progress)
        self._helm_worker.finished.connect(self._on_helm_done)
        self._helm_worker.start()

    @pyqtSlot(str, str)
    def _on_helm_progress(self, msg: str, level: str):
        self._helm_log.append_line(msg, level)
        self._helm_status_lbl.setText(msg[:90])

    @pyqtSlot(bool, str)
    def _on_helm_done(self, ok: bool, msg: str):
        self._helm_pb.setRange(0, 1)
        self._helm_pb.setValue(1)
        if ok:
            self._helm_status_lbl.setText("Helm kurulumlari tamamlandi!")
            self._btn_helm_next.setEnabled(True)
            QTimer.singleShot(800, lambda: self._go_to(5))
        else:
            self._helm_status_lbl.setText("Bazi chartlar kurulamadi.")
            self._btn_helm_retry.setVisible(True)
            self._btn_helm_next.setEnabled(True)

    def _skip_all(self):
        self._finish_setup()

    def _finish_setup(self):
        try:
            SETUP_COMPLETE_PATH.write_text(
                json.dumps({"completed_at": datetime.now().isoformat(), "version": APP_VERSION}),
                encoding="utf-8"
            )
        except Exception:
            pass
        self.wizard_done.emit()





# ─────────────────────────────────────────────
#  PANEL 1 — HOME / DASHBOARD  (iOS 26 style)
# ─────────────────────────────────────────────
class HomePanel(QWidget):
    # Kept for backward-compat with MainWindow signal connections
    request_cluster_action = pyqtSignal(str)
    navigate_to = pyqtSignal(int)   # panel index'e git (5 = Deploy)

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db  = db
        self.ops = ops
        self._mode = "local"          # "local" | "live"
        self._launch_worker: Optional[LaunchWorker] = None
        self._is_running = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(0)

        # ── HERO ──────────────────────────────────────────────────────────
        hero = QVBoxLayout()
        hero.setSpacing(6)
        hero.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        title_lbl = QLabel("AutoScaleOps")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f_title = QFont("Segoe UI", 24, QFont.Weight.Bold)
        title_lbl.setFont(f_title)
        title_lbl.setStyleSheet(f"color:{C_TEXT};")

        sub_lbl = QLabel("AI destekli Kubernetes platformunuz")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f_sub = QFont("Segoe UI", 12)
        sub_lbl.setFont(f_sub)
        sub_lbl.setStyleSheet(f"color:{C_TEXT_DIM};")

        hero.addWidget(title_lbl)
        hero.addWidget(sub_lbl)
        lay.addLayout(hero)
        lay.addSpacing(16)

        # ── GEREKSİNİM ŞERİDİ ────────────────────────────────────────────
        # Arka planda kontrol et, renk göster, tıklanabilir
        self._prereq_strip = QFrame()
        self._prereq_strip.setFixedHeight(44)
        self._prereq_strip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prereq_strip.setStyleSheet(f"""
            QFrame {{
                background:{C_SURFACE2};
                border:1px solid {C_BORDER};
                border-radius:12px;
            }}
            QFrame:hover {{ background:{C_HOVER}; }}
        """)
        strip_lay = QHBoxLayout(self._prereq_strip)
        strip_lay.setContentsMargins(14, 0, 14, 0)
        strip_lay.setSpacing(8)

        self._prereq_items: dict = {}   # key → QLabel (ikon)
        labels = [
            ("docker",      "Docker"),
            ("minikube",    "Minikube"),
            ("kubectl",     "kubectl"),
            ("ngrok",       "ngrok"),
            ("python_deps", "Paketler"),
        ]
        for key, name in labels:
            dot = QLabel("⬤")
            dot.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:9px; background:transparent; border:none;")
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;")
            self._prereq_items[key] = dot
            strip_lay.addWidget(dot)
            strip_lay.addWidget(lbl)
            if key != "python_deps":
                sep = QLabel("|")
                sep.setStyleSheet(f"color:{C_BORDER}; background:transparent; border:none; padding:0 4px;")
                strip_lay.addWidget(sep)

        strip_lay.addStretch()
        info_lbl = QLabel("Sistem Gereksinimleri →")
        info_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; background:transparent; border:none;")
        strip_lay.addWidget(info_lbl)

        # Tıklanınca Sistem sekmesine git
        self._prereq_strip.mousePressEvent = lambda e: self.request_cluster_action.emit("_nav_system")
        lay.addWidget(self._prereq_strip)
        lay.addSpacing(16)

        # Arka planda kontrol başlat
        self._strip_worker = SystemCheckWorker()
        self._strip_worker.result.connect(self._update_prereq_strip)
        self._strip_worker.start()

        # ── MODE CHIPS ────────────────────────────────────────────────────
        chips_row = QHBoxLayout()
        chips_row.setSpacing(10)
        chips_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._chip_local = QPushButton("🏠   Yerel")
        self._chip_local.setObjectName("mode_chip")
        self._chip_local.setProperty("active", "true")
        self._chip_local.setFixedHeight(38)
        self._chip_local.clicked.connect(lambda: self._set_mode("local"))

        self._chip_live = QPushButton("🌐   Canlıya Al")
        self._chip_live.setObjectName("mode_chip")
        self._chip_live.setProperty("active", "false")
        self._chip_live.setFixedHeight(38)
        self._chip_live.clicked.connect(lambda: self._set_mode("live"))

        chips_row.addWidget(self._chip_local)
        chips_row.addWidget(self._chip_live)
        lay.addLayout(chips_row)
        lay.addSpacing(18)

        # ── ACTIVE PROJECT CARD ───────────────────────────────────────────
        # Hangi projenin deploy edileceğini gösterir / değiştirmeye izin verir
        self._project_card = QFrame()
        self._project_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08); "
            f"border-radius:14px; }}"
        )
        _add_shadow(self._project_card, blur=16, offset_y=3, alpha=50)
        pc_lay = QHBoxLayout(self._project_card)
        pc_lay.setContentsMargins(16, 12, 16, 12)
        pc_lay.setSpacing(10)

        proj_icon = QLabel("📦")
        proj_icon.setFont(QFont("Segoe UI", 14))
        proj_icon.setStyleSheet("background:transparent; border:none;")

        proj_text = QVBoxLayout()
        proj_text.setSpacing(2)
        self._proj_name_lbl = QLabel("Proje seçilmedi")
        self._proj_name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._proj_name_lbl.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        self._proj_meta_lbl = QLabel("")
        self._proj_meta_lbl.setFont(QFont("Segoe UI", 10))
        self._proj_meta_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._proj_fmt_lbl = QLabel("")
        self._proj_fmt_lbl.setFont(QFont("Segoe UI", 10))
        self._proj_fmt_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._proj_fmt_lbl.setWordWrap(True)
        proj_text.addWidget(self._proj_name_lbl)
        proj_text.addWidget(self._proj_meta_lbl)
        proj_text.addWidget(self._proj_fmt_lbl)

        self._btn_pick_proj = QPushButton("Değiştir")
        self._btn_pick_proj.setFixedWidth(90)
        self._btn_pick_proj.setFixedHeight(32)
        self._btn_pick_proj.clicked.connect(self._pick_project)

        self._btn_go_deploy = QPushButton("＋  Deploy Et")
        self._btn_go_deploy.setObjectName("btn_primary")
        self._btn_go_deploy.setFixedHeight(32)
        self._btn_go_deploy.setFixedWidth(110)
        self._btn_go_deploy.setVisible(False)
        self._btn_go_deploy.clicked.connect(
            lambda: self.request_cluster_action.emit("_nav_deploy_mgr")
        )

        pc_btn_col = QVBoxLayout()
        pc_btn_col.setSpacing(6)
        pc_btn_col.addWidget(self._btn_pick_proj)
        pc_btn_col.addWidget(self._btn_go_deploy)

        pc_lay.addWidget(proj_icon)
        pc_lay.addLayout(proj_text, 1)
        pc_lay.addLayout(pc_btn_col)
        lay.addWidget(self._project_card)
        lay.addSpacing(16)

        # ── LAUNCH BUTTON ─────────────────────────────────────────────────
        btn_center = QHBoxLayout()
        btn_center.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._btn_launch = QPushButton("▶   Başlat")
        self._btn_launch.setObjectName("btn_launch")
        self._btn_launch.setFixedHeight(54)
        self._btn_launch.setFixedWidth(220)
        self._btn_launch.clicked.connect(self._do_launch)

        self._btn_stop_all = QPushButton("⏹   Durdur")
        self._btn_stop_all.setObjectName("btn_danger")
        self._btn_stop_all.setFixedHeight(54)
        self._btn_stop_all.setFixedWidth(220)
        self._btn_stop_all.setVisible(False)
        self._btn_stop_all.clicked.connect(self._do_stop)

        btn_center.addWidget(self._btn_launch)
        btn_center.addWidget(self._btn_stop_all)
        lay.addLayout(btn_center)
        lay.addSpacing(28)

        # ── STEP INDICATORS ───────────────────────────────────────────────
        steps_card = QFrame()
        steps_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08); "
            f"border-radius:18px; }}"
        )
        _add_shadow(steps_card, blur=24, offset_y=6, alpha=70)
        steps_layout = QHBoxLayout(steps_card)
        steps_layout.setContentsMargins(20, 16, 20, 16)
        steps_layout.setSpacing(0)

        self._step_docker    = StepWidget("Docker")
        self._step_cluster   = StepWidget("Cluster")
        self._step_dashboard = StepWidget("Dashboard")
        self._step_tunnel    = StepWidget("Tünel")

        def _sep():
            s = QLabel("─")
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setStyleSheet(f"color:{C_BORDER}; font-size:18px;")
            return s

        steps_layout.addStretch()
        steps_layout.addWidget(self._step_docker)
        steps_layout.addWidget(_sep())
        steps_layout.addWidget(self._step_cluster)
        steps_layout.addWidget(_sep())
        steps_layout.addWidget(self._step_dashboard)
        self._sep_tunnel = _sep()
        steps_layout.addWidget(self._sep_tunnel)
        steps_layout.addWidget(self._step_tunnel)
        steps_layout.addStretch()
        lay.addWidget(steps_card)
        lay.addSpacing(16)

        # ── ERROR CARD ────────────────────────────────────────────────────
        self._error_card = ErrorCard()
        self._error_card.fix_clicked.connect(self._on_fix_clicked)
        self._fix_action: str = ""
        lay.addWidget(self._error_card)

        # ── STATS ROW ─────────────────────────────────────────────────────
        stats_card = QFrame()
        stats_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08); "
            f"border-radius:18px; }}"
        )
        _add_shadow(stats_card, blur=20, offset_y=4, alpha=60)
        stats_grid = QHBoxLayout(stats_card)
        stats_grid.setContentsMargins(20, 16, 20, 16)
        stats_grid.setSpacing(0)
        self._stat_rps  = self._make_stat("RPS",     "—")
        self._stat_pods = self._make_stat("Podlar",  "—")
        self._stat_cpu  = self._make_stat("CPU",     "—")
        self._stat_mem  = self._make_stat("RAM",     "—")
        for i, w in enumerate([self._stat_rps, self._stat_pods, self._stat_cpu, self._stat_mem]):
            stats_grid.addWidget(w, 1)
            if i < 3:
                div = QFrame()
                div.setFixedWidth(1)
                div.setStyleSheet(f"background: rgba(255,255,255,0.07);")
                stats_grid.addWidget(div)
        lay.addWidget(stats_card)
        lay.addSpacing(16)

        # ── STATUS / URL CARD ─────────────────────────────────────────────
        self._status_card = QFrame()
        self._status_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08); border-radius:18px; }}"
        )
        _add_shadow(self._status_card, blur=24, offset_y=4, alpha=60)
        sc_lay = QVBoxLayout(self._status_card)
        sc_lay.setContentsMargins(22, 18, 22, 18)
        sc_lay.setSpacing(12)

        # — Ana URL satırı (app port veya ngrok) —
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self._url_icon = QLabel("🏠")
        self._url_icon.setFont(QFont("Segoe UI", 16))
        self._url_icon.setStyleSheet("background:transparent; border:none;")
        self._url_main_lbl = QLabel("http://localhost:8080")
        self._url_main_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._url_main_lbl.setStyleSheet(f"color:{C_ACCENT}; background:transparent; border:none;")
        self._url_main_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._btn_copy_main = QPushButton("Kopyala")
        self._btn_copy_main.setFixedWidth(82)
        self._btn_copy_main.clicked.connect(self._copy_url)
        self._btn_open_main = QPushButton("Aç ↗")
        self._btn_open_main.setObjectName("btn_primary")
        self._btn_open_main.setFixedWidth(70)
        self._btn_open_main.clicked.connect(self._open_url)
        row1.addWidget(self._url_icon)
        row1.addWidget(self._url_main_lbl, 1)
        row1.addWidget(self._btn_copy_main)
        row1.addWidget(self._btn_open_main)
        sc_lay.addLayout(row1)

        # — Divider —
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: rgba(255,255,255,0.06); border:none;")
        sc_lay.addWidget(div)

        # — Dashboard satırı —
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        dash_icon = QLabel("📊")
        dash_icon.setFont(QFont("Segoe UI", 14))
        dash_icon.setStyleSheet("background:transparent; border:none;")
        dash_lbl = QLabel("Dashboard  —  http://localhost:8501")
        dash_lbl.setFont(QFont("Segoe UI", 11))
        dash_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._btn_open_dash_home = QPushButton("Aç ↗")
        self._btn_open_dash_home.setFixedWidth(70)
        self._btn_open_dash_home.clicked.connect(lambda: webbrowser.open("http://localhost:8501"))
        row2.addWidget(dash_icon)
        row2.addWidget(dash_lbl, 1)
        row2.addWidget(self._btn_open_dash_home)
        sc_lay.addLayout(row2)

        # — ngrok uyarı notu (sadece live modunda görünür) —
        self._ngrok_note = QLabel(
            "ℹ️  Free tier: sitenizi ilk ziyaret edenlerde bir uyarı sayfası çıkar — "
            "'Visit Site'a tıklayınca geçer. Sabit URL için ngrok token girin (Tünel sekmesi)."
        )
        self._ngrok_note.setFont(QFont("Segoe UI", 10))
        self._ngrok_note.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._ngrok_note.setWordWrap(True)
        self._ngrok_note.setVisible(False)
        sc_lay.addWidget(self._ngrok_note)

        self._status_card.setVisible(False)
        lay.addWidget(self._status_card)

        # ── DEPLOY KISAYOLU KARTI ─────────────────────────────────────────
        lay.addSpacing(16)
        deploy_card = QFrame()
        deploy_card.setCursor(Qt.CursorShape.PointingHandCursor)
        deploy_card.setStyleSheet(f"""
            QFrame {{
                background: {C_SURFACE2};
                border: 1px solid rgba(99,102,241,0.25);
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid rgba(99,102,241,0.55);
                background: rgba(99,102,241,0.07);
            }}
        """)
        dc_lay = QHBoxLayout(deploy_card)
        dc_lay.setContentsMargins(20, 14, 16, 14)
        dc_lay.setSpacing(14)

        icon_lbl = QLabel("△")
        icon_lbl.setFont(QFont("Segoe UI", 18))
        icon_lbl.setStyleSheet(f"color:{C_ACCENT}; background:transparent; border:none;")
        icon_lbl.setFixedWidth(28)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        title_d = QLabel("Deploy Yönetimi")
        title_d.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_d.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        desc_d = QLabel("Projenizi yayınlamak için proje bu bölümden seçilip deploy edilir.")
        desc_d.setFont(QFont("Segoe UI", 10))
        desc_d.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        text_col.addWidget(title_d)
        text_col.addWidget(desc_d)

        btn_deploy_go = QPushButton("Deploy →")
        btn_deploy_go.setFixedWidth(90)
        btn_deploy_go.setFixedHeight(32)
        btn_deploy_go.setStyleSheet(f"""
            QPushButton {{
                background: rgba(99,102,241,0.15);
                color: {C_ACCENT};
                border: 1px solid rgba(99,102,241,0.35);
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(99,102,241,0.30);
            }}
        """)
        btn_deploy_go.clicked.connect(lambda: self.navigate_to.emit(5))

        dc_lay.addWidget(icon_lbl)
        dc_lay.addLayout(text_col, 1)
        dc_lay.addWidget(btn_deploy_go)

        # Kartın tamamına tıklayınca da git
        deploy_card.mousePressEvent = lambda e: self.navigate_to.emit(5)

        lay.addWidget(deploy_card)
        lay.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # İlk yüklemede aktif proje bilgisini göster
        self._refresh_project_label()

    # ── PRIVATE HELPERS ───────────────────────────────────────────────────

    def _make_stat(self, label: str, value: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet("QFrame { background: transparent; border: none; }")
        fl = QVBoxLayout(f)
        fl.setContentsMargins(16, 8, 16, 8)
        fl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(label.upper())
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; font-weight:600; letter-spacing:1px;")
        val = QLabel(value)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(f"color:{C_TEXT}; font-size:22px; font-weight:700;")
        val.setObjectName(f"stat_{label.lower()}")
        fl.addWidget(lbl)
        fl.addWidget(val)
        return f

    def _get_stat_label(self, frame: QFrame, key: str) -> Optional[QLabel]:
        for child in frame.findChildren(QLabel):
            if child.objectName() == f"stat_{key}":
                return child
        return None

    # ── PROJECT SELECTION HELPERS ──────────────────────────────────────────

    def _get_project_type_label(self, folder: str) -> str:
        """Proje klasörüne bakarak tip ve gerekli dosyaları döndürür."""
        if not folder:
            return ""
        p = Path(folder)
        if (p / "requirements.txt").exists() or list(p.glob("*.py")):
            return "Python  •  requirements.txt / *.py gerekli"
        if (p / "package.json").exists():
            return "Node.js  •  package.json gerekli"
        if (p / "index.html").exists() or list(p.glob("*.html")):
            return "Statik HTML  •  index.html gerekli"
        if (p / "Dockerfile").exists():
            return "Docker  •  Dockerfile mevcut"
        return "Proje türü tespit edilemedi  •  Dockerfile ekleyin"

    def _refresh_project_label(self):
        """Aktif proje bilgisini DB'den okuyup project card'ı günceller."""
        try:
            projects = self.db.get_all_projects()
            active = next((p for p in projects if p.get("is_active")), None)
            if not active:
                active = projects[0] if projects else None

            if active:
                name   = active.get("name", "?")
                port   = active.get("port", "—")
                folder = active.get("folder", "")
                self._proj_name_lbl.setText(name)
                self._proj_meta_lbl.setText(f"Port: {port}")
                self._proj_fmt_lbl.setText(self._get_project_type_label(folder))
                self._btn_pick_proj.setVisible(True)
                self._btn_go_deploy.setVisible(False)
            else:
                self._proj_name_lbl.setText("Henüz deploy edilmiş proje yok")
                self._proj_name_lbl.setStyleSheet(
                    f"color:{C_RED}; background:transparent; border:none;"
                )
                self._proj_meta_lbl.setText(
                    "Deploy sekmesine giderek ilk projenizi ekleyin."
                )
                self._proj_fmt_lbl.setText("")
                # "Değiştir" yerine "Deploy Et" butonu göster
                self._btn_pick_proj.setVisible(False)
                self._btn_go_deploy.setVisible(True)
        except Exception:
            pass

    def _pick_project(self):
        """Kullanıcının aktif projeyi seçmesini sağlayan basit dialog."""
        try:
            projects = self.db.get_all_projects()
        except Exception:
            projects = []
        if not projects:
            reply = QMessageBox.question(
                self, "Proje Yok",
                "Henüz deploy edilmiş proje bulunamadı.\n\n"
                "Deploy sekmesine giderek ilk projenizi eklemek ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.request_cluster_action.emit("_nav_deploy_mgr")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Proje Seç")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            f"QDialog {{ background:{C_BG}; }} "
            f"QLabel {{ color:{C_TEXT}; }} "
        )
        vl = QVBoxLayout(dlg)
        vl.setContentsMargins(20, 20, 20, 20)
        vl.setSpacing(10)

        hdr = QLabel("Yayınlamak istediğiniz projeyi seçin:")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        vl.addWidget(hdr)

        fmt_note = QLabel(
            "📋  Proje formatı:  Python → requirements.txt / *.py  |  "
            "Node.js → package.json  |  Statik → index.html"
        )
        fmt_note.setFont(QFont("Segoe UI", 10))
        fmt_note.setStyleSheet(f"color:{C_TEXT_DIM};")
        fmt_note.setWordWrap(True)
        vl.addWidget(fmt_note)

        selected_name: list = [None]

        for proj in projects:
            pname  = proj.get("name", "?")
            pport  = proj.get("port", "—")
            folder = proj.get("folder", "")
            is_act = proj.get("is_active", 0)

            btn = QPushButton()
            btn.setFixedHeight(56)
            btn_lay = QHBoxLayout(btn)
            btn_lay.setContentsMargins(12, 8, 12, 8)

            icon_lbl = QLabel("✅" if is_act else "📦")
            icon_lbl.setFont(QFont("Segoe UI", 14))
            icon_lbl.setStyleSheet("background:transparent; border:none;")

            info_col = QVBoxLayout()
            n_lbl = QLabel(pname)
            n_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            n_lbl.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
            m_lbl = QLabel(f"Port {pport}  •  {self._get_project_type_label(folder)}")
            m_lbl.setFont(QFont("Segoe UI", 10))
            m_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
            info_col.addWidget(n_lbl)
            info_col.addWidget(m_lbl)

            btn_lay.addWidget(icon_lbl)
            btn_lay.addLayout(info_col, 1)

            if is_act:
                btn.setStyleSheet(
                    f"QPushButton {{ background:{C_SURFACE2}; border:1px solid {C_ACCENT}; "
                    f"border-radius:10px; }} "
                    f"QPushButton:hover {{ background:{C_HOVER}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08); "
                    f"border-radius:10px; }} "
                    f"QPushButton:hover {{ background:{C_HOVER}; }}"
                )

            def _on_pick(n=pname):
                selected_name[0] = n
                dlg.accept()

            btn.clicked.connect(_on_pick)
            vl.addWidget(btn)

        cancel = QPushButton("İptal")
        cancel.setFixedHeight(38)
        cancel.clicked.connect(dlg.reject)
        vl.addWidget(cancel)

        if dlg.exec() == QDialog.DialogCode.Accepted and selected_name[0]:
            try:
                self.db.set_active_project(selected_name[0])
                # JSON'u da güncelle ki dashboard hemen yeni projeyi görsün
                projs = [p for p in self.db.get_all_projects() if p.get("name") == selected_name[0]]
                if projs:
                    p = projs[0]
                    _write_active_project_json(
                        p.get("name", selected_name[0]),
                        p.get("port", 8080),
                        p.get("service_name", f"{selected_name[0]}-service")
                    )
                self._refresh_project_label()
            except Exception:
                pass

    def _update_prereq_strip(self, checks: dict):
        """Gereksinim şeridinin renklerini günceller."""
        all_ok = all(v["ok"] for v in checks.values())
        # Şerit çerçeve rengi
        border_col = "rgba(52,211,153,0.3)" if all_ok else "rgba(248,113,113,0.3)"
        self._prereq_strip.setStyleSheet(f"""
            QFrame {{
                background:{C_SURFACE2};
                border:1px solid {border_col};
                border-radius:12px;
            }}
            QFrame:hover {{ background:{C_HOVER}; }}
        """)
        # Her dot'u güncelle
        for key, dot in self._prereq_items.items():
            ok = checks.get(key, {}).get("ok", False)
            color = C_GREEN if ok else C_RED
            dot.setStyleSheet(
                f"color:{color}; font-size:9px; background:transparent; border:none;"
            )

    def _set_mode(self, mode: str):
        self._mode = mode
        active_chip = self._chip_local if mode == "local" else self._chip_live
        inactive_chip = self._chip_live if mode == "local" else self._chip_local
        active_chip.setProperty("active", "true")
        inactive_chip.setProperty("active", "false")
        # Force QSS refresh
        for c in [active_chip, inactive_chip]:
            c.style().unpolish(c)
            c.style().polish(c)
        # Canlıya Al moduna geçince proje bilgisini tazele
        if mode == "live":
            self._refresh_project_label()

    def _set_all_steps(self, status: str):
        for sw in [self._step_docker, self._step_cluster, self._step_dashboard, self._step_tunnel]:
            sw.set_status(status)

    def _do_launch(self):
        if self._is_running:
            return
        self._is_running = True
        self._btn_launch.setVisible(False)
        self._btn_stop_all.setVisible(True)
        self._error_card.hide_error()
        self._status_card.setVisible(False)
        self._set_all_steps("idle")

        self._launch_worker = LaunchWorker(self.ops, self._mode, self)
        self._launch_worker.step_update.connect(self._on_step_update)
        self._launch_worker.error_signal.connect(self._on_error)
        self._launch_worker.url_ready.connect(self._on_url_ready)
        self._launch_worker.finished.connect(self._on_launch_done)
        self._launch_worker.start()

    def _check_port_forward(self):
        """Port-forward watchdog: HTTP seviyesinde kontrol; kırıksa yeniden başlat."""
        port = int(self.ops.db.get_setting("active_project_port", "8080"))
        # TCP değil, gerçek HTTP kontrolü (TCP open ama HTTP broken → kırık process)
        app_ok = self.ops.check_app()
        if app_ok:
            return
        # HTTP başarısız → eski process'leri temizle ve yeniden başlat
        def _restart():
            try:
                instance = self.ops.ensure_instance()
                ns = instance.get("namespace", "autoscaleops")
                self.ops.stop_port_forwards()       # kırık olanları zorla kapat
                import time as _t; _t.sleep(1)
                self.ops.start_port_forwards(ns)
            except Exception:
                pass
        threading.Thread(target=_restart, daemon=True).start()
        self._error_card.show_error(
            "Port-Forward Yeniden Başlatıldı",
            f"localhost:{port} yanıt vermiyordu — bağlantı otomatik yeniden kuruldu.",
            warning=True
        )
        # 10 sn sonra temizle
        QTimer.singleShot(10000, self._error_card.hide_error)

    def _do_stop(self):
        dlg = ShutdownDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return  # İptal

        choice = dlg.choice  # "services" | "full"
        self._btn_stop_all.setEnabled(False)

        if self._launch_worker and self._launch_worker.isRunning():
            self._launch_worker.quit()

        # Watchdog'u durdur
        if hasattr(self, '_pf_watchdog'):
            self._pf_watchdog.stop()

        # UI'yı hemen sıfırla
        self._is_running = False
        self._btn_stop_all.setVisible(False)
        self._btn_stop_all.setEnabled(True)
        self._btn_launch.setVisible(True)
        self._status_card.setVisible(False)
        self._set_all_steps("idle")
        self._error_card.hide_error()

        # Doğru kapatma sırası (arka planda):
        # 1. Tunnel → 2. Dashboard → 3. Port-forwards → 4. Minikube stop → [5. Docker]
        self._stop_worker = StopWorker(self.ops, choice, self)
        self._stop_worker.progress.connect(
            lambda msg: self._btn_launch.setText(f"⏳  {msg}")
        )
        self._stop_worker.done.connect(
            lambda: self._btn_launch.setText("▶   Başlat")
        )
        self._stop_worker.start()

    def _on_step_update(self, step: str, status: str):
        sub_map = {"running": "Başlatılıyor…", "ok": "Hazır", "error": "Hata"}
        sub = sub_map.get(status, "")
        mapping = {
            "docker":    self._step_docker,
            "cluster":   self._step_cluster,
            "dashboard": self._step_dashboard,
            "tunnel":    self._step_tunnel,
        }
        sw = mapping.get(step)
        if sw:
            sw.set_status(status, sub)
        # Adım başarıyla tamamlanınca hata kartını temizle
        if status == "ok":
            self._error_card.hide_error()

    def _on_error(self, step: str, title: str, desc: str):
        fix_labels = {
            "docker":    "🐳  Docker Desktop'u Aç",
            "cluster":   "📋  Activity Log'u Gör",
            "dashboard": "📋  Activity Log'u Gör",
            "tunnel":    "🔑  Tünel Ayarları",
        }
        self._fix_action = step
        # "warning" step'leri sarı göster (bloke edici değil)
        sw = {"docker": self._step_docker, "cluster": self._step_cluster,
              "dashboard": self._step_dashboard, "tunnel": self._step_tunnel}.get(step)
        is_warning = sw and sw._ICONS.get("warning") and title.startswith("Port") or "Henüz" in title
        self._error_card.show_error(title, desc, fix_labels.get(step, ""), warning=is_warning)

    def _on_url_ready(self, url: str):
        """ngrok URL hazır — Live modda çağrılır."""
        self._current_url = url
        self._url_icon.setText("🌐")
        self._url_main_lbl.setText(url)
        self._url_main_lbl.setStyleSheet(f"color:{C_ACCENT}; background:transparent; border:none;")
        self._ngrok_note.setVisible(True)
        self._status_card.setVisible(True)

    def _on_launch_done(self, ok: bool):
        if not ok:
            self._is_running = False
            self._btn_stop_all.setVisible(False)
            self._btn_launch.setVisible(True)
        else:
            # Port-forward watchdog: her 30sn'de port ölü mü kontrol et, ölüyse yeniden başlat
            self._pf_watchdog = QTimer(self)
            self._pf_watchdog.timeout.connect(self._check_port_forward)
            self._pf_watchdog.start(30000)

            # Local modda da URL kartını göster
            if self._mode == "local":
                port = int(self.ops.db.get_setting("active_project_port", "8080"))
                local_url = f"http://localhost:{port}"
                self._current_url = local_url
                self._url_icon.setText("🏠")
                self._url_main_lbl.setText(local_url)
                self._url_main_lbl.setStyleSheet(
                    f"color:{C_GREEN}; background:transparent; border:none;"
                )
                self._ngrok_note.setVisible(False)
                self._status_card.setVisible(True)

    def _copy_url(self):
        url = getattr(self, "_current_url", "")
        if url:
            QApplication.clipboard().setText(url)

    def _open_url(self):
        url = getattr(self, "_current_url", "")
        if url:
            webbrowser.open(url)

    def _on_fix_clicked(self):
        import subprocess as _sp
        if self._fix_action == "docker":
            # Docker Desktop'u bul ve başlat
            docker_paths = [
                r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
                str(Path.home() / "AppData" / "Local" / "Docker" / "Docker Desktop.exe"),
            ]
            started = False
            for dp in docker_paths:
                if Path(dp).exists():
                    try:
                        _sp.Popen([dp])
                        started = True
                        break
                    except Exception:
                        pass
            if not started:
                try:
                    _sp.Popen(["cmd", "/c", "start", "", "Docker Desktop.exe"])
                except Exception:
                    pass
        elif self._fix_action in ("cluster", "dashboard"):
            # Navigate to Activity Log panel — emit the old signal for MainWindow
            self.request_cluster_action.emit("_nav_activity")
        elif self._fix_action == "tunnel":
            self.request_cluster_action.emit("_nav_activity")  # Tunnel paneli yok → Aktivite'ye git

    # ── PUBLIC API (called by MainWindow) ─────────────────────────────────

    def update_metrics(self, data: dict):
        rps  = data.get("rps", 0.0)
        pods = data.get("pod_count", 0)
        for frame, key, val in [
            (self._stat_rps,  "rps",    f"{rps:.2f}"),
            (self._stat_pods, "podlar", str(pods)),
        ]:
            lbl = self._get_stat_label(frame, key)
            if lbl:
                lbl.setText(val)

    def update_hardware(self, data: dict):
        cpu = data.get("cpu_percent", 0)
        mem = data.get("memory_percent", 0)
        for frame, key, val in [
            (self._stat_cpu, "cpu", f"{cpu:.1f}%"),
            (self._stat_mem, "ram", f"{mem:.1f}%"),
        ]:
            lbl = self._get_stat_label(frame, key)
            if lbl:
                lbl.setText(val)

    def update_cluster_status(self, running: bool):
        # Update the cluster step widget to reflect external status changes
        if running and not self._is_running:
            self._step_cluster.set_status("ok", "Çalışıyor")
        elif not running and not self._is_running:
            self._step_cluster.set_status("idle")

    def refresh_activity(self):
        pass  # Activity moved to ActivityLog panel


# ─────────────────────────────────────────────
#  PANEL 2 — CLUSTER MANAGEMENT
# ─────────────────────────────────────────────
class ClusterPanel(QWidget):
    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db = db
        self.ops = ops
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Instance Info
        info_card = Card("Instance Information")
        info_body = info_card.body()
        self._info_lbl = QLabel("Loading...")
        self._info_lbl.setStyleSheet(f"color:{C_TEXT}; font-family:Consolas; font-size:12px;")
        info_body.addWidget(self._info_lbl)
        lay.addWidget(info_card)

        # Service Status
        svc_card = Card("Service Status")
        svc_body = svc_card.body()
        self._svc_rows = {}
        svcs = [("Prometheus", 9090), ("Pushgateway", 9091), ("App", 8080), ("Dashboard", 8501)]
        for name, port in svcs:
            row = QHBoxLayout()
            dot = StatusDot()
            lbl = QLabel(f"{name} (:{port})")
            lbl.setStyleSheet(f"color:{C_TEXT};")
            status_lbl = QLabel("Unknown")
            status_lbl.setStyleSheet(f"color:{C_TEXT_DIM};")
            open_btn = QPushButton("Open")
            open_btn.setFixedWidth(60)
            url = f"http://localhost:{port}"
            open_btn.clicked.connect(lambda checked, u=url: webbrowser.open(u))
            row.addWidget(dot)
            row.addSpacing(8)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(status_lbl)
            row.addWidget(open_btn)
            svc_body.addLayout(row)
            self._svc_rows[name.lower()] = (dot, status_lbl)
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self.refresh_services)
        svc_body.addWidget(refresh_btn)
        lay.addWidget(svc_card)

        # Port Forwards
        pf_card = Card("Port Forward Control")
        pf_body = pf_card.body()
        self._pf_status_lbl = QLabel("No port forwards active")
        self._pf_status_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px;")
        pf_btn_row = QHBoxLayout()
        btn_start_pf = QPushButton("Start Port Forwards")
        btn_start_pf.setObjectName("btn_primary")
        btn_start_pf.clicked.connect(self._start_pf)
        btn_stop_pf = QPushButton("Stop Port Forwards")
        btn_stop_pf.setObjectName("btn_danger")
        btn_stop_pf.clicked.connect(self._stop_pf)
        pf_btn_row.addWidget(btn_start_pf)
        pf_btn_row.addWidget(btn_stop_pf)
        pf_body.addWidget(self._pf_status_lbl)
        pf_body.addLayout(pf_btn_row)
        lay.addWidget(pf_card)

        # Scrape Config
        scrape_card = Card("Prometheus Scrape Config")
        scrape_body = scrape_card.body()
        self._scrape_log = LogWidget()
        self._scrape_log.setMaximumHeight(120)
        btn_apply_scrape = QPushButton("Apply / Refresh Scrape Config")
        btn_apply_scrape.setObjectName("btn_primary")
        btn_apply_scrape.clicked.connect(self._apply_scrape)
        scrape_body.addWidget(btn_apply_scrape)
        scrape_body.addWidget(self._scrape_log)
        lay.addWidget(scrape_card)

        # KEDA
        keda_card = Card("KEDA Autoscaling")
        keda_body = keda_card.body()
        self._keda_status_lbl = QLabel("Unknown")
        self._keda_status_lbl.setStyleSheet(f"color:{C_TEXT_DIM};")
        keda_btn_row = QHBoxLayout()
        btn_keda_on = QPushButton("Enable KEDA")
        btn_keda_on.setObjectName("btn_success")
        btn_keda_on.clicked.connect(lambda: self._toggle_keda(True))
        btn_keda_off = QPushButton("Disable KEDA")
        btn_keda_off.setObjectName("btn_danger")
        btn_keda_off.clicked.connect(lambda: self._toggle_keda(False))
        keda_btn_row.addWidget(btn_keda_on)
        keda_btn_row.addWidget(btn_keda_off)
        keda_body.addWidget(self._keda_status_lbl)
        keda_body.addLayout(keda_btn_row)
        lay.addWidget(keda_card)

        # Raw kubectl
        kubectl_card = Card("Raw kubectl Output")
        kubectl_body = kubectl_card.body()
        kubectl_row = QHBoxLayout()
        self._kubectl_combo = QComboBox()
        self._kubectl_combo.addItems(["get pods", "get services", "get events", "get scaledobject", "get deployments"])
        btn_run_kubectl = QPushButton("Run")
        btn_run_kubectl.setObjectName("btn_primary")
        btn_run_kubectl.clicked.connect(self._run_kubectl)
        kubectl_row.addWidget(self._kubectl_combo)
        kubectl_row.addWidget(btn_run_kubectl)
        self._kubectl_output = QTextEdit()
        self._kubectl_output.setReadOnly(True)
        self._kubectl_output.setFont(QFont("Consolas", 10))
        self._kubectl_output.setMaximumHeight(200)
        kubectl_body.addLayout(kubectl_row)
        kubectl_body.addWidget(self._kubectl_output)
        lay.addWidget(kubectl_card)

        lay.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_info()

    def refresh_info(self):
        instance = self.ops.get_instance()
        if instance:
            text = f"Instance ID:     {instance.get('instance_id', 'N/A')}\n"
            text += f"Namespace:       {instance.get('namespace', 'N/A')}\n"
            text += f"Minikube Profile: {instance.get('minikube_profile', 'N/A')}\n"
            text += f"Created:         {instance.get('created_at', 'N/A')[:19] if instance.get('created_at') else 'N/A'}"
        else:
            text = "No instance.json found. Run setup wizard first."
        self._info_lbl.setText(text)

    def refresh_services(self):
        def check():
            return self.ops.check_all_services()
        def done(svcs):
            svc_map = {
                "prometheus": "prometheus",
                "pushgateway": "pushgateway",
                "app": "app",
                "dashboard": "dashboard",
            }
            for key, (dot, lbl) in self._svc_rows.items():
                up = svcs.get(key, False)
                dot.set_color(C_GREEN if up else C_RED)
                lbl.setText("Running" if up else "Stopped")
                lbl.setStyleSheet(f"color:{''+C_GREEN if up else C_RED};")
        import threading
        threading.Thread(target=lambda: done(check()), daemon=True).start()

    def update_service(self, name: str, up: bool):
        row = self._svc_rows.get(name.lower())
        if row:
            dot, lbl = row
            dot.set_color(C_GREEN if up else C_RED)
            lbl.setText("Running" if up else "Stopped")

    def _start_pf(self):
        instance = self.ops.get_instance()
        if not instance:
            self._pf_status_lbl.setText("No instance found")
            return
        ns = instance.get("namespace", "autoscaleops")
        self.ops.start_port_forwards(ns)
        self._pf_status_lbl.setText(f"Port forwards started for namespace: {ns}")

    def _stop_pf(self):
        self.ops.stop_port_forwards()
        self._pf_status_lbl.setText("Port forwards stopped")

    def _apply_scrape(self):
        instance = self.ops.get_instance()
        if not instance:
            self._scrape_log.append_line("No instance found", "error")
            return
        ns = instance.get("namespace", "autoscaleops")
        self._scrape_log.append_line(f"Applying scrape config for namespace {ns}...", "info")
        def do():
            ok, out = self.ops.apply_scrape_config(ns)
            self._scrape_log.append_line(out[:300] if out else "Done", "ok" if ok else "error")
        import threading
        threading.Thread(target=do, daemon=True).start()

    def _toggle_keda(self, enable: bool):
        def do():
            ok, out = self.ops.toggle_keda(enable)
            state = "enabled" if enable else "disabled"
            self._keda_status_lbl.setText(f"KEDA {state}: {out[:100]}")
        import threading
        threading.Thread(target=do, daemon=True).start()

    def _run_kubectl(self):
        cmd = self._kubectl_combo.currentText()
        def do():
            ok, out = self.ops.run_kubectl(cmd)
            self._kubectl_output.setPlainText(out)
        import threading
        threading.Thread(target=do, daemon=True).start()


# ─────────────────────────────────────────────
#  PANEL 3 — HARDWARE MONITOR
# ─────────────────────────────────────────────
class SystemCheckWorker(QThread):
    """Arka planda sistem gereksinimlerini kontrol eder."""
    result = pyqtSignal(dict)

    def run(self):
        checks = {}

        # Docker Desktop
        try:
            r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                vr = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
                checks["docker"] = {"ok": True, "label": "Docker Desktop",
                                    "detail": vr.stdout.strip()[:60]}
            else:
                checks["docker"] = {"ok": False, "label": "Docker Desktop",
                                    "detail": "Çalışmıyor — Docker Desktop'ı başlatın"}
        except Exception:
            checks["docker"] = {"ok": False, "label": "Docker Desktop",
                                "detail": "Kurulu değil — indirip yükleyin"}

        # Minikube
        try:
            r = subprocess.run(["minikube", "version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                checks["minikube"] = {"ok": True, "label": "Minikube",
                                      "detail": r.stdout.strip().split("\n")[0][:60]}
            else:
                checks["minikube"] = {"ok": False, "label": "Minikube",
                                      "detail": "Kurulu değil"}
        except Exception:
            checks["minikube"] = {"ok": False, "label": "Minikube",
                                  "detail": "Kurulu değil — indirip yükleyin"}

        # kubectl  (--short deprecated yeni sürümlerde, birkaç yöntem dene)
        try:
            r = subprocess.run(["kubectl", "version", "--client"],
                               capture_output=True, text=True, timeout=10)
            combined = r.stdout + r.stderr
            ok = r.returncode == 0 or "Client Version" in combined or "clientVersion" in combined
            if ok:
                # İlk anlamlı satırı al
                first_line = combined.strip().split("\n")[0][:60]
                detail = first_line if first_line else "Kurulu"
            else:
                detail = "Kurulu değil"
            checks["kubectl"] = {"ok": ok, "label": "kubectl", "detail": detail}
        except Exception:
            checks["kubectl"] = {"ok": False, "label": "kubectl",
                                 "detail": "Kurulu değil — indirip yükleyin"}

        # ngrok — opsiyonel, ihtiyac olunca otomatik indirilir, bloklamaz
        ngrok_paths = ["ngrok", str(NGROK_EXE)]
        ngrok_ok = False
        ngrok_detail = "Otomatik indirilecek"
        for np in ngrok_paths:
            try:
                r = subprocess.run([np, "version"], capture_output=True, text=True, timeout=8)
                if r.returncode == 0:
                    ngrok_ok = True
                    ngrok_detail = r.stdout.strip()[:60]
                    break
            except Exception:
                continue
        # ngrok eksik olsa bile ok=True — kullanici Live Mode actigi anda indirilir
        checks["ngrok"] = {"ok": True, "label": "ngrok",
                           "detail": ngrok_detail if ngrok_ok else "Otomatik indirilecek (Live Mode)"}

        # Python paketleri — sadece GUI icin zorunlu olanlar kontrol edilir
        # streamlit/pmdarima gibi agir paketler buradan cikarildi (ihtiyac olunca kurulur)
        required = [
            ("PyQt6",             "PyQt6"),
            ("prometheus_client", "prometheus_client"),
            ("psutil",            "psutil"),
            ("requests",          "requests"),
            ("matplotlib",        "matplotlib"),
        ]
        missing = []
        for display_name, import_name in required:
            try:
                __import__(import_name)
            except ImportError:
                missing.append(display_name)
        if not missing:
            checks["python_deps"] = {"ok": True, "label": "Python Paketleri",
                                     "detail": "Tum paketler kurulu"}
        else:
            checks["python_deps"] = {"ok": False, "label": "Python Paketleri",
                                     "detail": f"Eksik: {', '.join(missing)}"}

        self.result.emit(checks)


# ─────────────────────────────────────────────
#  PANEL 3 — SİSTEM GEREKSİNİMLERİ
# ─────────────────────────────────────────────
class SystemPanel(QWidget):
    """Sistem gereksinimlerini kontrol eden panel."""

    _INSTALL_LINKS = {
        "docker":   "https://www.docker.com/products/docker-desktop/",
        "minikube": "https://minikube.sigs.k8s.io/docs/start/",
        "kubectl":  "https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/",
        "ngrok":    "https://ngrok.com/download",
    }

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._checks: dict = {}
        self._worker: Optional[SystemCheckWorker] = None
        self._card_widgets: list = []
        self._build_ui()
        QTimer.singleShot(300, self._run_check)

    # ── UI ────────────────────────────────────
    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(36, 36, 36, 36)
        lay.setSpacing(16)

        # ── Başlık
        hdr = QLabel("Sistem Gereksinimleri")
        hdr.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{C_TEXT};")
        sub = QLabel(
            "AutoScaleOps'un çalışması için aşağıdaki bileşenler gereklidir.\n"
            "Eksik olanları kurun, ardından 'Yeniden Kontrol Et'e basın."
        )
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        sub.setWordWrap(True)
        lay.addWidget(hdr)
        lay.addWidget(sub)
        lay.addSpacing(8)

        # ── Kart alanı
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background:transparent;")
        self._cards_lay = QVBoxLayout(self._cards_container)
        self._cards_lay.setSpacing(10)
        self._cards_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._cards_container)

        # ── Yükleniyor etiketi
        self._loading_lbl = QLabel("⏳  Kontrol ediliyor...")
        self._loading_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        lay.addWidget(self._loading_lbl)

        # ── Buton satırı
        btn_row = QHBoxLayout()
        self._btn_refresh = QPushButton("🔄   Yeniden Kontrol Et")
        self._btn_refresh.setFixedHeight(42)
        self._btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background:{C_SURFACE2}; color:{C_TEXT};
                border:1px solid {C_BORDER}; border-radius:12px;
                font-size:13px; padding:0 20px;
            }}
            QPushButton:hover {{ background:{C_HOVER}; }}
            QPushButton:disabled {{ color:{C_TEXT_DIM}; }}
        """)
        self._btn_refresh.clicked.connect(self._run_check)
        btn_row.addWidget(self._btn_refresh)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()

        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    # ── Kontrol ───────────────────────────────
    def _run_check(self):
        self._loading_lbl.setVisible(True)
        self._btn_refresh.setEnabled(False)
        # Eski kartları temizle
        for w in self._card_widgets:
            w.setParent(None)
            w.deleteLater()
        self._card_widgets.clear()

        self._worker = SystemCheckWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, checks: dict):
        self._checks = checks
        self._loading_lbl.setVisible(False)
        self._btn_refresh.setEnabled(True)
        for key, info in checks.items():
            card = self._build_card(key, info)
            self._cards_lay.addWidget(card)
            self._card_widgets.append(card)

    def _build_card(self, key: str, info: dict) -> QFrame:
        ok = info["ok"]
        bg     = "rgba(52,211,153,0.07)"  if ok else "rgba(248,113,113,0.07)"
        border = "rgba(52,211,153,0.25)"  if ok else "rgba(248,113,113,0.25)"

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background:{bg}; border:1px solid {border};
                border-radius:14px;
            }}
        """)
        row = QHBoxLayout(card)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(14)

        # İkon
        icon_lbl = QLabel("✅" if ok else "❌")
        icon_lbl.setFont(QFont("Segoe UI", 16))
        icon_lbl.setFixedWidth(28)
        icon_lbl.setStyleSheet("background:transparent; border:none;")

        # Metin
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_lbl = QLabel(info["label"])
        name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        detail_lbl = QLabel(info["detail"])
        detail_lbl.setStyleSheet(
            f"color:{'#34D399' if ok else C_TEXT_DIM}; font-size:11px;"
            " background:transparent; border:none;"
        )
        detail_lbl.setWordWrap(True)
        text_col.addWidget(name_lbl)
        text_col.addWidget(detail_lbl)

        row.addWidget(icon_lbl)
        row.addLayout(text_col, 1)

        # Aksiyon butonu (sadece hata durumunda)
        if not ok:
            if key == "python_deps":
                btn = QPushButton("📦  Kur")
                btn.setFixedSize(90, 34)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{C_ACCENT}; color:#0B0B18;
                        border-radius:10px; font-size:12px; font-weight:700;
                    }}
                    QPushButton:hover {{ background:{C_ACCENT2}; color:{C_TEXT}; }}
                """)
                btn.clicked.connect(self._install_python_deps)
                row.addWidget(btn)
            elif key in self._INSTALL_LINKS:
                btn = QPushButton("⬇  İndir")
                btn.setFixedSize(90, 34)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{C_SURFACE2}; color:{C_TEXT};
                        border:1px solid {C_BORDER}; border-radius:10px; font-size:12px;
                    }}
                    QPushButton:hover {{ background:{C_HOVER}; }}
                """)
                url = self._INSTALL_LINKS[key]
                btn.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))
                row.addWidget(btn)

        return card

    def _install_python_deps(self):
        req = Path(__file__).parent / "requirements.txt"
        req_d = Path(__file__).parent / "requirements_desktop.txt"
        cmds = []
        if req_d.exists():
            cmds.append(f"pip install -r \"{req_d}\"")
        if req.exists():
            cmds.append(f"pip install -r \"{req}\"")
        if not cmds:
            QMessageBox.warning(self, "Hata", "requirements.txt bulunamadı.")
            return
        full_cmd = " && ".join(cmds) + " && echo KURULUM TAMAMLANDI && pause"
        subprocess.Popen(["powershell", "-NoExit", "-Command", full_cmd])

    # ── Public API ────────────────────────────
    def all_ok(self) -> bool:
        return bool(self._checks) and all(v["ok"] for v in self._checks.values())

    def get_checks(self) -> dict:
        return self._checks


# ─────────────────────────────────────────────
#  PANEL 6.5 — ACTIVITY LOG
# ─────────────────────────────────────────────
class ActivityLogPanel(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._last_log_id = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(16)

        title = QLabel("Aktivite Logu")
        title.setStyleSheet(
            f"color:{C_TEXT}; font-size:20px; font-weight:700; background:transparent; border:none;"
        )
        sub = QLabel("Sistem olayları ve işlem geçmişi — otomatik yenilenir")
        sub.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;"
        )
        lay.addWidget(title)
        lay.addWidget(sub)

        self._log = LogWidget()
        self._log.setMinimumHeight(400)
        lay.addWidget(self._log, 1)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setFixedHeight(36)
        btn_refresh.setFixedWidth(100)
        btn_refresh.clicked.connect(self._force_reload)
        btn_clear = QPushButton("Logu Temizle")
        btn_clear.setFixedHeight(36)
        btn_clear.setFixedWidth(140)
        btn_clear.clicked.connect(self._clear_log)
        btn_row.addStretch()
        btn_row.addWidget(btn_refresh)
        btn_row.addWidget(btn_clear)
        lay.addLayout(btn_row)

        # DB'den ilk yükleme (UI hazır olduktan 200ms sonra)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self._load_from_db)
        # Her 4 saniyede otomatik yenile (yeni loglar gelince güncelle)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._load_from_db)
        self._refresh_timer.start(4000)

    def _load_from_db(self):
        """DB'deki yeni log kayıtlarını widget'a ekle."""
        try:
            entries = self.db.get_activity_log(limit=300)
            # id'ye göre büyükten küçüğe geliyor (ORDER BY id DESC);
            # sadece daha önce gösterilmeyenleri al
            new = [e for e in entries if e.get("id", 0) > self._last_log_id]
            if not new:
                return
            for entry in reversed(new):   # eskiden yeniye ekle
                ts    = (entry.get("timestamp") or "")[:19]
                etype = (entry.get("event_type") or "info").lower()
                desc  = (entry.get("description") or "").strip()
                if not desc:
                    continue
                if any(k in etype for k in ("error", "fail", "hata")):
                    level = "error"
                elif any(k in etype for k in ("deploy", "success", "start", "launch", "basalt")):
                    level = "success"
                else:
                    level = "info"
                self._log.append_line(f"[{ts}] [{etype.upper()}] {desc}", level)
                self._last_log_id = max(self._last_log_id, entry.get("id", 0))
        except Exception:
            pass

    def _force_reload(self):
        """Tüm logları sıfırdan yükle."""
        self._last_log_id = 0
        self._log.clear()
        self._load_from_db()

    def _clear_log(self):
        self._log.clear()
        self._last_log_id = 0

    def append_line(self, msg: str, level: str = "info"):
        self._log.append_line(msg, level)


# ─────────────────────────────────────────────
#  PANEL 7 — TROUBLESHOOTER
# ─────────────────────────────────────────────
class TroubleshooterPanel(QWidget):
    # signal to update diag list from worker thread
    _diag_ready = pyqtSignal(list)

    # ── issue definitions: (category, emoji, title, description, fix_action or None)
    _ISSUES = [
        # --- Kurulum ---
        ("🔧 Kurulum", "🐍",
         "Python stub (Microsoft Store) aktif",
         "python komutunu calistirinca Microsoft Store aciliyorsa App Execution Alias engelleniyor. "
         "Ayarlar > Uygulamalar > Uygulama yurutme takma adlari > python ve python3 kapali.",
         "disable_store_alias"),
        ("🔧 Kurulum", "🐳",
         "Docker Desktop kapali",
         "Docker Desktop baslatilmamis veya hata vermis. Minikube'un calisabilmesi icin Docker "
         "Desktop acik olmali. Asagida 'Otomatik Duzelt' ile Docker'i baslatmayi deneyin.",
         "start_docker"),
        ("🔧 Kurulum", "📦",
         "Python paketleri eksik",
         "PyQt6, kubernetes, statsmodels vb. paketler kurulu degil. "
         "requirements.txt yoksa autoscaleops_app.py'nin icinde import listesi mevcut.",
         "install_packages"),
        ("🔧 Kurulum", "🛠️",
         "Minikube veya kubectl bulunamadi",
         "PATH'te minikube veya kubectl yok. fix.ps1 calistirarak gerekli araclari otomatik indir "
         "ve kur. Gereksinim: Windows 10/11, 8 GB RAM, 30 GB bos disk.",
         "run_fixps1"),

        # --- Cluster ---
        ("☸️ Cluster", "💾",
         "Yetersiz kaynak (RAM / disk)",
         "Minikube en az 6 GB RAM ve 20 GB bos disk gerektirir. Gorevin Yoneticisi'nde bellek "
         "kullanimini kontrol edin; gereksiz programlari kapatin.",
         None),
        ("☸️ Cluster", "🏷️",
         "Namespace eksik",
         "'autoscaleops' veya 'monitoring' namespace bulunamadi. Cluster yeniden olusturulurken "
         "namespace'ler silinmis olabilir.",
         "create_namespaces"),
        ("☸️ Cluster", "🔌",
         "Port forward baglantilar kesildi",
         "Port forward islemleri oldurulmus ya da zaman asimina ugramis. Uygulama ile cluster "
         "arasindaki 8080/9090 portlari yeniden yonlendir.",
         "restart_pf"),
        ("☸️ Cluster", "🔖",
         "Eski hash tabanli Minikube profili",
         "Onceki surumde profil adi 'minikube-XXXX' gibi hash ile olusturuluyordu. Simdiki "
         "surumde profil adi sabit: 'autoscaleops'. Eski profili silin.",
         "delete_old_profiles"),

        # --- Uygulama ---
        ("📊 Uygulama", "📉",
         "Trafik 0 RPS gosteriyor",
         "Prometheus henuz metrikleri toplamaya baslamadi. Scrape yapilandirmasi uygulanmamis "
         "olabilir. 'Otomatik Duzelt' ile Prometheus scrape config yeniden uygulayabilirsiniz.",
         "apply_scrape"),
        ("📊 Uygulama", "🖥️",
         "Dashboard acilmiyor",
         "Streamlit dashboard sureci durmus. Loglari kontrol etmek icin Activity Log paneline "
         "bakin. Dashboard yeniden baslatmak icin 'Otomatik Duzelt' kullanin.",
         "start_dashboard"),
        ("📊 Uygulama", "📡",
         "Prometheus metrikleri gelmiyor",
         "Prometheus'un 9090 portu erisim vermiyor. Port forward yuklu degilse "
         "Prometheus sorgulari bos donerken gorulur.",
         "fwd_prometheus"),
        ("📊 Uygulama", "⚖️",
         "KEDA pod olceklendirmiyor",
         "ScaledObject kaynak eksik ya da Prometheus trigger dogru ayarlanmamis. "
         "kubectl get scaledobject -n autoscaleops calistirilarak kaynak varligini dogrulayin.",
         "check_keda"),

        # --- Performans ---
        ("⚡ Performans", "❄️",
         "Ilk istek cok yavas (cold-start)",
         "Minikube ilk basladiginda JVM / Python worker'lari henuz hazir degil. "
         "1-2 dakika bekleyin ya da is yuku gondermeye baslayip ilk sonuclari goz ardi edin.",
         None),
        ("⚡ Performans", "⏱️",
         "Yuksek gecikme (>200 ms p95)",
         "CPU talebini azaltin veya Minikube kaynak limitini artirin: "
         "minikube config set memory 8192 && minikube config set cpus 4. "
         "ARIMA tahmin ufkunu kisaltarak erken olceklendirme yapilabilir.",
         None),
        ("⚡ Performans", "🔄",
         "Sifirdan basla (tam yeniden kurulum)",
         "Hic bir yontem calismiyorsa clusteri tamamen silip yeniden kurun. "
         "Bu islem 5-10 dakika surer, tum veriler silinir.",
         "full_reinstall"),
    ]

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db = db
        self.ops = ops
        self._diag_results = []
        self._diag_ready.connect(self._populate_diag_results)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(20)

        # ── Baslik
        hdr = QLabel("Sorun Giderici")
        hdr.setStyleSheet(f"color:{C_TEXT}; font-size:20px; font-weight:bold;")
        sub = QLabel("Kendi kendinize sorunlari tespit edin ve otomatik duzeltmeleri uygulayin.")
        sub.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px;")
        lay.addWidget(hdr)
        lay.addWidget(sub)

        # ── Hizli tani + otomatik duzelt butonlari
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_run_diag = QPushButton("🔍  Tam Tani Calistir")
        self._btn_run_diag.setObjectName("btn_primary")
        self._btn_run_diag.setFixedHeight(40)
        self._btn_run_diag.clicked.connect(self._run_diagnostics)

        self._btn_fix_all = QPushButton("🚀  Tüm Hataları Düzelt")
        self._btn_fix_all.setObjectName("btn_success")
        self._btn_fix_all.setFixedHeight(40)
        self._btn_fix_all.clicked.connect(self._auto_fix_all)

        btn_export = QPushButton("📄  Rapor Aktar")
        btn_export.setFixedHeight(40)
        btn_export.clicked.connect(self._export_report)

        btn_row.addWidget(self._btn_run_diag)
        btn_row.addWidget(self._btn_fix_all)
        btn_row.addWidget(btn_export)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # ── Tani sonuclari alani
        self._diag_card = Card("Tani Sonuclari")
        self._diag_list = self._diag_card.body()
        self._diag_list.setSpacing(6)
        _placeholder = QLabel("Henuz tani calistirilmadi. 'Tam Tani Calistir' butonuna basin.")
        _placeholder.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px;")
        self._diag_list.addWidget(_placeholder)
        self._diag_placeholder = _placeholder
        lay.addWidget(self._diag_card)

        # ── Kategorilere gore bilinen sorunlar
        categories = {}
        for issue in self._ISSUES:
            cat = issue[0]
            categories.setdefault(cat, []).append(issue)

        for cat_name, issues in categories.items():
            cat_card = Card(cat_name)
            cb = cat_card.body()
            cb.setSpacing(8)
            for issue in issues:
                cb.addWidget(self._make_issue_row(issue))
            lay.addWidget(cat_card)

        lay.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Sorun satiri olustur
    def _make_issue_row(self, issue: tuple) -> QFrame:
        _cat, emoji, title, desc, fix_action = issue
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE2}; border:1px solid {C_BORDER}; "
            f"border-radius:10px; }} "
            f"QFrame:hover {{ border-color: rgba(99,102,241,0.45); }}"
        )
        fl = QVBoxLayout(f)
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(6)

        top = QHBoxLayout()
        icon_lbl = QLabel(emoji)
        icon_lbl.setStyleSheet("font-size:18px;")
        icon_lbl.setFixedWidth(28)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color:{C_TEXT}; font-weight:bold; font-size:13px;")
        top.addWidget(icon_lbl)
        top.addWidget(title_lbl)
        top.addStretch()

        if fix_action:
            fix_btn = QPushButton("Otomatik Duzelt")
            fix_btn.setObjectName("btn_warning")
            fix_btn.setFixedHeight(30)
            fix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            fix_btn.clicked.connect(lambda checked, a=fix_action: self._do_fix(a))
            top.addWidget(fix_btn)

        fl.addLayout(top)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px;")
        desc_lbl.setWordWrap(True)
        fl.addWidget(desc_lbl)
        return f

    # ── Otomatik duzeltme aksiyonlari
    def _do_fix(self, action: str):
        def _toast(msg: str):
            QMessageBox.information(self, "Otomatik Duzelt", msg)

        if action == "apply_scrape":
            instance = self.ops.get_instance()
            if instance:
                import threading
                threading.Thread(
                    target=lambda: self.ops.apply_scrape_config(instance["namespace"]),
                    daemon=True
                ).start()
                _toast("Prometheus scrape yapilandirmasi uygulanıyor...")
            else:
                _toast("Aktif cluster bulunamadi.")

        elif action == "start_dashboard":
            self.ops.start_dashboard()
            _toast("Dashboard baslatiliyor...")

        elif action == "restart_pf":
            instance = self.ops.get_instance()
            if instance:
                self.ops.start_port_forwards(instance["namespace"])
                _toast("Port forward'lar yeniden baslatildi.")
            else:
                _toast("Aktif cluster bulunamadi.")

        elif action == "start_docker":
            import threading
            def _start():
                import subprocess, time
                paths = [
                    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                ]
                import os
                local = os.environ.get("LOCALAPPDATA", "")
                if local:
                    paths.append(os.path.join(local, "Docker", "Docker Desktop.exe"))
                exe = next((p for p in paths if os.path.exists(p)), None)
                if exe:
                    subprocess.Popen([exe])
            threading.Thread(target=_start, daemon=True).start()
            _toast("Docker Desktop baslatiliyor. Hazir olmasini bekleyin (yaklasik 30 sn).")

        elif action == "install_packages":
            cmd = "pip install PyQt6 kubernetes statsmodels requests prometheus_client"
            self._show_fix(cmd)

        elif action == "run_fixps1":
            self._show_fix("powershell -ExecutionPolicy Bypass -File fix.ps1")

        elif action == "disable_store_alias":
            _toast(
                "Windows Ayarlari'ni acin:\n"
                "Uygulamalar > Uygulamalar ve ozellikler > Uygulama yurutme takma adlari\n"
                "'python.exe' ve 'python3.exe' satirlarini kapali konuma getirin."
            )

        elif action == "create_namespaces":
            cmd = (
                "kubectl create namespace autoscaleops --dry-run=client -o yaml | kubectl apply -f -\n"
                "kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -\n"
                "kubectl create namespace keda --dry-run=client -o yaml | kubectl apply -f -"
            )
            self._show_fix(cmd)

        elif action == "delete_old_profiles":
            cmd = (
                "# Eski profilleri listele\n"
                "minikube profile list\n\n"
                "# 'autoscaleops' dismindaki profilleri sil (profil adini degistirin)\n"
                "minikube delete -p <eski_profil_adi>"
            )
            self._show_fix(cmd)

        elif action == "fwd_prometheus":
            cmd = "kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring"
            self._show_fix(cmd)

        elif action == "check_keda":
            cmd = (
                "kubectl get scaledobject -n autoscaleops\n"
                "kubectl describe scaledobject autoscaleops-scaledobject -n autoscaleops\n"
                "kubectl get pods -n keda"
            )
            self._show_fix(cmd)

        elif action == "full_reinstall":
            reply = QMessageBox.question(
                self, "Sifirdan Basla",
                "Bu islem clusteri tamamen silecek ve yeniden kuracak.\n"
                "Tum veriler kaybolacak. Devam etmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                cmd = (
                    "minikube delete -p autoscaleops\n"
                    "powershell -ExecutionPolicy Bypass -File fix.ps1"
                )
                self._show_fix(cmd)

    def _run_diagnostics(self):
        # Clear and show loading
        while self._diag_list.count():
            item = self._diag_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._diag_placeholder = None
        loading = QLabel("⏳  Tani calistiriliyor...")
        loading.setStyleSheet(f"color:{C_ACCENT}; font-size:13px;")
        self._diag_list.addWidget(loading)
        self._btn_run_diag.setEnabled(False)
        self._btn_run_diag.setText("⏳  Calistiriliyor...")

        def do():
            results = self.ops.run_diagnostics()
            self._diag_ready.emit(results)

        import threading
        threading.Thread(target=do, daemon=True).start()

    @pyqtSlot(list)
    def _populate_diag_results(self, results: list):
        self._diag_results = results
        while self._diag_list.count():
            item = self._diag_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if results:
            for res in results:
                self._diag_list.addWidget(self._make_diag_row(res))
        else:
            no_res = QLabel("Tani tamamlandi ama sonuc donmedi.")
            no_res.setStyleSheet(f"color:{C_TEXT_DIM};")
            self._diag_list.addWidget(no_res)
        self._btn_run_diag.setEnabled(True)
        self._btn_run_diag.setText("🔍  Tam Tani Calistir")

    def _make_diag_row(self, res: dict) -> QFrame:
        f = QFrame()
        status = res.get("status", "ok")
        colors = {"ok": C_GREEN, "warn": C_YELLOW, "error": C_RED}
        color = colors.get(status, C_TEXT)
        f.setStyleSheet(
            f"background:{C_SURFACE2}; border:1px solid {C_BORDER}; "
            f"border-left:3px solid {color}; border-radius:8px;"
        )
        fl = QVBoxLayout(f)
        fl.setContentsMargins(16, 8, 16, 8)
        fl.setSpacing(4)
        top_row = QHBoxLayout()
        badge = {"ok": "✅ TAMAM", "warn": "⚠️ UYARI", "error": "❌ HATA"}.get(status, "?")
        badge_lbl = QLabel(badge)
        badge_lbl.setStyleSheet(
            f"color:{color}; font-weight:bold; font-size:11px; min-width:72px;"
        )
        check_lbl = QLabel(res.get("check", ""))
        check_lbl.setStyleSheet(f"color:{C_TEXT}; font-weight:bold; font-size:13px;")
        top_row.addWidget(badge_lbl)
        top_row.addWidget(check_lbl)
        top_row.addStretch()
        _result_lbl = None
        if status in ("warn", "error") and res.get("fix"):
            fix_btn = QPushButton("⚡ Duzelt")
            fix_btn.setObjectName("btn_warning")
            fix_btn.setFixedHeight(28)
            fix_btn.setMinimumWidth(90)
            _result_lbl = QLabel("")
            _result_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
            _result_lbl.setWordWrap(True)
            fix_btn.clicked.connect(
                lambda checked, r=res, b=fix_btn, rl=_result_lbl: self._direct_fix(r, b, rl)
            )
            top_row.addWidget(fix_btn)
        fl.addLayout(top_row)
        msg_lbl = QLabel(res.get("message", ""))
        msg_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px;")
        msg_lbl.setWordWrap(True)
        fl.addWidget(msg_lbl)
        if _result_lbl is not None:
            fl.addWidget(_result_lbl)
        return f

    # ── Direkt Otomatik Düzeltme ──────────────────────────────────────────────

    def _direct_fix(self, res: dict, btn: "QPushButton", result_lbl=None):
        """Dialog açmadan arka planda fix uygular; butonu ve sonuç etiketini günceller."""
        fix_cmd    = res.get("fix", "")
        check_name = res.get("check", "")
        btn.setEnabled(False)
        btn.setText("⏳")
        if result_lbl:
            result_lbl.setText("⏳ Düzeltme uygulanıyor…")

        def worker():
            ok, out = False, ""
            try:
                inst = self.ops.get_instance()
                ns   = inst.get("namespace", "autoscaleops") if inst else "autoscaleops"

                if any(k in check_name for k in ("App (localhost:8080)", "Port Forwards")):
                    # Kırık eski process'leri ZORLA öldür → temiz başlat
                    self.ops.stop_port_forwards()
                    import time; time.sleep(1.5)   # OS portları serbest bıraksın
                    self.ops.start_port_forwards(ns)
                    # Port açılana kadar bekle (max 12 sn)
                    app_port = int(self.ops.db.get_setting("active_project_port", "8080"))
                    ok = self.ops._wait_for_port(app_port, timeout=12)
                    if ok:
                        ok  = self.ops.check_app()
                        out = f"Port-forward başarıyla yeniden başlatıldı ✓ (:{app_port})"
                    else:
                        out = (f"Port-forward başlatılamadı — "
                               f"kubectl port-forward svc çıkışını kontrol edin")

                elif "Prometheus (" in check_name:
                    self.ops.stop_port_forwards()
                    import time; time.sleep(1.5)
                    self.ops.start_port_forwards(ns)
                    ok  = self.ops._wait_for_port(9090, timeout=12)
                    if ok: ok = self.ops.check_prometheus()
                    out = "Prometheus port-forward hazır ✓" if ok else "Prometheus'a erişilemiyor"

                elif "Pushgateway" in check_name:
                    self.ops.stop_port_forwards()
                    import time; time.sleep(1.5)
                    self.ops.start_port_forwards(ns)
                    ok  = self.ops._wait_for_port(9091, timeout=12)
                    if ok: ok = self.ops.check_pushgateway()
                    out = "Pushgateway port-forward hazır ✓" if ok else "Pushgateway'e erişilemiyor"

                elif "Scraping" in check_name:
                    proj = self.db.get_active_project()
                    proj_name = proj["name"] if proj and proj.get("name") else "app"
                    self.ops.apply_scrape_config(ns, proj_name)
                    ok  = True
                    out = "ServiceMonitor oluşturuldu ✓"

                elif fix_cmd and not any(fix_cmd.startswith(t) for t in (
                        "Close", "Free", "Ensure", "Run setup", "Start Docker")):
                    ok, out = run_ps(fix_cmd, timeout=60)
                    if not out.strip():
                        out = "Komut çalıştırıldı"

                else:
                    ok  = False
                    out = "Bu hata otomatik düzeltilemez — lütfen manuel müdahale edin."

            except Exception as exc:
                ok, out = False, str(exc)

            from PyQt6.QtCore import QTimer as _QT
            _QT.singleShot(0, lambda: self._fix_done(btn, ok, out, result_lbl))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot()
    def _fix_done(self, btn: "QPushButton", ok: bool, msg: str, result_lbl=None):
        btn.setEnabled(True)
        if ok:
            btn.setText("✅ Düzeltildi")
            btn.setStyleSheet(
                "background:#1a3a2a; color:#30D158; border:1px solid #30D158;"
                " border-radius:4px; padding:0 8px;"
            )
            if result_lbl:
                result_lbl.setText(f"✅ {msg}")
                result_lbl.setStyleSheet(f"color:#30D158; font-size:11px; padding-left:6px;")
        else:
            btn.setText("❌ Başarısız")
            btn.setToolTip(msg[:300])
            btn.setStyleSheet(
                "background:#3a1a1a; color:#FF453A; border:1px solid #FF453A;"
                " border-radius:4px; padding:0 8px;"
            )
            if result_lbl:
                result_lbl.setText(f"❌ {msg[:180]}")
                result_lbl.setStyleSheet(f"color:#FF453A; font-size:11px; padding-left:6px;")

    # ── Tüm Hataları Düzelt ──────────────────────────────────────────────────

    def _auto_fix_all(self):
        """Tüm HATA / UYARI satırlarını sırayla düzeltir."""
        errors = [r for r in self._diag_results if r.get("status") in ("error", "warn")]
        if not errors:
            QMessageBox.information(self, "Bilgi", "Düzeltilecek hata bulunamadı.\n"
                                    "Önce 'Tam Tanı Çalıştır' butonuna basın.")
            return

        self._btn_fix_all.setEnabled(False)
        self._btn_fix_all.setText(f"⏳  0/{len(errors)} düzeltiliyor…")

        def worker():
            inst     = self.ops.get_instance()
            ns       = inst.get("namespace", "autoscaleops") if inst else "autoscaleops"
            _pf_done = False  # port-forward bir kez başlatılsın yeter

            for i, res in enumerate(errors):
                from PyQt6.QtCore import QTimer as _QT
                idx = i
                _QT.singleShot(0, lambda _i=idx: self._btn_fix_all.setText(
                    f"⏳  {_i + 1}/{len(errors)} düzeltiliyor…"
                ))

                fix_cmd    = res.get("fix", "")
                check_name = res.get("check", "")
                try:
                    import time
                    if any(k in check_name for k in
                           ("App (localhost:8080)", "Port Forwards", "Prometheus (", "Pushgateway")):
                        if not _pf_done:
                            # Kırık process'leri temizle, temiz başlat
                            self.ops.stop_port_forwards()
                            time.sleep(1.5)
                            self.ops.start_port_forwards(ns)
                            # Port açılana kadar bekle
                            self.ops._wait_for_port(
                                int(self.ops.db.get_setting("active_project_port", "8080")),
                                timeout=12
                            )
                            _pf_done = True

                    elif "Scraping" in check_name:
                        proj = self.db.get_active_project()
                        proj_name = proj["name"] if proj and proj.get("name") else "app"
                        self.ops.apply_scrape_config(ns, proj_name)

                    elif "Minikube" in check_name:
                        profile = inst.get("minikube_profile", "autoscaleops") if inst else "autoscaleops"
                        run_ps(f"minikube start -p {profile} --driver=docker", timeout=180)

                    elif fix_cmd and not any(fix_cmd.startswith(t) for t in (
                            "Close", "Free", "Ensure", "Run setup", "Start Docker")):
                        run_ps(fix_cmd, timeout=60)

                except Exception:
                    pass

            from PyQt6.QtCore import QTimer as _QT
            _QT.singleShot(0, self._fix_all_done)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot()
    def _fix_all_done(self):
        self._btn_fix_all.setEnabled(True)
        self._btn_fix_all.setText("🚀  Tüm Hataları Düzelt")
        # Tanıyı yeniden çalıştır
        self._run_diagnostics()

    # ─────────────────────────────────────────────────────────────────────────

    def _show_fix(self, fix: str):
        dlg = QDialog(self)
        dlg.setWindowTitle("Komut Calistir")
        dlg.setFixedSize(560, 320)
        dlg.setStyleSheet(STYLESHEET)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)
        lbl = QLabel("Onerilern duzeltme komutu:")
        lbl.setStyleSheet(f"color:{C_TEXT}; font-weight:bold;")
        lay.addWidget(lbl)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Consolas", 10))
        text.setPlainText(fix)
        lay.addWidget(text)
        btn_run = QPushButton("▶  Komutu Calistir")
        btn_run.setObjectName("btn_primary")
        btn_result = QLabel("")
        btn_result.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        btn_result.setWordWrap(True)
        def run_fix():
            btn_run.setEnabled(False)
            btn_run.setText("⏳  Calistiriliyor...")
            ok, out = run_ps(fix, timeout=60)
            status_str = "✅ Tamam" if ok else "❌ Hata"
            btn_result.setText(f"{status_str}: {out[:300]}")
            btn_run.setEnabled(True)
            btn_run.setText("▶  Komutu Calistir")
        btn_run.clicked.connect(run_fix)
        lay.addWidget(btn_run)
        lay.addWidget(btn_result)
        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(dlg.reject)
        lay.addWidget(close_box)
        dlg.exec()

    def _export_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Tani Raporunu Aktar", "autoscaleops_tani.txt", "Text Files (*.txt)"
        )
        if not path:
            return
        try:
            lines = [
                "AutoScaleOps Tani Raporu",
                f"Olusturulma: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Uygulama Surumu: {APP_VERSION}",
                "=" * 60,
                "",
            ]
            if self._diag_results:
                lines.append("TANI KONTROLLERI:")
                for res in self._diag_results:
                    badge = {"ok": "TAMAM", "warn": "UYARI", "error": "HATA"}.get(
                        res.get("status", ""), res.get("status", "").upper()
                    )
                    lines.append(f"  [{badge:5}] {res.get('check','')}: {res.get('message','')}")
                    if res.get("fix"):
                        lines.append(f"         Duzeltme: {res['fix']}")
            else:
                lines.append("Tani sonucu bulunamadi. Once 'Tam Tani Calistir' butonuna basin.")
            lines.append("")
            lines.append("SON AKTIVITELER:")
            logs = self.db.get_activity_log(limit=20)
            for entry in logs:
                lines.append(
                    f"  {entry.get('timestamp','')[:19]} "
                    f"[{entry.get('event_type','')}] {entry.get('description','')}"
                )
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            QMessageBox.information(self, "Aktar", f"Rapor kaydedildi:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Aktarma Hatasi", str(e))


# ─────────────────────────────────────────────
#  PANEL 8 — SETTINGS
# ─────────────────────────────────────────────
class SettingsPanel(QWidget):
    language_changed = pyqtSignal(str)   # "tr" veya "en" yayınlar

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db = db
        self.ops = ops
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # ── Başlık
        hdr = QLabel(t("settings.title"))
        hdr.setStyleSheet(f"color:{C_TEXT}; font-size:20px; font-weight:bold;")
        lay.addWidget(hdr)

        # ── Tercihler kartı
        pref_card = Card(t("settings.preferences"))
        pref_b = pref_card.body()
        self._startup_chk = QCheckBox(t("settings.startup"))
        self._startup_chk.setChecked(ops.get_windows_startup())
        self._startup_chk.toggled.connect(lambda v: ops.set_windows_startup(v))
        self._tray_chk = QCheckBox(t("settings.tray"))
        self._tray_chk.setChecked(db.get_setting("minimize_to_tray", "true") == "true")
        self._tray_chk.toggled.connect(lambda v: db.set_setting("minimize_to_tray", str(v).lower()))
        refresh_row = QHBoxLayout()
        self._refresh_lbl = QLabel(t("settings.refresh"))
        self._refresh_combo = QComboBox()
        self._refresh_combo.addItems(["5s", "10s", "30s", "60s"])
        saved_interval = db.get_setting("auto_refresh_interval", "5s")
        idx = self._refresh_combo.findText(saved_interval)
        if idx >= 0:
            self._refresh_combo.setCurrentIndex(idx)
        self._refresh_combo.currentTextChanged.connect(lambda v: db.set_setting("auto_refresh_interval", v))
        refresh_row.addWidget(self._refresh_lbl)
        refresh_row.addWidget(self._refresh_combo)
        refresh_row.addStretch()
        self._notif_chk = QCheckBox(t("settings.notif"))
        self._notif_chk.setChecked(db.get_setting("notifications_enabled", "true") == "true")
        self._notif_chk.toggled.connect(lambda v: db.set_setting("notifications_enabled", str(v).lower()))
        pref_b.addWidget(self._startup_chk)
        pref_b.addWidget(self._tray_chk)
        pref_b.addLayout(refresh_row)
        pref_b.addWidget(self._notif_chk)
        lay.addWidget(pref_card)

        # ── Dil / Language kartı
        lang_card = Card(t("settings.language").rstrip(":"))
        lb = lang_card.body()
        lang_row = QHBoxLayout()
        lang_lbl = QLabel(t("settings.language"))
        lang_lbl.setStyleSheet(f"color:{C_TEXT};")
        self._lang_combo = QComboBox()
        self._lang_combo.addItem(t("settings.lang_tr"), "tr")
        self._lang_combo.addItem(t("settings.lang_en"), "en")
        saved_lang = db.get_setting("language", "tr")
        li = self._lang_combo.findData(saved_lang)
        if li >= 0:
            self._lang_combo.setCurrentIndex(li)
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        lang_row.addWidget(lang_lbl)
        lang_row.addWidget(self._lang_combo)
        lang_row.addStretch()
        lb.addLayout(lang_row)
        lang_note = QLabel("⚠  Tam etki için uygulamayı yeniden başlatın / Restart app for full effect.")
        lang_note.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        lang_note.setWordWrap(True)
        lb.addWidget(lang_note)
        lay.addWidget(lang_card)

        # ── KEDA & Ölçekleme Ayarları ──────────────────────────────────────
        keda_card = Card("KEDA & Olcekleme Ayarlari")
        kb = keda_card.body()

        keda_info = QLabel(
            "Pod basina dusen RPS esigini belirleyin. Ornek: esik=50 ve tahmin=100 → 2 pod."
        )
        keda_info.setWordWrap(True)
        keda_info.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        kb.addWidget(keda_info)

        keda_form = QHBoxLayout()

        # RPS Eşiği
        keda_form.addWidget(QLabel("Pod basina RPS esigi:"))
        self._keda_threshold = QSpinBox()
        self._keda_threshold.setRange(1, 10000)
        self._keda_threshold.setValue(int(db.get_setting("keda_rps_threshold", "50")))
        self._keda_threshold.setFixedWidth(90)
        self._keda_threshold.setToolTip("Bir pod'un kaldirabilecegi maksimum RPS")
        keda_form.addWidget(self._keda_threshold)
        keda_form.addSpacing(20)

        # Min Pod
        keda_form.addWidget(QLabel("Min pod:"))
        self._keda_min = QSpinBox()
        self._keda_min.setRange(0, 20)
        self._keda_min.setValue(int(db.get_setting("keda_min_pods", "1")))
        self._keda_min.setFixedWidth(60)
        keda_form.addWidget(self._keda_min)
        keda_form.addSpacing(20)

        # Max Pod
        keda_form.addWidget(QLabel("Max pod:"))
        self._keda_max = QSpinBox()
        self._keda_max.setRange(1, 100)
        self._keda_max.setValue(int(db.get_setting("keda_max_pods", "10")))
        self._keda_max.setFixedWidth(60)
        keda_form.addWidget(self._keda_max)
        keda_form.addStretch()
        kb.addLayout(keda_form)

        btn_save_keda = QPushButton("Kaydet")
        btn_save_keda.setFixedHeight(32)
        btn_save_keda.clicked.connect(self._save_keda_settings)
        kb.addWidget(btn_save_keda)
        lay.addWidget(keda_card)

        # ── Hakkında kartı
        about_card = Card(t("settings.about"))
        ab = about_card.body()
        instance = ops.get_instance()
        inst_id = instance.get("instance_id", "N/A") if instance else "N/A"
        ns = instance.get("namespace", "N/A") if instance else "N/A"
        self._about_lbl = QLabel(
            f"Version: {APP_VERSION}\n"
            f"Instance ID: {inst_id}\n"
            f"Namespace: {ns}"
        )
        self._about_lbl.setStyleSheet(f"color:{C_TEXT}; font-family:Consolas; font-size:12px;")
        self._about_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        about_btn_row = QHBoxLayout()
        btn_docs = QPushButton(t("settings.docs"))
        btn_docs.clicked.connect(lambda: webbrowser.open("https://github.com/Fknorl/AutoScaleOps"))
        btn_open_folder = QPushButton(t("settings.open_folder"))
        btn_open_folder.clicked.connect(lambda: run_ps(f"explorer {APP_DIR}"))
        btn_check_updates = QPushButton(t("settings.check_updates"))
        btn_check_updates.clicked.connect(lambda: webbrowser.open("https://github.com/Fknorl/AutoScaleOps/releases"))
        about_btn_row.addWidget(btn_docs)
        about_btn_row.addWidget(btn_open_folder)
        about_btn_row.addWidget(btn_check_updates)
        about_btn_row.addStretch()
        ab.addWidget(self._about_lbl)
        ab.addLayout(about_btn_row)
        lay.addWidget(about_card)

        lay.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _save_keda_settings(self):
        threshold = str(self._keda_threshold.value())
        min_pods  = str(self._keda_min.value())
        max_pods  = str(self._keda_max.value())
        self.db.set_setting("keda_rps_threshold", threshold)
        self.db.set_setting("keda_min_pods",      min_pods)
        self.db.set_setting("keda_max_pods",      max_pods)
        QMessageBox.information(
            self, "Kaydedildi",
            f"KEDA ayarlari kaydedildi.\n"
            f"Esik: {threshold} RPS/pod | Min: {min_pods} | Max: {max_pods}\n\n"
            f"Yeni deploy'larda bu degerler kullanilacak.\n"
            f"Mevcut ScaledObject icin kubectl patch gerekebilir."
        )

    def _on_lang_changed(self, index: int):
        global _APP_LANG
        lang_code = self._lang_combo.itemData(index)
        if not lang_code:
            return
        _APP_LANG = lang_code
        self.db.set_setting("language", lang_code)
        self.language_changed.emit(lang_code)
        QMessageBox.information(
            self,
            t("settings.title"),
            t("settings.restart_notice")
        )

    def load_user(self):
        pass  # Profil kaldırıldı — no-op




# ─────────────────────────────────────────────
#  DASHBOARD PANEL
# ─────────────────────────────────────────────
class DashboardPanel(QWidget):
    """Gerçek zamanlı metrik dashboard.
    QTimer ile 5 sn'de bir otomatik güncellenir — tam panel yenileme yok,
    sadece veri güncellenir (draw_idle + label setText).
    """
    PROM_URL = "http://127.0.0.1:9090/api/v1/query"
    PROM_RANGE_URL = "http://127.0.0.1:9090/api/v1/query_range"
    COST_PER_POD_HOUR = 0.04

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db  = db
        self.ops = ops
        self._hist_ts:   list[str]   = []
        self._hist_rps:  list[float] = []
        self._hist_pred: list[float] = []
        self._MAX_PTS = 72          # 6 dk @ 5 sn
        self._has_mpl = False
        self._fill = None
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)
        QTimer.singleShot(1200, self._refresh)

    # ── UI ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        self._live_dot = QLabel("⬤  CANLI")
        self._live_dot.setStyleSheet(
            f"color:{C_GREEN}; font-size:10px; font-weight:600; background:transparent; border:none;"
        )
        self._upd_lbl = QLabel("—")
        self._upd_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; background:transparent; border:none;")
        btn_rf = QPushButton("↻")
        btn_rf.setFixedSize(34, 34)
        btn_rf.setToolTip("Şimdi yenile")
        btn_rf.clicked.connect(self._refresh)
        hdr.addWidget(title)
        hdr.addSpacing(10)
        hdr.addWidget(self._live_dot)
        hdr.addSpacing(8)
        hdr.addWidget(self._upd_lbl)
        hdr.addStretch()
        hdr.addWidget(btn_rf)
        lay.addLayout(hdr)

        # ── Metric cards
        mc_row = QHBoxLayout()
        mc_row.setSpacing(10)
        self._mc_rps  = _DashMetricCard("Anlık RPS",   "—", C_ACCENT)
        self._mc_pred = _DashMetricCard("AI Tahmini",  "—", "#A78BFA")
        self._mc_pods = _DashMetricCard("Aktif Pod",   "—", C_GREEN)
        self._mc_cost = _DashMetricCard("₺/Saat",      "—", C_YELLOW)
        self._mc_eff  = _DashMetricCard("RPS/Pod",     "—", "#38BDF8")
        for mc in [self._mc_rps, self._mc_pred, self._mc_pods, self._mc_cost, self._mc_eff]:
            mc_row.addWidget(mc, 1)
        lay.addLayout(mc_row)

        # ── Chart card
        chart_card = QFrame()
        chart_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08); border-radius:18px; }}"
        )
        _add_shadow(chart_card, blur=24, offset_y=6, alpha=70)
        cc = QVBoxLayout(chart_card)
        cc.setContentsMargins(18, 14, 18, 14)
        cc.setSpacing(8)

        cc_hdr = QHBoxLayout()
        ct = QLabel("Trafik Zaman Serisi")
        ct.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        ct.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        self._range_lbl = QLabel("Son 6 dakika  •  5 sn aralık")
        self._range_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; background:transparent; border:none;")
        cc_hdr.addWidget(ct)
        cc_hdr.addStretch()
        cc_hdr.addWidget(self._range_lbl)
        cc.addLayout(cc_hdr)

        try:
            import matplotlib
            matplotlib.use("QtAgg")
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            _bg = "#0C0C1E"
            matplotlib.rcParams.update({
                "axes.facecolor":   _bg,
                "figure.facecolor": _bg,
                "text.color":       "#F2F4FF",
                "axes.labelcolor":  "#5A6A8A",
                "xtick.color":      "#5A6A8A",
                "ytick.color":      "#5A6A8A",
                "axes.edgecolor":   "#28285A",
                "grid.color":       "#28285A",
                "grid.alpha":       0.35,
                "xtick.labelsize":  8,
                "ytick.labelsize":  8,
            })
            self._fig = Figure(figsize=(10, 2.8), dpi=96)
            self._fig.patch.set_facecolor(_bg)
            self._ax = self._fig.add_subplot(111)
            self._ax.set_facecolor(_bg)
            self._ax.grid(True, alpha=0.25, linestyle="--")
            for sp in self._ax.spines.values():
                sp.set_color("#28285A")
            self._ln_real, = self._ax.plot([], [], color="#818CF8", linewidth=2.2,
                                            label="Gerçek RPS", solid_capstyle="round")
            self._ln_pred, = self._ax.plot([], [], color="#A78BFA", linewidth=1.6,
                                            linestyle="--", label="AI Tahmini")
            self._ax.legend(loc="upper left", framealpha=0.0,
                            labelcolor="#F2F4FF", fontsize=9)
            self._ax.set_ylabel("RPS", fontsize=9, color="#5A6A8A")
            self._fig.tight_layout(pad=0.8)
            self._canvas = FigureCanvasQTAgg(self._fig)
            self._canvas.setStyleSheet(f"background:{_bg}; border:none;")
            self._canvas.setMinimumHeight(220)
            cc.addWidget(self._canvas, stretch=1)
            self._canvas.draw()
            self._has_mpl = True
        except Exception:
            fallback = QLabel("Grafik için: pip install matplotlib")
            fallback.setStyleSheet(f"color:{C_TEXT_DIM}; padding:20px; background:transparent; border:none;")
            cc.addWidget(fallback)

        lay.addWidget(chart_card)

        # ── Bottom row
        bot = QHBoxLayout()
        bot.setSpacing(14)

        # Service status card
        svc_card = Card("Servis Durumu")
        sb = svc_card.body()
        self._svc_rows: dict[str, tuple] = {}
        for key, name in [
            ("prometheus", "Prometheus  :9090"),
            ("pushgw",     "Pushgateway :9091"),
            ("app",        "Uygulama"),
            ("keda",       "KEDA"),
        ]:
            row = QHBoxLayout()
            dot = QLabel("⬤")
            dot.setStyleSheet(
                f"color:{C_TEXT_DIM}; font-size:9px; background:transparent; border:none;"
            )
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color:{C_TEXT}; font-size:12px; background:transparent; border:none;")
            slbl = QLabel("—")
            slbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; background:transparent; border:none;")
            row.addWidget(dot)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(slbl)
            sb.addLayout(row)
            self._svc_rows[key] = (dot, slbl)
        bot.addWidget(svc_card, 1)

        # Scaling + KEDA card
        scale_card = Card("Ölçekleme Kontrolü")
        scb = scale_card.body()
        self._keda_lbl = QLabel("KEDA: kontrol ediliyor…")
        self._keda_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;")
        self._keda_detail = QLabel("Min: —  /  Max: —")
        self._keda_detail.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:11px; background:transparent; border:none;"
        )
        scale_row = QHBoxLayout()
        self._scale_spin = QSpinBox()
        self._scale_spin.setRange(0, 20)
        self._scale_spin.setValue(2)
        self._scale_spin.setStyleSheet(
            f"QSpinBox {{ background:{C_SURFACE2}; color:{C_TEXT}; "
            f"border:1px solid rgba(255,255,255,18); border-radius:10px; padding:6px 10px; }}"
        )
        btn_scale = QPushButton("Ölçekle")
        btn_scale.setObjectName("btn_primary")
        btn_scale.setFixedHeight(34)
        btn_scale.clicked.connect(self._do_manual_scale)
        scale_row.addWidget(QLabel("Pod sayısı:"))
        scale_row.addWidget(self._scale_spin)
        scale_row.addWidget(btn_scale)
        scale_row.addStretch()
        self._scale_result = QLabel("")
        self._scale_result.setStyleSheet(
            f"color:{C_GREEN}; font-size:11px; background:transparent; border:none;"
        )
        self._btn_keda_toggle = QPushButton("KEDA Devre Dışı Bırak")
        self._btn_keda_toggle.setObjectName("btn_secondary")
        self._btn_keda_toggle.setFixedHeight(32)
        self._btn_keda_toggle.clicked.connect(self._toggle_keda)
        self._keda_toggle_result = QLabel("")
        self._keda_toggle_result.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:10px; background:transparent; border:none;"
        )
        scb.addWidget(self._keda_lbl)
        scb.addWidget(self._keda_detail)
        scb.addLayout(scale_row)
        scb.addWidget(self._scale_result)
        scb.addWidget(self._btn_keda_toggle)
        scb.addWidget(self._keda_toggle_result)
        bot.addWidget(scale_card, 1)

        lay.addLayout(bot)

        # ── Tab widget (Analiz / Yük Testi / Etkinlikler / GreenOps)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08);
                border-radius:14px; margin-top:-1px;
            }}
            QTabBar::tab {{
                background:transparent; color:{C_TEXT_DIM};
                padding:8px 18px; font-size:12px; border:none;
            }}
            QTabBar::tab:selected {{
                color:{C_TEXT}; font-weight:600;
                border-bottom:2px solid {C_ACCENT};
            }}
            QTabBar::tab:hover {{ color:{C_TEXT}; }}
        """)
        self._tabs.addTab(self._build_analysis_tab(),   "📊  Analiz")
        self._tabs.addTab(self._build_load_test_tab(),  "🧪  Yük Testi")
        self._tabs.addTab(self._build_events_tab(),     "📅  Etkinlikler")
        self._tabs.addTab(self._build_greenops_tab(),   "🌱  GreenOps")
        self._tabs.addTab(self._build_history_tab(),   "📜  Geçmiş")
        self._tabs.addTab(self._build_technical_tab(), "🔧  Teknik")
        lay.addWidget(self._tabs)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Data Refresh ────────────────────────────────────────────────────────
    def _refresh(self):
        import threading
        threading.Thread(target=self._fetch_and_apply, daemon=True).start()

    def _fetch_and_apply(self):
        import datetime, requests as _req
        data = {}
        try:
            r = _req.get(self.PROM_URL,
                         params={"query": 'sum(rate(http_requests_total[1m]))'},
                         timeout=2)
            res = r.json().get("data", {}).get("result", [])
            data["rps"] = float(res[0]["value"][1]) if res else 0.0
        except Exception:
            data["rps"] = 0.0

        try:
            r = _req.get(self.PROM_URL,
                         params={"query": "predicted_rps_30min"},
                         timeout=2)
            res = r.json().get("data", {}).get("result", [])
            data["pred"] = float(res[0]["value"][1]) if res else 0.0
        except Exception:
            data["pred"] = 0.0

        # Timeseries (son 6 dakika, 30sn adım)
        try:
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            r = _req.get(self.PROM_RANGE_URL, params={
                "query": 'sum(rate(http_requests_total[1m]))',
                "start": (now - datetime.timedelta(minutes=6)).isoformat() + "Z",
                "end":   now.isoformat() + "Z",
                "step":  "30s",
            }, timeout=3)
            vals = r.json().get("data", {}).get("result", [])
            if vals:
                pts = vals[0].get("values", [])
                data["ts_time"]  = [datetime.datetime.fromtimestamp(float(t)).strftime("%H:%M:%S")
                                    for t, _ in pts]
                data["ts_rps"]   = [float(v) for _, v in pts]
            else:
                data["ts_time"] = []
                data["ts_rps"]  = []
        except Exception:
            data["ts_time"] = []
            data["ts_rps"]  = []

        # AI prediction timeseries
        try:
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            r = _req.get(self.PROM_RANGE_URL, params={
                "query": "predicted_rps_30min",
                "start": (now - datetime.timedelta(minutes=6)).isoformat() + "Z",
                "end":   now.isoformat() + "Z",
                "step":  "30s",
            }, timeout=3)
            vals = r.json().get("data", {}).get("result", [])
            data["ts_pred"] = [float(v) for _, v in vals[0].get("values", [])] if vals else []
        except Exception:
            data["ts_pred"] = []

        # Pod count
        try:
            ns = (self.ops.get_instance() or {}).get("namespace", "autoscaleops")
            name = self.db.get_setting("active_project_name", "autoscaleops-app")
            ok, out = run_ps(
                f"kubectl get pods -n {ns} -l app={name} "
                f"--field-selector=status.phase=Running --no-headers 2>&1"
            )
            data["pods"] = len([l for l in out.strip().splitlines() if l.strip()]) if ok else 0
        except Exception:
            data["pods"] = 0

        # Service liveness
        import socket
        for key, host, port in [
            ("prometheus", "127.0.0.1", 9090),
            ("pushgw",     "127.0.0.1", 9091),
            ("app",        "127.0.0.1", int(self.db.get_setting("active_project_port", "8080"))),
        ]:
            try:
                s = socket.create_connection((host, port), timeout=1)
                s.close()
                data[f"svc_{key}"] = True
            except Exception:
                data[f"svc_{key}"] = False

        # KEDA
        try:
            ok, out = run_ps("kubectl get scaledobjects -A --no-headers 2>&1")
            data["keda_ok"] = ok and bool(out.strip())
            data["keda_txt"] = out.strip().split("\n")[0][:60] if ok and out.strip() else "—"
        except Exception:
            data["keda_ok"] = False
            data["keda_txt"] = "—"

        import datetime as _dt
        data["ts_now"] = _dt.datetime.now().strftime("%H:%M:%S")
        # Apply on main thread
        QTimer.singleShot(0, lambda: self._apply(data))

    def _apply(self, data: dict):
        rps   = data.get("rps",  0.0)
        pred  = data.get("pred", 0.0)
        pods  = data.get("pods", 0)
        cost  = pods * self.COST_PER_POD_HOUR
        eff   = (rps / pods) if pods > 0 else 0.0

        self._mc_rps.set_value(f"{rps:.1f}")
        self._mc_pred.set_value(f"{pred:.1f}",
                                f"Δ {pred-rps:+.1f}" if pred else "")
        self._mc_pods.set_value(str(pods))
        self._mc_cost.set_value(f"₺{cost:.3f}")
        self._mc_eff.set_value(f"{eff:.1f}" if pods else "—")

        # Live dot
        self._live_dot.setStyleSheet(
            f"color:{C_GREEN}; font-size:10px; font-weight:600; background:transparent; border:none;"
            if rps > 0 else
            f"color:{C_TEXT_DIM}; font-size:10px; font-weight:600; background:transparent; border:none;"
        )
        self._upd_lbl.setText(f"Son güncelleme: {data.get('ts_now','—')}")

        # Chart
        if self._has_mpl:
            ts   = data.get("ts_time", [])
            rps_v = data.get("ts_rps",  [])
            pred_v = data.get("ts_pred", [])
            # Pad pred to same length
            if len(pred_v) < len(rps_v):
                pred_v = pred_v + [0.0] * (len(rps_v) - len(pred_v))
            xs = list(range(len(rps_v)))
            self._ln_real.set_data(xs, rps_v)
            self._ln_pred.set_data(xs, pred_v[:len(xs)])
            if xs:
                self._ax.set_xlim(0, max(xs))
                ymax = max(max(rps_v + pred_v[:len(xs)] + [1]), 10) * 1.15
                self._ax.set_ylim(0, ymax)
            # X tick labels
            if ts:
                step = max(1, len(ts) // 6)
                self._ax.set_xticks(xs[::step])
                self._ax.set_xticklabels([ts[i] for i in xs[::step]], fontsize=7)
            # Fill under real RPS
            if self._fill:
                try:
                    self._fill.remove()
                except Exception:
                    pass
                self._fill = None
            if rps_v:
                self._fill = self._ax.fill_between(xs, rps_v, alpha=0.10, color="#818CF8")
            self._canvas.draw_idle()

        # Services
        for key in ("prometheus", "pushgw", "app"):
            up = data.get(f"svc_{key}", False)
            dot, slbl = self._svc_rows[key]
            dot.setStyleSheet(
                f"color:{C_GREEN}; font-size:9px; background:transparent; border:none;"
                if up else
                f"color:{C_RED}; font-size:9px; background:transparent; border:none;"
            )
            slbl.setText("Bağlı" if up else "Çevrimdışı")

        # KEDA
        keda_ok = data.get("keda_ok", False)
        dot_k, slbl_k = self._svc_rows["keda"]
        dot_k.setStyleSheet(
            f"color:{C_GREEN}; font-size:9px; background:transparent; border:none;"
            if keda_ok else
            f"color:{C_YELLOW}; font-size:9px; background:transparent; border:none;"
        )
        slbl_k.setText("Aktif" if keda_ok else "Yok / Bekliyor")
        self._keda_lbl.setText(f"KEDA: {'Aktif' if keda_ok else 'Devre Dışı'}")
        self._keda_detail.setText(data.get("keda_txt", "—"))
        # Store for toggle button
        self._last_keda_ok = keda_ok
        self._btn_keda_toggle.setText(
            "KEDA Devre Dışı Bırak" if keda_ok else "KEDA Aktifleştir"
        )
        # Save metrics to history (background)
        threading.Thread(
            target=self._save_metrics_history, args=(rps, pred, pods), daemon=True
        ).start()
        # GreenOps check (background, throttled to every ~30s)
        now_ts = time.time()
        if not hasattr(self, "_last_go_check") or now_ts - self._last_go_check > 30:
            self._last_go_check = now_ts
            threading.Thread(target=self._greenops_check, daemon=True).start()

    # ── Manual Scale ───────────────────────────────────────────────────────
    def _do_manual_scale(self):
        n = self._scale_spin.value()
        self._scale_result.setText("Ölçekleniyor…")
        def do():
            instance = self.ops.get_instance()
            if not instance:
                QTimer.singleShot(0, lambda: self._scale_result.setText("Instance bulunamadı"))
                return
            ns   = instance.get("namespace", "autoscaleops")
            name = self.db.get_setting("active_project_name", "autoscaleops-app")
            ok, out = run_ps(
                f"kubectl scale deployment {name}-deployment --replicas={n} -n {ns} 2>&1"
            )
            msg = f"✅  {n} pod'a ölçeklendi" if ok else f"❌  {out[:60]}"
            QTimer.singleShot(0, lambda: self._scale_result.setText(msg))
        import threading
        threading.Thread(target=do, daemon=True).start()

    # ── Constants for tabs ──────────────────────────────────────────────────
    STATE_DIR = Path.home() / ".autoscaleops" / ".dashboard_state"
    SPECIAL_DAYS = [
        (2,  14, "Sevgililer Günü",  "çok_yüksek", 1.80),
        (3,   8, "Kadınlar Günü",    "yüksek",     1.50),
        (5,   2, "Anneler Günü",     "çok_yüksek", 1.80),
        (6,  16, "Babalar Günü",     "yüksek",     1.50),
        (9,   1, "Okula Dönüş",      "çok_yüksek", 1.80),
        (11, 11, "11.11 Kampanya",   "yüksek",     1.50),
        (11, 25, "Siber Pazartesi",  "çok_yüksek", 1.80),
        (11, 29, "Kara Cuma",        "çok_yüksek", 1.80),
        (12, 12, "12.12 Kampanya",   "yüksek",     1.50),
        (12, 25, "Noel",             "çok_yüksek", 1.80),
        (1,   1, "Yılbaşı",          "çok_yüksek", 1.80),
        (7,   1, "Yaz İndirimleri",  "yüksek",     1.50),
    ]
    LEVEL_COLOR = {
        "çok_yüksek": "#f87171",
        "yüksek":     "#fbbf24",
        "orta":       "#a3e635",
        "düşük":      "#4ade80",
    }
    LEVEL_MULT = {"çok_yüksek": 1.80, "yüksek": 1.50, "orta": 1.30, "düşük": 1.15}

    # ── Tab Builders ────────────────────────────────────────────────────────
    def _build_analysis_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{C_SURFACE}; border:none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        # ComboBox selector
        sel_row = QHBoxLayout()
        sel_lbl = QLabel("Analiz Türü:")
        sel_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:12px; background:transparent; border:none;")
        self._analysis_combo = QComboBox()
        self._analysis_combo.addItems([
            "Mevcut Durum",
            "Haftalık Trend",
            "Maliyet Optimizasyonu",
            "Tahmin Doğruluğu",
            "Önümüzdeki Hafta Tahmini",
        ])
        self._analysis_combo.setStyleSheet(
            f"QComboBox {{ background:{C_SURFACE2}; color:{C_TEXT}; "
            f"border:1px solid rgba(255,255,255,18); border-radius:10px; padding:6px 12px; }}"
            f"QComboBox QAbstractItemView {{ background:{C_SURFACE2}; color:{C_TEXT}; }}"
        )
        btn_refresh_analysis = QPushButton("↻")
        btn_refresh_analysis.setFixedSize(32, 32)
        btn_refresh_analysis.clicked.connect(lambda: self._update_analysis(self._analysis_combo.currentIndex()))
        sel_row.addWidget(sel_lbl)
        sel_row.addWidget(self._analysis_combo, 1)
        sel_row.addWidget(btn_refresh_analysis)
        lay.addLayout(sel_row)

        # HTML content browser
        self._analysis_browser = QTextBrowser()
        self._analysis_browser.setOpenExternalLinks(False)
        self._analysis_browser.setStyleSheet(
            f"QTextBrowser {{ background:{C_SURFACE2}; color:{C_TEXT}; "
            f"border:1px solid rgba(255,255,255,0.06); border-radius:12px; "
            f"padding:14px; font-size:13px; }}"
        )
        self._analysis_browser.setMinimumHeight(220)
        lay.addWidget(self._analysis_browser)
        self._analysis_combo.currentIndexChanged.connect(self._update_analysis)
        # Initial content
        QTimer.singleShot(2000, lambda: self._update_analysis(0))
        return w

    def _update_analysis(self, idx: int):
        import datetime, json as _json
        history = []
        hist_file = self.STATE_DIR / "metrics_history.json"
        try:
            if hist_file.exists():
                history = _json.loads(hist_file.read_text(encoding="utf-8"))
        except Exception:
            pass

        rps   = float(self._mc_rps._val_lbl.text().replace("—","0") or 0)
        pred  = float(self._mc_pred._val_lbl.text().replace("—","0") or 0)
        pods  = int(self._mc_pods._val_lbl.text().replace("—","0") or 0)
        cost  = pods * self.COST_PER_POD_HOUR

        def _kv(k, v, color="#F2F4FF"):
            return f"<tr><td style='color:#5A6A8A;padding:4px 12px 4px 0'>{k}</td><td style='color:{color};font-weight:600'>{v}</td></tr>"

        if idx == 0:  # Mevcut Durum
            now = datetime.datetime.now()
            upcoming = self._get_upcoming_events(days=14)
            rows = (_kv("Anlık RPS", f"{rps:.2f}") +
                    _kv("AI Tahmini", f"{pred:.2f}") +
                    _kv("Aktif Pod", str(pods)) +
                    _kv("Verimlilik", f"{(rps/pods):.2f} RPS/pod" if pods else "—") +
                    _kv("₺/Saat", f"₺{cost:.4f}") +
                    _kv("Zaman", now.strftime("%d.%m.%Y %H:%M")))
            ev_html = ""
            for ev in upcoming[:5]:
                clr = self.LEVEL_COLOR.get(ev.get("level",""), "#aaa")
                ev_html += f"<li style='color:{clr};margin:3px 0'>★ {ev['name']} — {ev['date']} &nbsp;<b>×{ev['mult']}</b></li>"
            html = (f"<h3 style='color:{C_ACCENT};margin:0 0 10px'>Mevcut Durum</h3>"
                    f"<table>{rows}</table>"
                    + (f"<h4 style='color:{C_TEXT};margin:14px 0 6px'>Yaklaşan Etkinlikler</h4><ul style='padding-left:16px'>{ev_html}</ul>" if ev_html else ""))

        elif idx == 1:  # Haftalık Trend
            if len(history) >= 2:
                recent = history[-min(len(history), 500):]
                rps_vals = [e.get("rps", 0) for e in recent]
                avg = sum(rps_vals) / len(rps_vals)
                peak = max(rps_vals)
                minv = min(rps_vals)
                trend = ((rps_vals[-1] - rps_vals[0]) / (rps_vals[0] + 0.001)) * 100
                rows = (_kv("Ortalama RPS", f"{avg:.2f}") +
                        _kv("Tepe RPS", f"{peak:.2f}", "#f87171") +
                        _kv("Minimum RPS", f"{minv:.2f}") +
                        _kv("Trend", f"{trend:+.1f}%", "#4ade80" if trend >= 0 else "#f87171") +
                        _kv("Veri Noktası", str(len(recent))))
            else:
                rows = _kv("Bilgi", "Yeterli veri yok — sistem çalışırken birikir")
            html = f"<h3 style='color:{C_ACCENT};margin:0 0 10px'>Haftalık Trend</h3><table>{rows}</table>"

        elif idx == 2:  # Maliyet Optimizasyonu
            hourly = cost
            daily  = hourly * 24
            monthly = daily * 30
            idle_hrs = 8
            savings = idle_hrs * (pods - 1) * self.COST_PER_POD_HOUR if pods > 1 else 0
            rows = (_kv("Saatlik Maliyet", f"₺{hourly:.4f}") +
                    _kv("Günlük Tahmini", f"₺{daily:.3f}") +
                    _kv("Aylık Tahmini", f"₺{monthly:.2f}") +
                    _kv("Boşta Tasarruf", f"₺{savings:.4f}/gün", "#4ade80") +
                    _kv("Pod Başına", f"₺{self.COST_PER_POD_HOUR}/saat"))
            recom = max(1, int(rps / 5)) if rps > 0 else pods
            html = (f"<h3 style='color:{C_ACCENT};margin:0 0 10px'>Maliyet Optimizasyonu</h3>"
                    f"<table>{rows}</table>"
                    f"<p style='color:#a3e635;margin-top:12px'>💡 Öneri: Şu trafik için <b>{recom} pod</b> yeterli.</p>")

        elif idx == 3:  # Tahmin Doğruluğu
            if len(history) >= 10:
                pairs = [(e.get("rps",0), e.get("pred",0)) for e in history[-100:] if e.get("pred",0) > 0]
                if pairs:
                    mape = sum(abs(r-p)/(r+0.001)*100 for r,p in pairs) / len(pairs)
                    cur_err = abs(rps - pred) / (rps + 0.001) * 100
                    rows = (_kv("7 Günlük MAPE", f"{mape:.1f}%") +
                            _kv("Mevcut Hata", f"{cur_err:.1f}%") +
                            _kv("Örnek Sayısı", str(len(pairs))) +
                            _kv("Anlık RPS", f"{rps:.2f}") +
                            _kv("AI Tahmini", f"{pred:.2f}"))
                    html = f"<h3 style='color:{C_ACCENT};margin:0 0 10px'>Tahmin Doğruluğu</h3><table>{rows}</table>"
                else:
                    html = f"<h3 style='color:{C_ACCENT}'>Tahmin Doğruluğu</h3><p style='color:{C_TEXT_DIM}'>Tahmin verisi bulunamadı.</p>"
            else:
                html = f"<h3 style='color:{C_ACCENT}'>Tahmin Doğruluğu</h3><p style='color:{C_TEXT_DIM}'>Daha fazla veri birikmesi bekleniyor ({len(history)}/10).</p>"

        else:  # Önümüzdeki Hafta Tahmini
            if len(history) >= 20:
                recent = history[-min(len(history), 200):]
                rps_vals = [e.get("rps", 0) for e in recent]
                avg = sum(rps_vals) / len(rps_vals)
                trend_pct = ((rps_vals[-1] - rps_vals[0]) / (rps_vals[0] + 0.001)) * 100 / max(len(rps_vals), 1)
                forecast = avg * (1 + trend_pct * 7 / 100)
                peak_f = forecast * 1.4
                max_replicas = max(2, int(peak_f / 5) + 1)
                rows = (_kv("7 Günlük Ort Tahmini", f"{forecast:.2f} RPS") +
                        _kv("Büyüme Trendi", f"{trend_pct*7:+.1f}%") +
                        _kv("Tepe Tahmini (×1.4)", f"{peak_f:.2f} RPS", "#fbbf24") +
                        _kv("Önerilen maxReplicas", str(max_replicas), "#4ade80"))
                html = f"<h3 style='color:{C_ACCENT};margin:0 0 10px'>Önümüzdeki Hafta Tahmini</h3><table>{rows}</table>"
            else:
                html = f"<h3 style='color:{C_ACCENT}'>Önümüzdeki Hafta Tahmini</h3><p style='color:{C_TEXT_DIM}'>Daha fazla veri birikmesi bekleniyor ({len(history)}/20).</p>"

        base_css = f"body{{background:{C_SURFACE2};color:{C_TEXT};font-family:'Segoe UI',sans-serif;font-size:13px;padding:6px}}"
        self._analysis_browser.setHtml(f"<html><head><style>{base_css}</style></head><body>{html}</body></html>")

    def _get_upcoming_events(self, days=14) -> list:
        import datetime as _dt
        today = _dt.date.today()
        result = []
        for month, day, name, level, mult in self.SPECIAL_DAYS:
            for year_off in (0, 1):
                try:
                    ev_date = _dt.date(today.year + year_off, month, day)
                    diff = (ev_date - today).days
                    if 0 <= diff <= days:
                        result.append({"name": name, "date": ev_date.strftime("%d.%m.%Y"),
                                       "diff": diff, "level": level, "mult": mult})
                except ValueError:
                    pass
        # User events
        for ev in self._load_events():
            try:
                start = _dt.date.fromisoformat(ev.get("baslangic", ""))
                end   = _dt.date.fromisoformat(ev.get("bitis", start.isoformat()))
                diff  = (start - today).days
                if -1 <= diff <= days or (start <= today <= end):
                    result.append({"name": ev.get("ad","?"), "date": start.strftime("%d.%m.%Y"),
                                   "diff": max(diff, 0), "level": ev.get("seviye","orta"),
                                   "mult": self.LEVEL_MULT.get(ev.get("seviye","orta"), 1.30)})
            except Exception:
                pass
        result.sort(key=lambda x: x["diff"])
        return result

    def _build_load_test_tab(self) -> QWidget:
        self._k6_proc = None
        self._k6_timer = QTimer(self)
        self._k6_timer.timeout.connect(self._poll_k6_status)
        self._k6_start_time = time.time()
        self._k6_duration = 60
        self._py_sim_stop_flag = [False]
        self._py_sim_results = {"reqs": 0, "errors": 0, "durations": []}

        w = QWidget()
        w.setStyleSheet(f"background:{C_SURFACE}; border:none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)

        # Config card
        cfg = QFrame()
        cfg.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE2}; border:1px solid rgba(255,255,255,0.07); border-radius:12px; }}"
        )
        cfg_lay = QVBoxLayout(cfg)
        cfg_lay.setContentsMargins(16, 12, 16, 12)
        cfg_lay.setSpacing(8)

        cfg_title = QLabel("Test Konfigürasyonu")
        cfg_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        cfg_title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        cfg_lay.addWidget(cfg_title)

        p1 = QHBoxLayout()
        for lbl, spin_name, mn, mx, val in [
            ("Sanal Kullanıcı (VU):", "_k6_vu",    1, 500, 10),
            ("Süre (sn):",           "_k6_dur",  10, 3600, 60),
        ]:
            l = QLabel(lbl); l.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
            s = QSpinBox(); s.setRange(mn, mx); s.setValue(val)
            s.setStyleSheet(f"QSpinBox {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:4px 8px; }}")
            setattr(self, spin_name, s)
            p1.addWidget(l); p1.addWidget(s); p1.addSpacing(16)
        p1.addStretch()
        cfg_lay.addLayout(p1)

        p2 = QHBoxLayout()
        gap_lbl = QLabel("İstek Aralığı (sn):")
        gap_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._k6_gap = QDoubleSpinBox()
        self._k6_gap.setRange(0.1, 10.0)
        self._k6_gap.setSingleStep(0.1)
        self._k6_gap.setValue(1.0)
        self._k6_gap.setStyleSheet(f"QDoubleSpinBox {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:4px 8px; }}")
        p2.addWidget(gap_lbl); p2.addWidget(self._k6_gap); p2.addStretch()
        cfg_lay.addLayout(p2)

        # Scenario selection
        sc_lbl = QLabel("Senaryo:")
        sc_lbl.setStyleSheet(f"color:{C_TEXT}; font-weight:600; background:transparent; border:none;")
        cfg_lay.addWidget(sc_lbl)
        sc_row = QHBoxLayout()
        self._k6_radio_std = QRadioButton("Standart Yük")
        self._k6_radio_ev  = QRadioButton("Etkinlik Simülasyonu")
        self._k6_radio_std.setChecked(True)
        for rb in (self._k6_radio_std, self._k6_radio_ev):
            rb.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        sc_row.addWidget(self._k6_radio_std)
        sc_row.addWidget(self._k6_radio_ev)
        sc_row.addStretch()
        cfg_lay.addLayout(sc_row)

        ev_row = QHBoxLayout()
        ev_lbl = QLabel("Etkinlik:")
        ev_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._k6_ev_combo = QComboBox()
        for _, _, name, level, mult in self.SPECIAL_DAYS:
            self._k6_ev_combo.addItem(f"{name} (×{mult})")
        self._k6_ev_combo.setStyleSheet(
            f"QComboBox {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:4px 8px; }}"
            f"QComboBox QAbstractItemView {{ background:{C_SURFACE2}; color:{C_TEXT}; }}"
        )
        self._k6_mult_lbl = QLabel("×1.80")
        self._k6_mult_lbl.setStyleSheet(f"color:#fbbf24; font-weight:600; background:transparent; border:none;")
        self._k6_ev_combo.currentIndexChanged.connect(self._on_k6_event_changed)
        ev_row.addWidget(ev_lbl); ev_row.addWidget(self._k6_ev_combo); ev_row.addWidget(self._k6_mult_lbl); ev_row.addStretch()
        cfg_lay.addLayout(ev_row)

        self._k6_radio_std.toggled.connect(lambda c: self._k6_ev_combo.setEnabled(not c))
        self._k6_ev_combo.setEnabled(False)

        btn_start = QPushButton("▶  Testi Başlat")
        btn_start.setObjectName("btn_primary")
        btn_start.setFixedHeight(36)
        btn_start.clicked.connect(self._start_k6_test)
        cfg_lay.addWidget(btn_start)
        lay.addWidget(cfg)

        # Progress card
        prog_card = QFrame()
        prog_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE2}; border:1px solid rgba(255,255,255,0.07); border-radius:12px; }}"
        )
        prog_lay = QVBoxLayout(prog_card)
        prog_lay.setContentsMargins(16, 12, 16, 12)
        prog_lay.setSpacing(6)
        prog_title = QLabel("Test Durumu")
        prog_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        prog_title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        prog_lay.addWidget(prog_title)
        self._k6_prog = QProgressBar()
        self._k6_prog.setRange(0, 100)
        self._k6_prog.setValue(0)
        self._k6_prog.setStyleSheet(
            f"QProgressBar {{ background:{C_SURFACE}; border:none; border-radius:6px; height:14px; }}"
            f"QProgressBar::chunk {{ background:{C_ACCENT}; border-radius:6px; }}"
        )
        self._k6_status_lbl = QLabel("Bekliyor…")
        self._k6_status_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;")
        btn_stop = QPushButton("■  Durdur")
        btn_stop.setFixedWidth(100)
        btn_stop.clicked.connect(self._stop_k6_test)
        stop_row = QHBoxLayout()
        stop_row.addWidget(self._k6_status_lbl)
        stop_row.addStretch()
        stop_row.addWidget(btn_stop)
        prog_lay.addWidget(self._k6_prog)
        prog_lay.addLayout(stop_row)
        lay.addWidget(prog_card)

        # Results card
        res_card = QFrame()
        res_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE2}; border:1px solid rgba(255,255,255,0.07); border-radius:12px; }}"
        )
        res_lay = QVBoxLayout(res_card)
        res_lay.setContentsMargins(16, 12, 16, 12)
        res_title = QLabel("Son Test Sonuçları")
        res_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        res_title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        self._k6_result_browser = QTextBrowser()
        self._k6_result_browser.setMinimumHeight(100)
        self._k6_result_browser.setStyleSheet(
            f"QTextBrowser {{ background:{C_SURFACE}; color:{C_TEXT}; border:none; border-radius:8px; padding:10px; font-size:12px; }}"
        )
        self._k6_result_browser.setHtml(
            f"<p style='color:{C_TEXT_DIM}'>Henüz test çalıştırılmadı.</p>"
        )
        res_lay.addWidget(res_title)
        res_lay.addWidget(self._k6_result_browser)
        lay.addWidget(res_card)
        lay.addStretch()
        return w

    def _on_k6_event_changed(self, idx: int):
        mult = self.SPECIAL_DAYS[idx][4] if idx < len(self.SPECIAL_DAYS) else 1.0
        vu   = self._k6_vu.value()
        self._k6_mult_lbl.setText(f"×{mult}  →  {int(vu * mult)} VU")

    def _start_k6_test(self):
        import shutil as _sh
        vu  = self._k6_vu.value()
        dur = self._k6_dur.value()
        gap = self._k6_gap.value()
        if self._k6_radio_ev.isChecked():
            idx  = self._k6_ev_combo.currentIndex()
            mult = self.SPECIAL_DAYS[idx][4] if idx < len(self.SPECIAL_DAYS) else 1.0
            vu   = max(1, int(vu * mult))
        active = {}
        if ACTIVE_PROJECT_PATH.exists():
            try:
                active = json.loads(ACTIVE_PROJECT_PATH.read_text())
            except Exception:
                pass
        port   = active.get("port", 8080)
        target = f"http://localhost:{port}"

        use_k6 = _sh.which("k6") is not None
        if use_k6:
            self._k6_output_path = str(self.STATE_DIR / "k6_last_result.json")
            script = (
                "import http from 'k6/http';\nimport { sleep } from 'k6';\n"
                f"export const options = {{ vus: {vu}, duration: '{dur}s', "
                f"thresholds: {{ http_req_duration: ['p(95)<1000'], http_req_failed: ['rate<0.10'] }} }};\n"
                f"export default function() {{ http.get('{target}'); sleep({gap}); }}\n"
            )
            self.STATE_DIR.mkdir(parents=True, exist_ok=True)
            script_path = str(self.STATE_DIR / "k6_script.js")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)
            try:
                self._k6_proc = subprocess.Popen(
                    ["k6", "run", "--out", f"json={self._k6_output_path}", script_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception as e:
                self._k6_result_browser.setHtml(f"<p style='color:#f87171'>❌ k6 başlatılamadı: {e}</p>")
                return
            self._k6_start_time = time.time()
            self._k6_duration   = dur
            self._k6_prog.setValue(0)
            self._k6_status_lbl.setText(f"Çalışıyor (k6)…  {vu} VU  •  {dur}s")
            self._k6_timer.start(1000)
        else:
            # Python tabanlı trafik simülatörü (k6 gerekmez)
            self._py_sim_stop = False
            self._py_sim_results = {"reqs": 0, "errors": 0, "durations": []}
            self._k6_start_time = time.time()
            self._k6_duration   = dur
            self._k6_proc = None  # k6 yok, Python modu
            self._k6_prog.setValue(0)
            self._k6_status_lbl.setText(f"Çalışıyor (Python)…  {vu} iş parçacığı  •  {dur}s  →  {target}")
            # Bilgi banner'ı
            css = f"body{{background:{C_SURFACE};color:{C_TEXT};font-family:'Segoe UI',sans-serif;padding:4px}}"
            self._k6_result_browser.setHtml(
                f"<html><head><style>{css}</style></head><body>"
                f"<p style='color:#fbbf24'>⚡ Python trafik simülatörü aktif (k6 kurulu değil).<br>"
                f"Hedef: <b>{target}</b> — {vu} eş zamanlı iş parçacığı, {dur}s</p>"
                f"</body></html>"
            )
            def _worker(target_url, gap_s, stop_flag, results):
                import requests as _r
                while not stop_flag[0]:
                    t0 = time.time()
                    try:
                        resp = _r.get(target_url, timeout=5)
                        elapsed_ms = (time.time() - t0) * 1000
                        results["reqs"] += 1
                        results["durations"].append(elapsed_ms)
                        if resp.status_code >= 400:
                            results["errors"] += 1
                    except Exception:
                        results["reqs"] += 1
                        results["errors"] += 1
                    time.sleep(gap_s)

            self._py_sim_stop_flag = [False]
            for _ in range(vu):
                threading.Thread(
                    target=_worker,
                    args=(target, gap, self._py_sim_stop_flag, self._py_sim_results),
                    daemon=True
                ).start()
            self._k6_timer.start(1000)

    def _poll_k6_status(self):
        elapsed = time.time() - self._k6_start_time
        pct = min(int(elapsed / self._k6_duration * 100), 99)
        self._k6_prog.setValue(pct)
        rem = max(0, int(self._k6_duration - elapsed))

        if self._k6_proc is not None:
            # k6 modu
            self._k6_status_lbl.setText(f"Çalışıyor (k6)…  {int(elapsed)}s / {self._k6_duration}s  ({pct}%)  •  {rem}s kaldı")
            if self._k6_proc.poll() is not None:
                self._k6_timer.stop()
                self._k6_prog.setValue(100)
                self._k6_status_lbl.setText("Tamamlandı ✅")
                results = self._parse_k6_results(self._k6_output_path)
                self._show_k6_results(results)
                self._k6_proc = None
        else:
            # Python modu
            r = getattr(self, "_py_sim_results", {"reqs": 0, "errors": 0, "durations": []})
            self._k6_status_lbl.setText(
                f"Çalışıyor (Python)…  {int(elapsed)}s / {self._k6_duration}s  ({pct}%)  •  {r['reqs']} istek  •  {rem}s kaldı"
            )
            if elapsed >= self._k6_duration:
                self._stop_k6_test()

    def _stop_k6_test(self):
        self._k6_timer.stop()
        if self._k6_proc is not None:
            self._k6_proc.terminate()
            self._k6_proc = None
        if hasattr(self, "_py_sim_stop_flag"):
            self._py_sim_stop_flag[0] = True
        self._k6_prog.setValue(100 if time.time() - (self._k6_start_time or 0) >= self._k6_duration else 0)
        self._k6_status_lbl.setText("Tamamlandı ✅" if self._k6_prog.value() == 100 else "Durduruldu")
        # Python modu sonuçlarını göster
        r = getattr(self, "_py_sim_results", None)
        if r and r["reqs"] > 0:
            durations = sorted(r["durations"])
            results = {
                "reqs": r["reqs"],
                "failed": r["errors"],
                "avg_ms": sum(durations) / len(durations) if durations else 0,
                "p95_ms": durations[int(len(durations) * 0.95)] if durations else 0,
                "p99_ms": durations[int(len(durations) * 0.99)] if durations else 0,
                "rps_peak": r["reqs"] / max(self._k6_duration, 1),
            }
            self._show_k6_results(results)

    def _parse_k6_results(self, output_path: str) -> dict:
        import json as _json
        results = {"reqs": 0, "failed": 0, "avg_ms": 0, "p95_ms": 0, "p99_ms": 0, "rps_peak": 0}
        try:
            lines = []
            if Path(output_path).exists():
                with open(output_path, encoding="utf-8") as f:
                    lines = f.readlines()
            durations = []
            for line in lines:
                try:
                    obj = _json.loads(line)
                    if obj.get("type") == "Point" and obj.get("metric") == "http_req_duration":
                        durations.append(obj["data"]["value"])
                    if obj.get("type") == "Point" and obj.get("metric") == "http_reqs":
                        results["reqs"] += 1
                    if obj.get("type") == "Point" and obj.get("metric") == "http_req_failed":
                        results["failed"] += int(obj["data"]["value"])
                except Exception:
                    pass
            if durations:
                durations.sort()
                results["avg_ms"] = sum(durations) / len(durations)
                results["p95_ms"] = durations[int(len(durations) * 0.95)]
                results["p99_ms"] = durations[int(len(durations) * 0.99)]
                results["rps_peak"] = len(durations) / max(self._k6_duration, 1)
        except Exception:
            pass
        return results

    def _show_k6_results(self, r: dict):
        fail_pct = (r["failed"] / max(r["reqs"], 1)) * 100
        ok_icon  = "✅" if fail_pct < 1 else "⚠️"
        html = (
            f"<p style='font-size:14px;font-weight:600;color:#4ade80'>{ok_icon} Test tamamlandı</p>"
            f"<table style='border-collapse:collapse;width:100%'>"
            f"<tr><td style='color:#5A6A8A;padding:3px 12px 3px 0'>Toplam İstek</td><td style='color:{C_TEXT};font-weight:600'>{r['reqs']}</td></tr>"
            f"<tr><td style='color:#5A6A8A;padding:3px 12px 3px 0'>Hata Oranı</td><td style='color:#f87171;font-weight:600'>{fail_pct:.1f}%</td></tr>"
            f"<tr><td style='color:#5A6A8A;padding:3px 12px 3px 0'>Ortalama Yanıt</td><td style='color:{C_TEXT};font-weight:600'>{r['avg_ms']:.0f} ms</td></tr>"
            f"<tr><td style='color:#5A6A8A;padding:3px 12px 3px 0'>p95</td><td style='color:#fbbf24;font-weight:600'>{r['p95_ms']:.0f} ms</td></tr>"
            f"<tr><td style='color:#5A6A8A;padding:3px 12px 3px 0'>p99</td><td style='color:#f87171;font-weight:600'>{r['p99_ms']:.0f} ms</td></tr>"
            f"<tr><td style='color:#5A6A8A;padding:3px 12px 3px 0'>RPS (ort)</td><td style='color:{C_ACCENT};font-weight:600'>{r['rps_peak']:.1f}</td></tr>"
            f"</table>"
        )
        css = f"body{{background:{C_SURFACE};color:{C_TEXT};font-family:'Segoe UI',sans-serif;padding:4px}}"
        self._k6_result_browser.setHtml(f"<html><head><style>{css}</style></head><body>{html}</body></html>")

    def _build_events_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{C_SURFACE}; border:none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)

        # Upcoming special days
        up_title = QLabel("Yaklaşan Özel Günler (14 Gün)")
        up_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        up_title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        lay.addWidget(up_title)

        self._upcoming_frame = QFrame()
        self._upcoming_frame.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE2}; border:1px solid rgba(255,255,255,0.07); border-radius:12px; }}"
        )
        self._upcoming_layout = QVBoxLayout(self._upcoming_frame)
        self._upcoming_layout.setContentsMargins(14, 10, 14, 10)
        self._upcoming_layout.setSpacing(4)
        lay.addWidget(self._upcoming_frame)

        # User events
        user_hdr = QHBoxLayout()
        user_title = QLabel("Kullanıcı Etkinlikleri")
        user_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        user_title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        btn_add_ev = QPushButton("+ Etkinlik Ekle")
        btn_add_ev.setFixedHeight(30)
        btn_add_ev.clicked.connect(self._add_event_dialog)
        user_hdr.addWidget(user_title)
        user_hdr.addStretch()
        user_hdr.addWidget(btn_add_ev)
        lay.addLayout(user_hdr)

        self._user_events_frame = QFrame()
        self._user_events_frame.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE2}; border:1px solid rgba(255,255,255,0.07); border-radius:12px; }}"
        )
        self._user_events_layout = QVBoxLayout(self._user_events_frame)
        self._user_events_layout.setContentsMargins(14, 10, 14, 10)
        self._user_events_layout.setSpacing(4)
        lay.addWidget(self._user_events_frame)
        lay.addStretch()
        QTimer.singleShot(500, self._refresh_events_list)
        return w

    def _refresh_events_list(self):
        import datetime as _dt
        # Clear upcoming
        for i in reversed(range(self._upcoming_layout.count())):
            item = self._upcoming_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        upcoming = self._get_upcoming_events(14)
        if upcoming:
            for ev in upcoming:
                clr = self.LEVEL_COLOR.get(ev.get("level",""), "#aaa")
                diff = ev["diff"]
                diff_txt = "Bugün!" if diff == 0 else f"{diff} gün sonra"
                row_lbl = QLabel(f"★  {ev['name']}  —  {ev['date']}  •  ×{ev['mult']}  •  {diff_txt}")
                row_lbl.setStyleSheet(f"color:{clr}; font-size:12px; background:transparent; border:none; padding:2px 0;")
                self._upcoming_layout.addWidget(row_lbl)
        else:
            lbl = QLabel("Önümüzdeki 14 günde özel etkinlik yok.")
            lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;")
            self._upcoming_layout.addWidget(lbl)

        # User events
        for i in reversed(range(self._user_events_layout.count())):
            item = self._user_events_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        events = self._load_events()
        if events:
            for idx_ev, ev in enumerate(events):
                clr = self.LEVEL_COLOR.get(ev.get("seviye",""), "#aaa")
                ev_row = QHBoxLayout()
                lbl = QLabel(f"◆  {ev.get('ad','?')}  •  {ev.get('baslangic','')} → {ev.get('bitis','')}  •  {ev.get('seviye','')}")
                lbl.setStyleSheet(f"color:{clr}; font-size:12px; background:transparent; border:none;")
                btn_del = QPushButton("🗑")
                btn_del.setFixedSize(28, 28)
                btn_del.setToolTip("Sil")
                def make_del(i):
                    def _del():
                        evs = self._load_events()
                        evs.pop(i)
                        self._save_events(evs)
                        self._refresh_events_list()
                    return _del
                btn_del.clicked.connect(make_del(idx_ev))
                ev_row.addWidget(lbl, 1)
                ev_row.addWidget(btn_del)
                container = QWidget()
                container.setStyleSheet("background:transparent; border:none;")
                container.setLayout(ev_row)
                self._user_events_layout.addWidget(container)
        else:
            lbl = QLabel("Henüz kullanıcı etkinliği eklenmedi.")
            lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;")
            self._user_events_layout.addWidget(lbl)

    def _add_event_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Etkinlik Ekle")
        dlg.setMinimumWidth(360)
        dlg.setStyleSheet(f"QDialog {{ background:{C_SURFACE}; }} QLabel {{ color:{C_TEXT}; background:transparent; }}")
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)

        def _field(label, widget):
            r = QHBoxLayout()
            l = QLabel(label); l.setFixedWidth(130)
            r.addWidget(l); r.addWidget(widget, 1)
            lay.addLayout(r)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Örn: Yaz Kampanyası")
        name_edit.setStyleSheet(f"QLineEdit {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:6px 10px; }}")

        start_edit = QDateEdit()
        start_edit.setCalendarPopup(True)
        start_edit.setDate(QDate.currentDate())
        start_edit.setStyleSheet(f"QDateEdit {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:6px 10px; }}")

        end_edit = QDateEdit()
        end_edit.setCalendarPopup(True)
        end_edit.setDate(QDate.currentDate())
        end_edit.setStyleSheet(f"QDateEdit {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:6px 10px; }}")

        sev_combo = QComboBox()
        sev_combo.addItems(["çok_yüksek", "yüksek", "orta", "düşük"])
        sev_combo.setStyleSheet(
            f"QComboBox {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:6px 10px; }}"
            f"QComboBox QAbstractItemView {{ background:{C_SURFACE2}; color:{C_TEXT}; }}"
        )

        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("Açıklama (isteğe bağlı)")
        desc_edit.setStyleSheet(f"QLineEdit {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:6px 10px; }}")

        _field("Etkinlik Adı:", name_edit)
        _field("Başlangıç:", start_edit)
        _field("Bitiş:", end_edit)
        _field("Trafik Seviyesi:", sev_combo)
        _field("Açıklama:", desc_edit)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet(f"QPushButton {{ background:{C_ACCENT}; color:#fff; border:none; border-radius:8px; padding:6px 16px; }}")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            ev = {
                "ad":         name_edit.text().strip(),
                "baslangic":  start_edit.date().toString("yyyy-MM-dd"),
                "bitis":      end_edit.date().toString("yyyy-MM-dd"),
                "seviye":     sev_combo.currentText(),
                "aciklama":   desc_edit.text().strip(),
            }
            if ev["ad"]:
                evs = self._load_events()
                evs.append(ev)
                self._save_events(evs)
                self._refresh_events_list()

    def _load_events(self) -> list:
        import json as _json
        f = self.STATE_DIR / "events.json"
        try:
            if f.exists():
                return _json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save_events(self, events: list):
        import json as _json
        self.STATE_DIR.mkdir(parents=True, exist_ok=True)
        (self.STATE_DIR / "events.json").write_text(
            _json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _build_greenops_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{C_SURFACE}; border:none;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE2}; border:1px solid rgba(255,255,255,0.07); border-radius:14px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(10)

        title = QLabel("🌱  GreenOps — Enerji Tasarrufu Politikası")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        cl.addWidget(title)

        self._go_enabled = QCheckBox("GreenOps etkin")
        self._go_enabled.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        cl.addWidget(self._go_enabled)

        def _row(label, widget):
            r = QHBoxLayout()
            l = QLabel(label); l.setFixedWidth(200)
            l.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
            r.addWidget(l); r.addWidget(widget); r.addStretch()
            cl.addLayout(r)

        self._go_start = QTimeEdit()
        self._go_start.setDisplayFormat("HH:mm")
        self._go_start.setStyleSheet(f"QTimeEdit {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:5px 10px; }}")
        _row("Mesai Başlangıcı:", self._go_start)

        self._go_end = QTimeEdit()
        self._go_end.setDisplayFormat("HH:mm")
        self._go_end.setStyleSheet(f"QTimeEdit {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:5px 10px; }}")
        _row("Mesai Bitişi:", self._go_end)

        self._go_offhour = QSpinBox()
        self._go_offhour.setRange(0, 10); self._go_offhour.setValue(1)
        self._go_offhour.setStyleSheet(f"QSpinBox {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:5px 10px; }}")
        _row("Mesai Dışı Pod Sayısı:", self._go_offhour)

        self._go_weekend = QSpinBox()
        self._go_weekend.setRange(0, 10); self._go_weekend.setValue(1)
        self._go_weekend.setStyleSheet(f"QSpinBox {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid rgba(255,255,255,14); border-radius:8px; padding:5px 10px; }}")
        _row("Hafta Sonu Pod Sayısı:", self._go_weekend)

        btn_save_go = QPushButton("💾  Kaydet ve Uygula")
        btn_save_go.setObjectName("btn_primary")
        btn_save_go.setFixedHeight(36)
        btn_save_go.clicked.connect(self._save_greenops_and_apply)
        cl.addWidget(btn_save_go)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:rgba(255,255,255,0.08); background:rgba(255,255,255,0.08); border:none; max-height:1px;")
        cl.addWidget(sep)

        self._go_status_lbl = QLabel("Durum: kontrol ediliyor…")
        self._go_status_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; background:transparent; border:none;")
        self._go_savings_lbl = QLabel("")
        self._go_savings_lbl.setStyleSheet(f"color:#4ade80; font-size:12px; background:transparent; border:none;")
        cl.addWidget(self._go_status_lbl)
        cl.addWidget(self._go_savings_lbl)

        lay.addWidget(card)
        lay.addStretch()

        # Load saved config
        self._greenops_load_ui()
        return w

    def _greenops_load_ui(self):
        cfg = self._load_greenops()
        self._go_enabled.setChecked(cfg.get("enabled", False))
        try:
            from PyQt6.QtCore import QTime
            sh, sm = map(int, cfg.get("start", "09:00").split(":"))
            eh, em = map(int, cfg.get("end",   "18:00").split(":"))
            self._go_start.setTime(QTime(sh, sm))
            self._go_end.setTime(QTime(eh, em))
        except Exception:
            pass
        self._go_offhour.setValue(cfg.get("offhour_pods", 1))
        self._go_weekend.setValue(cfg.get("weekend_pods", 1))

    def _load_greenops(self) -> dict:
        import json as _json
        f = self.STATE_DIR / "greenops_config.json"
        try:
            if f.exists():
                return _json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"enabled": False, "start": "09:00", "end": "18:00", "offhour_pods": 1, "weekend_pods": 1}

    def _save_greenops(self, cfg: dict):
        import json as _json
        self.STATE_DIR.mkdir(parents=True, exist_ok=True)
        (self.STATE_DIR / "greenops_config.json").write_text(
            _json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _save_greenops_and_apply(self):
        cfg = {
            "enabled":      self._go_enabled.isChecked(),
            "start":        self._go_start.time().toString("HH:mm"),
            "end":          self._go_end.time().toString("HH:mm"),
            "offhour_pods": self._go_offhour.value(),
            "weekend_pods": self._go_weekend.value(),
        }
        self._save_greenops(cfg)
        self._go_status_lbl.setText("Kaydedildi. Bir sonraki döngüde uygulanacak.")
        threading.Thread(target=self._greenops_check, daemon=True).start()

    def _greenops_check(self):
        import datetime as _dt
        cfg = self._load_greenops()
        if not cfg.get("enabled"):
            QTimer.singleShot(0, lambda: self._go_status_lbl.setText("Durum: GreenOps devre dışı"))
            return
        now = _dt.datetime.now()
        is_weekend = now.weekday() >= 5
        try:
            sh, sm = map(int, cfg["start"].split(":"))
            eh, em = map(int, cfg["end"].split(":"))
            from PyQt6.QtCore import QTime as _QT
            start_t = _dt.time(sh, sm)
            end_t   = _dt.time(eh, em)
        except Exception:
            start_t = _dt.time(9, 0)
            end_t   = _dt.time(18, 0)
        in_hours = start_t <= now.time() <= end_t
        if is_weekend:
            target = cfg.get("weekend_pods", 1)
            reason = "Hafta sonu"
        elif not in_hours:
            target = cfg.get("offhour_pods", 1)
            reason = "Mesai dışı"
        else:
            msg = f"Durum: Mesai saatleri — KEDA kontrolünde ({now.strftime('%H:%M')})"
            QTimer.singleShot(0, lambda: self._go_status_lbl.setText(msg))
            return
        instance = self.ops.get_instance() or {}
        ns   = instance.get("namespace", "autoscaleops")
        name = self.db.get_setting("active_project_name", "autoscaleops-app")
        # Scale down
        run_ps(f"kubectl scale deployment {name}-deployment --replicas={target} -n {ns} 2>&1")
        run_ps(f"kubectl delete scaledobject --all -n {ns} 2>&1")
        savings = (cfg.get("offhour_pods", 1) - target) * self.COST_PER_POD_HOUR * 8
        msg = f"Durum: {reason} — {target} pod'a ölçeklendi"
        sav = f"Tahmini Tasarruf: ₺{savings:.4f}/gün"
        QTimer.singleShot(0, lambda: self._go_status_lbl.setText(msg))
        QTimer.singleShot(0, lambda: self._go_savings_lbl.setText(sav))

    def _toggle_keda(self):
        self._keda_toggle_result.setText("İşleniyor…")
        keda_ok = self._keda_detail.text() != "—" and "—" not in self._keda_detail.text()
        # Re-check via stored state from last apply
        last_ok = getattr(self, "_last_keda_ok", False)
        def do():
            instance = self.ops.get_instance() or {}
            ns   = instance.get("namespace", "autoscaleops")
            name = self.db.get_setting("active_project_name", "autoscaleops-app")
            if last_ok:
                run_ps(f"kubectl delete scaledobject --all -n {ns} 2>&1")
                run_ps(f"kubectl scale deployment {name}-deployment --replicas=1 -n {ns} 2>&1")
                msg  = "KEDA devre dışı bırakıldı"
                btxt = "KEDA Aktifleştir"
            else:
                chart = Path(__file__).parent / "charts" / "autoscaleops" / "templates" / "keda-scaledobject.yaml"
                if chart.exists():
                    run_ps(f"kubectl apply -f \"{chart}\" -n {ns} 2>&1")
                    msg  = "KEDA aktifleştirildi"
                else:
                    msg  = "ScaledObject YAML bulunamadı"
                btxt = "KEDA Devre Dışı Bırak"
            QTimer.singleShot(0, lambda: self._keda_toggle_result.setText(msg))
            QTimer.singleShot(0, lambda: self._btn_keda_toggle.setText(btxt))
        threading.Thread(target=do, daemon=True).start()

    def _save_metrics_history(self, rps: float, pred: float, pods: int):
        import json as _json, datetime as _dt
        self.STATE_DIR.mkdir(parents=True, exist_ok=True)
        hist_file = self.STATE_DIR / "metrics_history.json"
        history = []
        try:
            if hist_file.exists():
                history = _json.loads(hist_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        history.append({"ts": _dt.datetime.now().isoformat(), "rps": rps, "pred": pred, "pods": pods})
        history = history[-2000:]  # keep last 2000 points (~2.8 hours at 5s interval)
        hist_file.write_text(_json.dumps(history, ensure_ascii=False), encoding="utf-8")

    # ── History Tab ────────────────────────────────────────────────────────
    def _build_history_tab(self) -> QWidget:
        import json as _json, datetime as _dt
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Top controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Zaman Aralığı:"))
        self._hist_combo = QComboBox()
        self._hist_combo.addItems(["1 Gün", "3 Gün", "7 Gün", "14 Gün", "30 Gün"])
        self._hist_combo.setFixedWidth(110)
        ctrl.addWidget(self._hist_combo)
        ctrl.addSpacing(8)
        btn_refresh = QPushButton("↻ Yenile")
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self._refresh_history)
        ctrl.addWidget(btn_refresh)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        # Matplotlib canvas
        self._hist_has_mpl = False
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _Canvas
            from matplotlib.figure import Figure as _Figure
            _bg = "#0C0C1E"
            self._hist_fig = _Figure(figsize=(10, 3), dpi=96)
            self._hist_fig.patch.set_facecolor(_bg)
            self._hist_ax = self._hist_fig.add_subplot(111)
            self._hist_ax.set_facecolor(_bg)
            self._hist_ax.grid(True, alpha=0.25, linestyle="--")
            for sp in self._hist_ax.spines.values():
                sp.set_color("#28285A")
            self._hist_ln_rps,  = self._hist_ax.plot([], [], color="#818CF8", linewidth=2, label="Gerçek RPS")
            self._hist_ln_pred, = self._hist_ax.plot([], [], color="#A78BFA", linewidth=1.4,
                                                      linestyle="--", label="AI Tahmini")
            self._hist_ax.legend(loc="upper left", framealpha=0.0, labelcolor="#F2F4FF", fontsize=9)
            self._hist_ax.set_ylabel("RPS", fontsize=9, color="#5A6A8A")
            self._hist_fig.tight_layout(pad=0.8)
            self._hist_canvas = _Canvas(self._hist_fig)
            self._hist_canvas.setStyleSheet(f"background:{_bg}; border:none;")
            self._hist_canvas.setMinimumHeight(220)
            lay.addWidget(self._hist_canvas, stretch=1)
            self._hist_canvas.draw()
            self._hist_has_mpl = True
        except Exception:
            lay.addWidget(QLabel("Grafik için: pip install matplotlib"))

        # Stats label
        self._hist_stats = QLabel("Veri yükleniyor...")
        self._hist_stats.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; padding:4px 0;")
        lay.addWidget(self._hist_stats)

        # Connect combo — initial load deferred so window is ready
        self._hist_combo.currentIndexChanged.connect(lambda idx: self._refresh_history())
        QTimer.singleShot(300, self._refresh_history)
        return w

    def _refresh_history(self):
        try:
            self._do_refresh_history()
        except Exception as e:
            try:
                self._hist_stats.setText(f"Geçmiş yüklenemedi: {e}")
            except Exception:
                pass

    def _do_refresh_history(self):
        import json as _json, datetime as _dt
        days_map = [1, 3, 7, 14, 30]
        idx = self._hist_combo.currentIndex()
        days = days_map[idx] if 0 <= idx < len(days_map) else 1

        hist_file = self.STATE_DIR / "metrics_history.json"
        records = []
        try:
            if hist_file.exists():
                records = _json.loads(hist_file.read_text(encoding="utf-8"))
                if not isinstance(records, list):
                    records = []
        except Exception:
            records = []

        cutoff = _dt.datetime.now() - _dt.timedelta(days=days)
        filtered = []
        for r in records:
            try:
                ts_str = r.get("ts", "")
                # strip timezone info if present so comparison works
                ts_str = ts_str[:26].replace("Z", "")
                if _dt.datetime.fromisoformat(ts_str) >= cutoff:
                    filtered.append(r)
            except Exception:
                pass
        records = filtered

        if not records:
            self._hist_stats.setText("Bu aralıkta veri yok — Dashboard açıkken otomatik kaydedilir.")
            if self._hist_has_mpl:
                self._hist_ln_rps.set_data([], [])
                self._hist_ln_pred.set_data([], [])
                self._hist_ax.set_xlim(0, 1)
                self._hist_ax.set_ylim(0, 10)
                self._hist_canvas.draw_idle()
            return

        xs = list(range(len(records)))
        rps_vals  = [float(r.get("rps",  0.0)) for r in records]
        pred_vals = [float(r.get("pred", 0.0)) for r in records]

        avg_rps  = sum(rps_vals) / len(rps_vals)
        peak_rps = max(rps_vals)
        min_rps  = min(rps_vals)
        self._hist_stats.setText(
            f"Ort RPS: {avg_rps:.2f}  •  Tepe: {peak_rps:.2f}  •  Min: {min_rps:.2f}  •  {len(records)} veri noktası"
        )

        if self._hist_has_mpl:
            self._hist_ln_rps.set_data(xs, rps_vals)
            self._hist_ln_pred.set_data(xs, pred_vals)
            self._hist_ax.set_xlim(0, max(xs) if xs else 1)
            all_y = rps_vals + pred_vals
            mn, mx = min(all_y), max(all_y)
            pad = max((mx - mn) * 0.1, 0.5)
            self._hist_ax.set_ylim(max(0, mn - pad), mx + pad)
            self._hist_canvas.draw_idle()

    # ── Technical Tab ──────────────────────────────────────────────────────
    def _build_technical_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Refresh button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ref = QPushButton("↻ Yenile")
        btn_ref.setFixedWidth(100)
        btn_ref.clicked.connect(self._refresh_technical)
        btn_row.addWidget(btn_ref)
        lay.addLayout(btn_row)

        def _section(title):
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color:{C_ACCENT}; font-size:12px; font-weight:600; padding:4px 0 2px;")
            lay.addWidget(lbl)
            te = QTextEdit()
            te.setReadOnly(True)
            te.setStyleSheet(
                f"background:{C_SURFACE}; color:{C_TEXT}; font-family:Consolas,monospace; "
                f"font-size:11px; border:1px solid #28285A; border-radius:6px; padding:6px;"
            )
            te.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
            lay.addWidget(te)
            return te

        self._tech_pods   = _section("Pod Durumu")
        self._tech_pods.setMaximumHeight(150)
        self._tech_keda   = _section("KEDA ScaledObject")
        self._tech_keda.setMaximumHeight(90)
        self._tech_events = _section("Son Kubernetes Olayları")
        self._tech_events.setMaximumHeight(200)
        self._tech_log    = _section("Aktivite Logu")
        self._tech_log.setMaximumHeight(200)

        self._refresh_technical()
        return w

    def _refresh_technical(self):
        def do():
            instance = self.ops.get_instance()
            ns = instance.get("namespace", "autoscaleops") if instance else "autoscaleops"

            # Pods
            _, pods_out = run_ps(f"kubectl get pods -n {ns} -o wide --no-headers 2>&1", timeout=12)
            # KEDA ScaledObject
            _, keda_out = run_ps(f"kubectl get scaledobject -n {ns} --no-headers 2>&1", timeout=12)
            # Events (last 15)
            _, ev_out   = run_ps(
                f"kubectl get events -n {ns} --sort-by=.lastTimestamp --no-headers 2>&1", timeout=12
            )
            ev_lines = ev_out.strip().splitlines()[-15:]
            ev_out   = "\n".join(ev_lines)

            # Activity log from DB
            logs = self.db.get_activity_log(limit=40)
            log_lines = []
            for entry in reversed(logs):
                ts   = entry.get("timestamp", "")[:19]
                etype = entry.get("event_type", "")
                desc  = entry.get("description", "")
                log_lines.append(f"[{ts}] {etype:<14} {desc}")
            log_out = "\n".join(log_lines) if log_lines else "(henüz aktivite yok)"

            QTimer.singleShot(0, lambda: self._tech_pods.setPlainText(pods_out or "(sonuç yok)"))
            QTimer.singleShot(0, lambda: self._tech_keda.setPlainText(keda_out or "(sonuç yok)"))
            QTimer.singleShot(0, lambda: self._tech_events.setPlainText(ev_out or "(sonuç yok)"))
            QTimer.singleShot(0, lambda: self._tech_log.setPlainText(log_out))

        import threading
        threading.Thread(target=do, daemon=True).start()

    # ── External update hooks (called from MainWindow workers) ─────────────
    def update_metrics(self, data: dict):
        """MetricsPoller'dan gelen anlık veri ile kart güncelle."""
        rps  = data.get("rps", 0.0)
        pods = data.get("pod_count", 0)
        pred = data.get("predicted_rps", 0.0)
        cost = pods * self.COST_PER_POD_HOUR
        eff  = (rps / pods) if pods > 0 else 0.0
        self._mc_rps.set_value(f"{rps:.1f}")
        self._mc_pods.set_value(str(pods))
        if pred:
            self._mc_pred.set_value(f"{pred:.1f}", f"Δ {pred-rps:+.1f}")
        self._mc_cost.set_value(f"₺{cost:.3f}")
        self._mc_eff.set_value(f"{eff:.1f}" if pods else "—")

    def update_service(self, name: str, up: bool):
        """ServiceWatcher'dan gelen durum güncellemesi."""
        key_map = {"prometheus": "prometheus", "pushgateway": "pushgw", "app": "app"}
        key = key_map.get(name)
        if key and key in self._svc_rows:
            dot, slbl = self._svc_rows[key]
            dot.setStyleSheet(
                f"color:{C_GREEN}; font-size:9px; background:transparent; border:none;"
                if up else
                f"color:{C_RED}; font-size:9px; background:transparent; border:none;"
            )
            slbl.setText("Bağlı" if up else "Çevrimdışı")


# ─────────────────────────────────────────────
#  SCREEN 2 — MAIN APPLICATION WINDOW
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    # Worker thread'lerden main thread'e cluster durumu iletmek için
    _cluster_status_signal   = pyqtSignal(bool)
    _predictor_alert_signal  = pyqtSignal(str)   # predictor watchdog uyarısı

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db = db
        self.ops = ops
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Sidebar
        self._sidebar = self._build_sidebar()
        root_lay.addWidget(self._sidebar)

        # Right side: top bar + content
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)
        self._topbar = self._build_topbar()
        right_lay.addWidget(self._topbar)
        # Bildirim banner'ı (topbar altında, content üstünde)
        self._banner = NotificationBanner()
        right_lay.addWidget(self._banner)
        # Content stack
        self._content_stack = QStackedWidget()
        right_lay.addWidget(self._content_stack)
        root_lay.addWidget(right)

        # Build panels  — index sırası:
        #   0:Ana Sayfa  1:Dashboard  2:Aktivite
        #   3:Sorun Gider  4:Ayarlar  5:Deploy  6:AI Profil
        self._home_panel      = HomePanel(db, ops)
        self._dashboard_panel = DashboardPanel(db, ops)
        self._activity_panel  = ActivityLogPanel(db)
        self._trouble_panel   = TroubleshooterPanel(db, ops)
        self._settings_panel  = SettingsPanel(db, ops)
        self._deploy_panel    = DeployPanel(db, ops)
        self._ai_profile_panel = AiProfilePanel(db, ops)

        for panel in [self._home_panel, self._dashboard_panel,
                      self._activity_panel, self._trouble_panel,
                      self._settings_panel, self._deploy_panel,
                      self._ai_profile_panel]:
            self._content_stack.addWidget(panel)

        # Connect home cluster buttons
        self._home_panel.request_cluster_action.connect(self._handle_cluster_action)
        # Deploy kısayolu — HomePanel'den direkt Deploy paneline git
        self._home_panel.navigate_to.connect(self._nav_select)
        # Connect deploy panel navigation
        self._deploy_panel.navigate_request.connect(self._handle_cluster_action)
        # Dil değişikliği → nav butonlarını güncelle
        self._settings_panel.language_changed.connect(self._apply_language)

        # Workers setup
        self._setup_workers()
        self._nav_select(0)

        # Başlangıç bildirimi — kullanıcıya sonraki adımı göster
        QTimer.singleShot(800, self._show_startup_banner)

    def show_banner(self, message: str, level: str = "info", auto_dismiss_ms: int = 0):
        """Dışarıdan banner göstermek için public metod."""
        self._banner.show_message(message, level=level, auto_dismiss_ms=auto_dismiss_ms)

    def _show_startup_banner(self):
        """Uygulama açılışında duruma göre bildirim göster."""
        try:
            cluster_running = getattr(self.ops, '_cluster_running', False)
        except Exception:
            cluster_running = False

        if not cluster_running:
            self._banner.show_message(
                "Cluster henüz başlatılmadı. Ana Sayfa'dan 'Cluster Başlat' butonuna tıkla.",
                level="warning"
            )
        else:
            self._banner.show_message(
                "Cluster çalışıyor. Dashboard'dan metrikleri takip edebilirsin.",
                level="success",
                auto_dismiss_ms=5000
            )

    # ── Dil uygula ────────────────────────────
    @pyqtSlot(str)
    def _apply_language(self, lang_code: str):
        """Dil değiştiğinde navigasyon butonlarını anında güncelle."""
        nav_keys = [
            "nav.home", "nav.dashboard", "nav.activity",
            "nav.troubleshoot", "nav.settings", "nav.deploy", "nav.ai_profile",
        ]
        icons = ["⊙", "▦", "≡", "⚙", "◇", "△", "✦"]
        for i, (btn, key, icon) in enumerate(zip(self._nav_buttons, nav_keys, icons)):
            btn.setText(f"  {icon}   {t(key)}")

    # ── Sidebar ───────────────────────────────
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"""
            QWidget {{
                background-color: {C_SIDEBAR};
                border-right: 1px solid rgba(255,255,255,8);
            }}
        """)
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Logo area ───────────────────────────────────────────────────────
        logo_w = QWidget()
        logo_w.setFixedHeight(60)
        logo_w.setStyleSheet(f"""
            background: transparent;
            border-bottom: 1px solid rgba(255,255,255,6);
        """)
        logo_lay = QHBoxLayout(logo_w)
        logo_lay.setContentsMargins(20, 0, 16, 0)

        # Kare ikon kutusu
        icon_box = QLabel("A")
        icon_box.setFixedSize(28, 28)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #9BA8FA, stop:1 {C_ACCENT2});
            color: #fff;
            font-size: 13px;
            font-weight: 700;
            border-radius: 8px;
            border: none;
        """)

        logo_lbl = QLabel("AutoScaleOps")
        logo_lbl.setStyleSheet(
            f"color:{C_TEXT}; font-size:13px; font-weight:700; "
            f"background:transparent; border:none; letter-spacing:0.2px;"
        )
        logo_lay.addWidget(icon_box)
        logo_lay.addSpacing(8)
        logo_lay.addWidget(logo_lbl)
        logo_lay.addStretch()
        lay.addWidget(logo_w)
        lay.addSpacing(10)

        # ── Nav items ───────────────────────────────────────────────────────
        # 0:Ana Sayfa  1:Dashboard  2:Aktivite  3:Sorun Gider  4:Ayarlar  5:Deploy  6:AI Profil
        nav_items = [
            (t("nav.home"),         "⊙"),
            (t("nav.dashboard"),    "▦"),
            (t("nav.activity"),     "≡"),
            (t("nav.troubleshoot"), "⚙"),
            (t("nav.settings"),     "◇"),
            (t("nav.deploy"),       "△"),
            (t("nav.ai_profile"),   "✦"),
        ]
        self._nav_buttons = []
        nav_container = QWidget()
        nav_container.setStyleSheet("background:transparent; border:none;")
        nav_lay = QVBoxLayout(nav_container)
        nav_lay.setContentsMargins(12, 0, 12, 0)
        nav_lay.setSpacing(2)
        for i, (name, icon) in enumerate(nav_items):
            btn = QPushButton(f"  {icon}   {name}")
            btn.setFixedHeight(40)
            btn.setCheckable(True)
            btn.setStyleSheet(self._nav_btn_style(False))
            btn.clicked.connect(lambda checked, idx=i: self._nav_select(idx))
            nav_lay.addWidget(btn)
            self._nav_buttons.append(btn)
        lay.addWidget(nav_container)
        lay.addStretch()

        # ── Alt alan: versiyon ──────────────────────────────────────────────
        bottom_line = QFrame()
        bottom_line.setFixedHeight(1)
        bottom_line.setStyleSheet(f"background: rgba(255,255,255,6); border:none;")
        lay.addWidget(bottom_line)

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:10px; padding:8px 20px; "
            f"background:transparent; border:none;"
        )
        lay.addWidget(ver_lbl)
        return sidebar

    def _nav_btn_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: rgba(99,102,241,0.14);
                    color: {C_ACCENT};
                    border: none;
                    border-left: 2px solid {C_ACCENT};
                    border-radius: 10px;
                    font-size: 12px;
                    font-weight: 600;
                    text-align: left;
                    padding-left: 12px;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent;
                color: {C_TEXT_DIM};
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 400;
                text-align: left;
                padding-left: 14px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,4);
                color: {C_TEXT};
            }}
        """

    def _nav_select(self, idx: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == idx)
            btn.setStyleSheet(self._nav_btn_style(i == idx))
        self._content_stack.setCurrentIndex(idx)

    # ── Top Bar ───────────────────────────────
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"""
            background: {C_BG};
            border-bottom: 1px solid rgba(255,255,255,7);
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        # Cluster durumu
        self._cluster_dot = StatusDot(C_RED)
        self._cluster_status_bar_lbl = QLabel("Cluster durduruldu")
        self._cluster_status_bar_lbl.setStyleSheet(
            f"color:{C_RED}; font-weight:600; font-size:12px;"
        )
        lay.addWidget(self._cluster_dot)
        lay.addSpacing(4)
        lay.addWidget(self._cluster_status_bar_lbl)
        lay.addStretch()

        # Canlı metrikler
        self._bar_rps_lbl = QLabel("RPS  —")
        self._bar_rps_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self._bar_pods_lbl = QLabel("Pod  —")
        self._bar_pods_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")

        # İnce dikey ayırıcı
        def _vsep():
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setFixedHeight(18)
            s.setStyleSheet("color: rgba(255,255,255,12); background: rgba(255,255,255,12); border:none;")
            return s

        lay.addWidget(self._bar_rps_lbl)
        lay.addWidget(_vsep())
        lay.addWidget(self._bar_pods_lbl)
        lay.addWidget(_vsep())

        # Avatar + kullanıcı adı (tıklanınca menü açılır)
        self._topbar_avatar = QLabel()
        self._topbar_avatar.setFixedSize(30, 30)
        self._topbar_avatar.setStyleSheet(
            f"border-radius:15px; background:{C_ACCENT2}; color:#fff; "
            f"font-weight:700; font-size:12px;"
        )
        self._topbar_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._topbar_name = QLabel("Kullanıcı")
        self._topbar_name.setStyleSheet(f"color:{C_TEXT}; font-size:12px;")

        # Chevron butonu
        self._topbar_btn = QToolButton()
        self._topbar_btn.setText("›")
        self._topbar_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                color: {C_TEXT_DIM};
                font-size: 16px;
                padding: 0;
            }}
            QToolButton:hover {{ color: {C_TEXT}; }}
        """)
        self._topbar_btn.clicked.connect(self._show_user_menu)

        lay.addWidget(self._topbar_avatar)
        lay.addSpacing(4)
        lay.addWidget(self._topbar_name)
        lay.addWidget(self._topbar_btn)
        return bar

    def _show_user_menu(self):
        menu = QMenu(self)
        menu.addAction("Ayarlar", lambda: self._nav_select(4))
        menu.addSeparator()
        menu.addAction("Çıkış", self._logout)
        menu.exec(QCursor.pos())

    def _logout(self):
        reply = QMessageBox.question(self, "Çıkış",
                                     "Oturumu kapatmak istediğinizden emin misiniz?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.log_activity("logout", "Kullanıcı oturumu kapattı")
            self.hide()
            if self.parent():
                self.parent()._show_main_app_and_check() if hasattr(self.parent(), '_show_main_app_and_check') else None

    def load_user(self):
        user = self.db.get_user()
        if not user:
            return
        name = user.get("name", "User")
        self._topbar_name.setText(name)
        initials = "".join(part[0].upper() for part in name.split()[:2])
        avatar_path = user.get("avatar_path")
        if avatar_path and __import__("pathlib").Path(avatar_path).exists():
            pix = QPixmap(avatar_path).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self._topbar_avatar.setPixmap(make_circular_pixmap(pix, 32))
        else:
            self._topbar_avatar.setText(initials)

    # ── Workers ───────────────────────────────
    def _setup_workers(self):
        # Hardware monitor
        # QTimer MUST be created inside the target thread (via started signal),
        # not in the main thread and then moved — that causes QObject::setParent errors.
        self._hw_thread = QThread(self)
        self._hw_monitor = HardwareMonitor(self.db)
        self._hw_monitor.moveToThread(self._hw_thread)
        self._hw_monitor.snapshot.connect(self._on_hw_snapshot)
        def _start_hw_timer():
            self._hw_timer = QTimer()
            self._hw_timer.timeout.connect(self._hw_monitor.collect)
            self._hw_timer.start(30000)
        self._hw_thread.started.connect(_start_hw_timer)
        self._hw_thread.start()
        # Immediate first collection
        QTimer.singleShot(2000, self._hw_monitor.collect)

        # Metrics poller
        self._metrics_thread = QThread(self)
        self._metrics_poller = MetricsPoller(self.ops)
        self._metrics_poller.moveToThread(self._metrics_thread)
        self._metrics_poller.metrics.connect(self._on_metrics)
        def _start_metrics_timer():
            self._metrics_poll_timer = QTimer()
            self._metrics_poll_timer.timeout.connect(self._metrics_poller.poll)
            self._metrics_poll_timer.start(5000)
        self._metrics_thread.started.connect(_start_metrics_timer)
        self._metrics_thread.start()
        QTimer.singleShot(3000, self._metrics_poller.poll)

        # Service watcher
        self._svc_thread = QThread(self)
        self._svc_watcher = ServiceWatcher(self.ops)
        self._svc_watcher.moveToThread(self._svc_thread)
        self._svc_watcher.service_status.connect(self._on_service_status)
        def _start_svc_timer():
            self._svc_timer = QTimer()
            self._svc_timer.timeout.connect(self._svc_watcher.check)
            self._svc_timer.start(10000)
        self._svc_thread.started.connect(_start_svc_timer)
        self._svc_thread.start()
        QTimer.singleShot(5000, self._svc_watcher.check)

        # Activity refresh timer
        self._activity_timer = QTimer()
        self._activity_timer.timeout.connect(self._home_panel.refresh_activity)
        self._activity_timer.start(30000)
        QTimer.singleShot(1000, self._home_panel.refresh_activity)

        # Cluster status poller
        self._cluster_status_timer = QTimer()
        self._cluster_status_timer.timeout.connect(self._poll_cluster_status)
        self._cluster_status_timer.start(15000)
        QTimer.singleShot(1000, self._poll_cluster_status)

        self._cluster_worker_thread = None
        self._cluster_worker = None

        # Cluster status sinyalini main thread slot'una bağla
        self._cluster_status_signal.connect(
            self._update_cluster_ui, Qt.ConnectionType.QueuedConnection
        )
        # Predictor watchdog uyarısı
        self._predictor_alert_signal.connect(
            self._on_predictor_alert, Qt.ConnectionType.QueuedConnection
        )

        # ── ARIMA Predictor watchdog ─────────────────────────────────────────
        # İlk başlatma: 8 sn sonra
        # Watchdog: her 2 dk'da bir predictor sağlığını kontrol eder,
        # çökmüşse sessizce yeniden başlatır.
        self._predictor_proc: Optional[subprocess.Popen] = None
        self._predictor_miss_count: int = 0   # kaç kontrol periyodundur tahmin yok
        QTimer.singleShot(8000, self._start_predictor_if_needed)
        self._predictor_watchdog = QTimer(self)
        self._predictor_watchdog.timeout.connect(self._check_predictor_health)
        self._predictor_watchdog.start(120_000)   # her 2 dakika

    def _start_predictor_if_needed(self):
        """
        ARIMA predictor'ı arka planda başlatır.
        Süreç referansını self._predictor_proc'da saklar (watchdog için).
        """
        import threading, subprocess, sys
        from pathlib import Path as _Path

        predictor_path = _Path(__file__).parent / "ai-model" / "predictor.py"
        if not predictor_path.exists():
            return

        # Zaten canlı bir süreç var mı?
        if self._predictor_proc and self._predictor_proc.poll() is None:
            return

        # Pushgateway erişilebilir mi?
        try:
            import requests as _req
            r = _req.get("http://127.0.0.1:9091/metrics", timeout=2)
            if r.status_code != 200:
                return
        except Exception:
            return

        def _run():
            try:
                import os as _os
                env = _os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                proc = subprocess.Popen(
                    [sys.executable, str(predictor_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                )
                self._predictor_proc = proc
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def _check_predictor_health(self):
        """
        Her 2 dakikada bir predictor sağlığını kontrol eder.
        Prometheus'ta predicted_rps_30min yoksa veya süreç ölmüşse yeniden başlatır.
        3 ardışık başarısız kontrolden sonra kullanıcıya uyarı toast gösterir.
        """
        import threading

        def _check():
            alive = (self._predictor_proc is not None and
                     self._predictor_proc.poll() is None)
            try:
                import requests as _req
                r = _req.get("http://127.0.0.1:9090/api/v1/query",
                             params={"query": "predicted_rps_30min"}, timeout=3)
                has_metric = bool(r.json().get("data", {}).get("result", []))
            except Exception:
                has_metric = False

            if not alive or not has_metric:
                self._predictor_miss_count += 1
                self._start_predictor_if_needed()
                if self._predictor_miss_count >= 3:
                    # Ana thread'e uyarı gönder
                    self._predictor_alert_signal.emit(
                        f"Tahmin motoru yanit vermiyor ({self._predictor_miss_count}x). "
                        "Yeniden baslatildi."
                    )
            else:
                self._predictor_miss_count = 0

        threading.Thread(target=_check, daemon=True).start()

    @pyqtSlot(str)
    def _on_predictor_alert(self, msg: str):
        """Predictor watchdog uyarısını status bar'da göster."""
        self.statusBar().showMessage(f"⚠ Tahmin Motoru: {msg}", 10000)

    @pyqtSlot(dict)
    def _on_hw_snapshot(self, data: dict):
        self._home_panel.update_hardware(data)

    @pyqtSlot(dict)
    def _on_metrics(self, data: dict):
        rps = data.get("rps", 0.0)
        pods = data.get("pod_count", 0)
        self._bar_rps_lbl.setText(f"RPS  {rps:.1f}")
        self._bar_pods_lbl.setText(f"Pod  {pods}")
        self._home_panel.update_metrics(data)
        self._dashboard_panel.update_metrics(data)

    @pyqtSlot(str, bool)
    def _on_service_status(self, name: str, up: bool):
        self._dashboard_panel.update_service(name, up)

    def _poll_cluster_status(self):
        def check():
            status = self.ops.get_cluster_status()
            running = status.get("running", False)
            # main thread'e sinyal yolla — UI'ya dokunma
            self._cluster_status_signal.emit(running)
        threading.Thread(target=check, daemon=True).start()

    def _update_cluster_ui(self, running: bool):
        color = C_GREEN if running else C_RED
        text = "Cluster çalışıyor" if running else "Cluster durduruldu"
        self._cluster_dot.set_color(color)
        self._cluster_status_bar_lbl.setText(text)
        self._cluster_status_bar_lbl.setStyleSheet(f"color:{color}; font-weight:600; font-size:12px;")
        self._home_panel.update_cluster_status(running)
        if hasattr(self, "_tray"):
            self._tray.update_cluster_state(running)
        # Banner bildirimi
        if hasattr(self, "_banner"):
            if running:
                self._banner.show_message(
                    "Cluster başarıyla çalışıyor. Dashboard'dan metrikleri takip edebilirsin.",
                    level="success", auto_dismiss_ms=6000
                )
            else:
                self._banner.show_message(
                    "Cluster durduruldu. Tekrar başlatmak için Ana Sayfa'ya git.",
                    level="warning"
                )

    # ── Cluster actions ───────────────────────
    @pyqtSlot(str)
    def _handle_cluster_action(self, action: str):
        # Navigation helpers emitted from HomePanel / DeployPanel
        # Index sırası: 0:Ana Sayfa  1:Dashboard  2:Aktivite
        #               3:Sorun Gider  4:Ayarlar  5:Deploy
        if action in ("_nav_system", "_nav_dashboard"):
            self._nav_select(1)   # Dashboard
            return
        if action == "_nav_activity":
            self._nav_select(2)
            return
        if action == "_nav_tunnel":
            self._nav_select(4)   # Ayarlar'a yönlendir
            return
        if action == "_nav_home":
            self._nav_select(0)
            return
        if action == "_nav_deploy_mgr":
            self._nav_select(5)   # Deploy
            # DeployPanel Proje Yönetimi sekmesini aç (index 1)
            if hasattr(self._deploy_panel, '_project_list'):
                for child in self._deploy_panel.findChildren(QTabWidget):
                    child.setCurrentIndex(1)
                    break
            return
        if self._cluster_worker_thread and self._cluster_worker_thread.isRunning():
            QMessageBox.information(self, "Busy", "A cluster operation is already in progress.")
            return
        self._cluster_worker_thread = QThread(self)
        self._cluster_worker = ClusterWorker(self.ops, action)
        self._cluster_worker.moveToThread(self._cluster_worker_thread)
        self._cluster_worker_thread.started.connect(self._cluster_worker.run)
        self._cluster_worker.progress.connect(self._on_cluster_progress)
        self._cluster_worker.finished.connect(self._on_cluster_done)
        self._cluster_worker.finished.connect(self._cluster_worker_thread.quit)
        self._cluster_worker_thread.start()

        # Update UI to "working" state
        action_tr = "başlatılıyor" if action == "start" else "durduruluyor"
        self._cluster_dot.set_color(C_YELLOW)
        self._cluster_status_bar_lbl.setText(f"Cluster {action_tr}...")
        self._cluster_status_bar_lbl.setStyleSheet(f"color:{C_YELLOW}; font-weight:600; font-size:12px;")

    @pyqtSlot(str, str)
    def _on_cluster_progress(self, msg: str, level: str):
        pass  # Could update a progress widget if needed

    @pyqtSlot(bool, str)
    def _on_cluster_done(self, ok: bool, msg: str):
        if ok:
            self._show_notification("AutoScaleOps", msg)
        else:
            self._show_notification("AutoScaleOps Error", msg)
        QTimer.singleShot(2000, self._poll_cluster_status)

    def _show_notification(self, title: str, msg: str):
        if hasattr(self, "_tray_icon") and self.db.get_setting("notifications_enabled", "true") == "true":
            self._tray_icon.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 4000)

    # ── Close / tray behavior ─────────────────
    def closeEvent(self, event):
        minimize_to_tray = self.db.get_setting("minimize_to_tray", "true") == "true"
        if minimize_to_tray and hasattr(self, "_tray_icon") and self._tray_icon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self._tray_icon.showMessage(
                APP_NAME,
                "AutoScaleOps arka planda çalışmaya devam ediyor.",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
        else:
            # Kapatma dialogunu göster
            dlg = ShutdownDialog(self)
            result = dlg.exec()
            if result != QDialog.DialogCode.Accepted:
                event.ignore()  # İptal
                return
            choice = dlg.choice
            if choice == "full":
                run_ps(
                    "Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue "
                    "| Stop-Process -Force 2>&1"
                )
            self._cleanup()
            event.accept()

    def _cleanup(self):
        for attr in ["_hw_thread", "_metrics_thread", "_svc_thread"]:
            t = getattr(self, attr, None)
            if t and t.isRunning():
                t.quit()
                t.wait(1000)
        self.ops.cleanup()

    def set_tray_icon(self, tray_icon):
        self._tray_icon = tray_icon



# ─────────────────────────────────────────────
#  SYSTEM TRAY
# ─────────────────────────────────────────────
class TrayIcon(QSystemTrayIcon):
    show_app = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, ops, parent=None):
        super().__init__(parent)
        self.ops = ops
        self._cluster_running = False

        # Icon (create a simple colored icon if no file)
        icon_path = ASSETS_DIR / "icon.ico"
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            pix = QPixmap(32, 32)
            pix.fill(QColor(C_ACCENT))
            self.setIcon(QIcon(pix))

        self.setToolTip(APP_NAME)
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        title_action = menu.addAction(APP_NAME)
        title_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Uygulamayı Aç", lambda: self.show_app.emit())
        menu.addAction("Dashboard Aç", lambda: webbrowser.open("http://localhost:8501"))
        menu.addSeparator()
        self._start_action = menu.addAction("Cluster Başlat", self._start_cluster)
        self._stop_action = menu.addAction("Cluster Durdur", self._stop_cluster)
        menu.addSeparator()
        self._status_action = menu.addAction("Durum: Cluster Durduruldu")
        self._status_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Çıkış", lambda: self.quit_app.emit())
        self.setContextMenu(menu)

    def update_cluster_state(self, running: bool):
        self._cluster_running = running
        self._start_action.setEnabled(not running)
        self._stop_action.setEnabled(running)
        durum = "Çalışıyor" if running else "Durduruldu"
        self._status_action.setText(f"Durum: Cluster {durum}")

    def _start_cluster(self):
        import threading
        threading.Thread(target=lambda: self.ops.start_cluster(), daemon=True).start()

    def _stop_cluster(self):
        import threading
        threading.Thread(target=lambda: self.ops.stop_cluster(), daemon=True).start()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_app.emit()


# ─────────────────────────────────────────────
#  APPLICATION CONTROLLER
# ─────────────────────────────────────────────
class AppController(QObject):
    def __init__(self):
        super().__init__()
        self.db = AppDatabase()
        self.ops = SystemOps(self.db)
        self.instance = None

        # Kaydedilen dili global değişkene yükle (tüm t() çağrıları için)
        global _APP_LANG
        _APP_LANG = self.db.get_setting("language", "tr")

        # Main stack window
        self._win = QMainWindow()
        self._win.setWindowTitle(APP_NAME)
        self._win.setMinimumSize(900, 600)
        self._win.resize(1000, 680)
        # Pencereyi ekranin ortasinda ac
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self._win.move(
                sg.center().x() - 500,
                sg.center().y() - 340
            )

        self._stack = QStackedWidget()
        self._win.setCentralWidget(self._stack)
        self._win.setStyleSheet(STYLESHEET)

        # Screen 0: Splash
        self._splash = SplashScreen()
        self._stack.addWidget(self._splash)  # index 0

        # Screen 1: Setup Wizard (placeholder — created when needed)
        self._wizard = None
        self._wizard_placeholder = QWidget()
        self._stack.addWidget(self._wizard_placeholder)  # index 1

        # Screen 2: Main window (placeholder)
        self._main_app = None
        self._main_placeholder = QWidget()
        self._stack.addWidget(self._main_placeholder)  # index 2

        self._stack.setCurrentIndex(0)

        # Tray
        self._tray = TrayIcon(self.ops, self._win)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show_app.connect(self._show_main)
            self._tray.quit_app.connect(self._quit_app)
            self._tray.show()

        # Init timer
        self._init_timer = QTimer()
        self._init_timer.setSingleShot(True)
        self._init_timer.timeout.connect(self._init_app)
        self._init_timer.start(1500)

    def show(self):
        self._win.show()
        self._win.raise_()
        self._win.activateWindow()

    def _init_app(self):
        self._splash.set_status("Sistem kontrol ediliyor...")
        try:
            self.instance = self.ops.ensure_instance()
        except Exception:
            self.instance = None

        if SETUP_COMPLETE_PATH.exists():
            self._splash.set_status("Uygulama yukleniyor...")
            QTimer.singleShot(500, self._show_main_app_and_check)
        else:
            self._splash.set_status("Ilk kurulum baslatiliyor...")
            QTimer.singleShot(500, self._show_wizard)

    def _show_wizard(self):
        if self._wizard is None:
            self._wizard = SetupWizard(self.db, self.ops)
            self._wizard.wizard_done.connect(self._on_wizard_done)
            # Replace placeholder
            self._stack.removeWidget(self._wizard_placeholder)
            self._wizard_placeholder.deleteLater()
            self._stack.insertWidget(1, self._wizard)
        self._stack.setCurrentIndex(1)

    def _on_wizard_done(self):
        self._show_main_app_and_check()

    def _show_main_app_and_check(self):
        self._show_main_app()
        QTimer.singleShot(800, self._post_login_check)

    def _post_login_check(self):
        """PIN girişi sonrası sistem gereksinimlerini kontrol eder."""
        self._prereq_worker = SystemCheckWorker()
        self._prereq_worker.result.connect(self._on_prereq_result)
        self._prereq_worker.start()

    def _on_prereq_result(self, checks: dict):
        # Sadece gercekten kritik olanlari goster (ngrok opsiyonel, atlaniyor)
        CRITICAL_KEYS = {"docker", "minikube", "kubectl", "python_deps"}
        missing = [v["label"] for k, v in checks.items()
                   if k in CRITICAL_KEYS and not v["ok"]]
        if missing and self._main_app:
            QTimer.singleShot(200, lambda: QMessageBox.warning(
                self._main_app,
                "Eksik Gereksinimler",
                f"Bazi bileesenler eksik veya calismıyor:\n\n"
                + "\n".join(f"  * {m}" for m in missing)
                + "\n\nLutfen fix.ps1'i yeniden calistirip kurulumu tamamlayin."
            ))

    def _show_main_app(self):
        if self._main_app is None:
            self._main_app = MainWindow(self.db, self.ops)
            self._main_app.set_tray_icon(self._tray)
            self._stack.removeWidget(self._main_placeholder)
            self._main_placeholder.deleteLater()
            self._stack.insertWidget(2, self._main_app)
        self._main_app.load_user()
        self._stack.setCurrentWidget(self._main_app)

    def _show_main(self):
        self._win.show()
        self._win.raise_()
        self._win.activateWindow()

    def _quit_app(self):
        reply = QMessageBox.question(
            self._win, "AutoScaleOps'tan Cik",
            "Port yonlendirmeleri durdurulsun ve uygulama kapatilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.ops.cleanup()
            self.db.close()
            QApplication.quit()


# ─────────────────────────────────────────────
#  OTOMATİK DANIŞMAN — ProfileAdvisor
# ─────────────────────────────────────────────
class ProfileAdvisor(QObject):
    """
    Arka planda çalışan otomatik danışman.

    Görevleri:
      1. Prometheus'tan saatlik RPS verisi çeker → DB'ye kaydeder
      2. Haftalık örüntü tablosunu günceller (gün × saat matrisi)
      3. Yeterli veri birikince saat ağırlıklarını otomatik hesaplar
      4. domain_profile.json'ı günceller → predictor.py bunu okur

    Çalışma sıklığı: Her 1 saatte bir (3600 saniye)
    Otomatik devreye girme: En az 3 günlük veri birikince
    """

    # Ana pencereye bildirim sinyalleri
    advisor_log     = pyqtSignal(str, str)   # mesaj, seviye ("info"|"ok"|"warn")
    profile_updated = pyqtSignal()           # DB profili değişti → UI slider'ları güncelle

    PROM_URL = "http://127.0.0.1:9090/api/v1/query_range"
    MIN_DAYS_FOR_AUTO = 3    # Otomatik ağırlık için gereken minimum gün sayısı

    def __init__(self, db: 'AppDatabase', ops: 'SystemOps', parent=None):
        super().__init__(parent)
        self.db  = db
        self.ops = ops

    def run_cycle(self) -> None:
        """Bir danışman döngüsü çalıştırır. QThread veya QTimer'dan çağrılır."""
        import threading
        threading.Thread(target=self._cycle_bg, daemon=True).start()

    def _cycle_bg(self) -> None:
        """Arka plan iş parçacığında çalışır."""
        import datetime as _dt, time as _time, requests as _req

        now       = _time.time()
        today_str = _dt.date.today().isoformat()
        midnight  = _dt.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp()

        self.advisor_log.emit("Profil danismani: Prometheus'tan veri cekiliyor...", "info")

        # ── 1. Bugünün saatlik RPS ortalamalarını çek ─────────────────────
        try:
            resp = _req.get(
                self.PROM_URL,
                params={
                    "query": "sum(rate(http_requests_total[10m]))",
                    "start": str(int(midnight)),
                    "end":   str(int(now)),
                    "step":  "3600"
                },
                timeout=10
            )
            data = resp.json()
            saved = 0
            if data.get("status") == "success" and data["data"]["result"]:
                for ts, v in data["data"]["result"][0].get("values", []):
                    hour = _dt.datetime.fromtimestamp(float(ts)).hour
                    rps  = float(v)
                    if rps > 0:
                        self.db.save_hourly_rps(today_str, hour, rps)
                        saved += 1
            if saved:
                self.advisor_log.emit(
                    f"  {saved} saatlik RPS verisi kaydedildi ({today_str})", "ok"
                )
        except Exception as e:
            self.advisor_log.emit(f"  Prometheus hatasi: {e}", "warn")
            return

        # ── 2. Haftalık örüntü tablosunu yeniden hesapla ──────────────────
        self.db.rebuild_weekly_pattern()

        # ── 3. Yeterli veri var mı? ────────────────────────────────────────
        pattern = self.db.get_weekly_pattern()
        if not pattern:
            self.advisor_log.emit("  Henuz haftalik oruntu yok — veri birikmesi bekleniyor.", "info")
            return

        # Kaç farklı gün var?
        import datetime as _dt2
        with self.db._lock:
            cur = self.db.conn.execute(
                "SELECT COUNT(DISTINCT date) FROM hourly_rps_history"
            )
            unique_days = cur.fetchone()[0]

        if unique_days < self.MIN_DAYS_FOR_AUTO:
            self.advisor_log.emit(
                f"  {unique_days}/{self.MIN_DAYS_FOR_AUTO} gun birikmis — "
                f"otomatik agirlik icin {self.MIN_DAYS_FOR_AUTO} gun gerekli.", "info"
            )
            return

        # ── 4. Otomatik ağırlıkları hesapla ve uygula ────────────────────
        auto_weights = self.db.compute_auto_weights()
        if not auto_weights:
            return

        # Mevcut profili al, sadece veri olan saatleri güncelle
        current_profile = self.db.get_traffic_profile()
        updates = {}
        changes = []
        for hour, new_w in auto_weights.items():
            old_w = current_profile.get(hour, {}).get("weight", 1.0)
            # Büyük farklılık varsa (>%15) güncelle
            if abs(new_w - old_w) > 0.15:
                updates[hour] = {"weight": new_w, "label": "auto"}
                changes.append(f"  Saat {hour:02d}: {old_w:.2f} → {new_w:.2f}")

        if updates:
            self.db.set_full_profile({
                h: updates.get(h, {"weight": current_profile.get(h, {}).get("weight", 1.0),
                                   "label":  current_profile.get(h, {}).get("label", "")})
                for h in range(24)
            })
            self.ops.sync_domain_profile()   # predictor.py'ye bildir
            self.profile_updated.emit()      # UI slider'larını güncelle (main thread)
            self.advisor_log.emit(
                f"  Otomatik agirliklar guncellendi ({len(updates)} saat):", "ok"
            )
            for c in changes[:5]:   # En fazla 5 satır göster
                self.advisor_log.emit(c, "info")
            if len(changes) > 5:
                self.advisor_log.emit(f"  ... ve {len(changes)-5} saat daha", "info")
        else:
            self.advisor_log.emit(
                f"  Profil guncel — buyuk degisim yok ({unique_days} gunluk veri).", "ok"
            )


# ─────────────────────────────────────────────
#  AI PROFİL PANELİ
# ─────────────────────────────────────────────
class AiProfilePanel(QWidget):
    """Domain knowledge paneli.

    Üç bölüm:
      1. 24 saatlik yoğunluk haritası (3 katman: canlı, ort., profil)
      2. Saatlik profil düzenleyici (kaydırıcılar)
      3. Etkinlik takvimi
    """
    PROM_URL = "http://127.0.0.1:9090/api/v1/query"

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db  = db
        self.ops = ops
        self._live_rps: dict[int, float] = {}   # saat → ortalama RPS (Prom'dan)
        self._hist_rps: dict[int, float] = {}   # saat → 7 günlük ort. (DB + Prom)

        # Otomatik Danışman
        self._advisor = ProfileAdvisor(db, ops, parent=self)
        self._advisor.advisor_log.connect(self._on_advisor_log,
                                          Qt.ConnectionType.QueuedConnection)
        self._advisor.profile_updated.connect(self.refresh_sliders_from_profile,
                                              Qt.ConnectionType.QueuedConnection)

        self._build_ui()

        # DB'deki geçmiş veriyi hemen yükle (Prometheus açık olmasa bile çalışır)
        QTimer.singleShot(500,  self._load_history_from_db)
        # Prometheus'tan canlı + bugünkü veriyi çek
        QTimer.singleShot(1500, self._refresh_live)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_live)
        self._timer.start(30000)   # Her 30 saniyede güncelle

        # Danışman: ilk çalıştırma 5 dk sonra, sonra her saat
        QTimer.singleShot(300000, self._advisor.run_cycle)
        self._advisor_timer = QTimer(self)
        self._advisor_timer.timeout.connect(self._advisor.run_cycle)
        self._advisor_timer.start(3600000)   # Her 1 saatte bir

    # ── UI ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("AI Profil")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        subtitle = QLabel("Domain knowledge → ARIMA'ya besle")
        subtitle.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; background:transparent; border:none;")
        sync_btn = QPushButton("⟳  Kubernetes'e Gönder")
        sync_btn.setFixedHeight(36)
        sync_btn.setToolTip("Profil ve etkinlikleri ConfigMap olarak Kubernetes'e uygula")
        sync_btn.clicked.connect(self._sync_to_k8s)
        hdr.addWidget(title)
        hdr.addSpacing(12)
        hdr.addWidget(subtitle)
        hdr.addStretch()
        hdr.addWidget(sync_btn)
        lay.addLayout(hdr)

        self._sync_lbl = QLabel("")
        self._sync_lbl.setStyleSheet(f"color:{C_GREEN}; font-size:11px; background:transparent; border:none;")
        lay.addWidget(self._sync_lbl)

        # ── 1. Yoğunluk Haritası ───────────────────────────────────────────
        map_card = self._make_card("24 Saatlik Yoğunluk Haritası")
        map_lay  = map_card.layout()

        # Gösterge
        legend_row = QHBoxLayout()
        for color, label in [("#34D399", "Canlı RPS"), ("#818CF8", "Kullanıcı Profili"), ("#FCD34D", "30 Gün Ort.")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:14px; background:transparent; border:none;")
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; background:transparent; border:none;")
            legend_row.addWidget(dot)
            legend_row.addWidget(lbl)
            legend_row.addSpacing(12)
        legend_row.addStretch()
        map_lay.addLayout(legend_row)

        self._heatmap = _HeatmapWidget(self.db)
        self._heatmap.setMinimumHeight(200)
        map_lay.addWidget(self._heatmap)
        lay.addWidget(map_card)

        # ── 2. Saatlik Profil Düzenleyici ──────────────────────────────────
        prof_card = self._make_card("Saatlik Yoğunluk Profili  (0.1 = çok düşük · 1.0 = normal · 3.0 = çok yüksek)")
        prof_lay  = prof_card.layout()

        grid = QGridLayout()
        grid.setSpacing(6)
        self._sliders: list[QSlider] = []
        self._hour_vals: list[QLabel] = []

        profile = self.db.get_traffic_profile()

        for h in range(24):
            hour_lbl = QLabel(f"{h:02d}")
            hour_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hour_lbl.setFixedWidth(28)
            hour_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; background:transparent; border:none;")

            sl = QSlider(Qt.Orientation.Vertical)
            sl.setRange(1, 30)   # 0.1 → 3.0  (×10)
            sl.setValue(int(round(profile.get(h, {}).get("weight", 1.0) * 10)))
            sl.setFixedHeight(80)
            sl.setFixedWidth(22)
            sl.setStyleSheet(self._slider_style())
            sl.valueChanged.connect(lambda v, hour=h: self._on_slider(hour, v))

            val_lbl = QLabel(f"{sl.value()/10:.1f}")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setFixedWidth(28)
            val_lbl.setStyleSheet(f"color:{C_ACCENT}; font-size:10px; font-weight:600; background:transparent; border:none;")

            col = h
            grid.addWidget(hour_lbl, 0, col, Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(sl,       1, col, Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(val_lbl,  2, col, Qt.AlignmentFlag.AlignHCenter)
            self._sliders.append(sl)
            self._hour_vals.append(val_lbl)

        prof_lay.addLayout(grid)

        reset_btn = QPushButton("Sıfırla (tümünü 1.0)")
        reset_btn.setFixedHeight(30)
        reset_btn.clicked.connect(self._reset_profile)
        prof_lay.addWidget(reset_btn)
        lay.addWidget(prof_card)

        # ── 3. Etkinlik Takvimi ────────────────────────────────────────────
        ev_card = self._make_card("Etkinlik Takvimi  (Yaklaşan etkinliklerde güvenlik marjı uygulanır)")
        ev_lay  = ev_card.layout()

        # Giriş formu
        form = QHBoxLayout()
        self._ev_name  = QLineEdit()
        self._ev_name.setPlaceholderText("Etkinlik adı (örn: Büyük İndirim Günü)")
        self._ev_name.setFixedHeight(34)
        self._ev_date  = QDateEdit()
        self._ev_date.setCalendarPopup(True)
        self._ev_date.setDate(QDate.currentDate().addDays(1))
        self._ev_date.setFixedHeight(34)
        self._ev_date.setFixedWidth(130)
        self._ev_margin = QDoubleSpinBox()
        self._ev_margin.setRange(0.0, 1.0)
        self._ev_margin.setSingleStep(0.05)
        self._ev_margin.setValue(0.30)
        self._ev_margin.setFixedHeight(34)
        self._ev_margin.setFixedWidth(80)
        self._ev_margin.setToolTip("Güvenlik marjı: 0.3 = %30 ekstra kapasite")
        add_btn = QPushButton("+ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self._add_event)
        form.addWidget(self._ev_name, 3)
        form.addWidget(self._ev_date, 1)
        form.addWidget(QLabel("Marj:"), 0)
        form.addWidget(self._ev_margin, 0)
        form.addWidget(add_btn, 0)
        ev_lay.addLayout(form)

        # Etkinlik listesi
        self._ev_list = QListWidget()
        self._ev_list.setMaximumHeight(180)
        self._ev_list.setStyleSheet(f"""
            QListWidget {{
                background: {C_BG};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                color: {C_TEXT};
                font-size: 12px;
            }}
            QListWidget::item {{ padding: 6px 10px; border:none; }}
            QListWidget::item:selected {{ background: {C_SURFACE2}; }}
        """)
        del_btn = QPushButton("Seçili Etkinliği Sil")
        del_btn.setFixedHeight(30)
        del_btn.clicked.connect(self._delete_event)
        ev_lay.addWidget(self._ev_list)
        ev_lay.addWidget(del_btn)
        lay.addWidget(ev_card)

        # ── 4. Sistem Ne Öğrendi? ───────────────────────────────────────────
        learn_card = self._make_card("Sistem Ne Ogrendi?  (Haftalik Oruntu)")
        learn_lay  = learn_card.layout()

        self._learn_status = QLabel("Veri birikmesi bekleniyor...")
        self._learn_status.setStyleSheet(
            f"color:{C_TEXT_DIM}; font-size:11px; background:transparent; border:none;"
        )
        learn_lay.addWidget(self._learn_status)

        # 7-satır × 24-sütun özet tablo (gün × saat)
        self._pattern_table = QTableWidget(7, 24)
        self._pattern_table.setMaximumHeight(160)
        self._pattern_table.setHorizontalHeaderLabels([f"{h:02d}" for h in range(24)])
        self._pattern_table.setVerticalHeaderLabels(
            ["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]
        )
        self._pattern_table.horizontalHeader().setDefaultSectionSize(26)
        self._pattern_table.verticalHeader().setDefaultSectionSize(20)
        self._pattern_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pattern_table.setStyleSheet(f"""
            QTableWidget {{ background:{C_BG}; border:1px solid {C_BORDER};
                            gridline-color:{C_BORDER}; color:{C_TEXT}; font-size:9px; }}
            QHeaderView::section {{ background:{C_SURFACE}; color:{C_TEXT_DIM};
                                    font-size:9px; border:none; padding:2px; }}
        """)
        learn_lay.addWidget(self._pattern_table)

        btn_refresh_learn = QPushButton("Guncelle")
        btn_refresh_learn.setFixedHeight(28)
        btn_refresh_learn.clicked.connect(self._refresh_pattern_table)
        learn_lay.addWidget(btn_refresh_learn)
        lay.addWidget(learn_card)
        QTimer.singleShot(2000, self._refresh_pattern_table)

        # ── 5. Otomatik Danışman ────────────────────────────────────────────
        adv_card = self._make_card("Otomatik Profil Danismani")
        adv_lay  = adv_card.layout()

        adv_info = QLabel(
            "Danissman her saat Prometheus'tan saatlik RPS verisi ceker, haftalik orntuyu "
            "ogrenilir ve profil agirliklarini otomatik gunceller.\n"
            "En az 3 gunluk veri birikmesi gereklidir. 'auto' etiketli saatler otomatik ayarlanmistir."
        )
        adv_info.setWordWrap(True)
        adv_info.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; background:transparent; border:none;")
        adv_lay.addWidget(adv_info)

        adv_btn_row = QHBoxLayout()
        btn_run_adv = QPushButton("Simdi Calistir")
        btn_run_adv.setFixedHeight(30)
        btn_run_adv.clicked.connect(self._advisor.run_cycle)
        adv_btn_row.addWidget(btn_run_adv)
        adv_btn_row.addStretch()
        adv_lay.addLayout(adv_btn_row)

        self._advisor_log_widget = LogWidget()
        self._advisor_log_widget.setMaximumHeight(120)
        adv_lay.addWidget(self._advisor_log_widget)

        lay.addWidget(adv_card)

        lay.addStretch()
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._load_events()

    # ── Yardımcı widget oluşturucu ──────────────────────────────────────────
    def _make_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.08); border-radius:18px; }}"
        )
        _add_shadow(card, blur=24, offset_y=6, alpha=70)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)
        hdr = QLabel(title)
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        lay.addWidget(hdr)
        return card

    @staticmethod
    def _slider_style() -> str:
        return f"""
            QSlider {{
                font-size: 12pt;
            }}
            QSlider::groove:vertical {{
                background: {C_SURFACE2};
                width: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:vertical {{
                background: {C_ACCENT};
                height: 12px;
                width: 12px;
                margin: 0 -3px;
                border-radius: 6px;
            }}
            QSlider::sub-page:vertical {{
                background: {C_ACCENT2};
                border-radius: 3px;
            }}
        """

    # ── Profil işlemleri ────────────────────────────────────────────────────
    def _on_slider(self, hour: int, raw_val: int):
        weight = raw_val / 10.0
        self._hour_vals[hour].setText(f"{weight:.1f}")
        color = C_RED if weight > 2.0 else (C_YELLOW if weight > 1.3 else C_ACCENT)
        self._hour_vals[hour].setStyleSheet(
            f"color:{color}; font-size:10px; font-weight:600; background:transparent; border:none;"
        )
        self.db.set_hour_weight(hour, weight)
        self._heatmap.update_profile(hour, weight)

    def _reset_profile(self):
        for h, sl in enumerate(self._sliders):
            sl.setValue(10)
        self.db.set_full_profile({h: {"weight": 1.0, "label": ""} for h in range(24)})
        self._heatmap.update()

    # ── Etkinlik işlemleri ──────────────────────────────────────────────────
    def _add_event(self):
        name   = self._ev_name.text().strip()
        date   = self._ev_date.date().toString("yyyy-MM-dd")
        margin = self._ev_margin.value()
        if not name:
            return
        self.db.add_domain_event(name, date, margin)
        self._ev_name.clear()
        self._load_events()

    def _delete_event(self):
        item = self._ev_list.currentItem()
        if not item:
            return
        event_id = item.data(Qt.ItemDataRole.UserRole)
        if event_id is not None:
            self.db.delete_domain_event(event_id)
            self._load_events()

    def _load_events(self):
        self._ev_list.clear()
        for ev in self.db.get_domain_events():
            text = f"{ev['event_date']}   {ev['name']}   (marj: %{int(ev['safety_margin']*100)})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, ev["id"])
            self._ev_list.addItem(item)

    # ── Kubernetes senkronizasyonu ───────────────────────────────────────────
    def _sync_to_k8s(self):
        self._sync_lbl.setText("Gönderiliyor...")
        self._sync_lbl.setStyleSheet(f"color:{C_YELLOW}; font-size:11px; background:transparent; border:none;")
        ok, msg = self.ops.sync_domain_profile()
        if ok:
            self._sync_lbl.setText(f"✓  {msg}")
            self._sync_lbl.setStyleSheet(f"color:{C_GREEN}; font-size:11px; background:transparent; border:none;")
        else:
            self._sync_lbl.setText(f"✗  {msg}")
            self._sync_lbl.setStyleSheet(f"color:{C_RED}; font-size:11px; background:transparent; border:none;")

    # ── Canlı veri çekme ────────────────────────────────────────────────────
    def _refresh_live(self):
        """
        İki sorgu yapar:
        1. Anlık RPS → şu anki saatin yeşil barını günceller
        2. Bugünün saatlik ortalamaları → sarı geçmiş çizgisini doldurur
           (Prometheus'ta gün başından beri veri varsa çalışır)
        """
        import threading
        threading.Thread(target=self._fetch_data_bg, daemon=True).start()

    def _fetch_data_bg(self):
        """Arka planda Prometheus'tan hem anlık hem geçmiş veriyi çeker."""
        try:
            import requests as _req, time as _time, datetime as _dt

            # ── 1. Anlık RPS (son 5 dk) ──────────────────────────────────
            resp = _req.get(
                self.PROM_URL,
                params={"query": "sum(rate(http_requests_total[5m]))"},
                timeout=5
            )
            data = resp.json()
            if data.get("status") == "success" and data["data"]["result"]:
                val = float(data["data"]["result"][0]["value"][1])
                current_hour = _dt.datetime.now().hour
                self._live_rps[current_hour] = val
                self._heatmap.update_live(current_hour, val)

            # ── 2. Bugünün saatlik RPS ortalamaları (sarı geçmiş çizgisi) ─
            # Gün başından şu ana kadar 1 saatlik adımlarla sorgula
            now = _time.time()
            midnight = _dt.datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).timestamp()

            range_resp = _req.get(
                self.PROM_URL.replace("/query", "/query_range"),
                params={
                    "query": "sum(rate(http_requests_total[10m]))",
                    "start": str(int(midnight)),
                    "end":   str(int(now)),
                    "step":  "3600"   # 1 saatlik adım → her saat 1 nokta
                },
                timeout=8
            )
            rdata = range_resp.json()
            if rdata.get("status") == "success" and rdata["data"]["result"]:
                today = _dt.date.today().isoformat()
                for ts, v in rdata["data"]["result"][0].get("values", []):
                    hour = _dt.datetime.fromtimestamp(float(ts)).hour
                    rps  = float(v)
                    self._hist_rps[hour] = rps
                    self._heatmap.update_hist(hour, rps)
                    # DB'ye kaydet → uygulama kapatılıp açılsa bile korunur
                    self.db.save_hourly_rps(today, hour, rps)

        except Exception:
            pass

    def _load_history_from_db(self):
        """Uygulama açılışında son 7 günün saatlik ortalamasını DB'den yükler."""
        try:
            hist = self.db.get_hourly_rps_history(days=7)
            for hour, avg_rps in hist.items():
                self._hist_rps[hour] = avg_rps
                self._heatmap.update_hist(hour, avg_rps)
        except Exception:
            pass

    def _refresh_pattern_table(self) -> None:
        """
        weekly_pattern tablosunu okur ve renk kodlu ısı haritası olarak gösterir.
        Yüksek RPS → kırmızı, düşük → mavi, orta → nötr.
        """
        import threading
        threading.Thread(target=self._load_pattern_bg, daemon=True).start()

    def _load_pattern_bg(self) -> None:
        try:
            pattern = self.db.get_weekly_pattern()   # {(dow, hour): {avg_rps, samples}}
            with self.db._lock:
                from contextlib import suppress
                with suppress(Exception):
                    cur = self.db.conn.execute(
                        "SELECT COUNT(DISTINCT date) FROM hourly_rps_history"
                    )
                    unique_days = cur.fetchone()[0]
        except Exception:
            unique_days = 0
            pattern = {}

        # UI güncellemesi main thread'de QTimer trick ile yapılır
        self._pattern_data = (pattern, unique_days)
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(0, self._apply_pattern_ui)

    def _apply_pattern_ui(self) -> None:
        """Pattern verisini tabloya uygular (main thread)."""
        from PyQt6.QtWidgets import QTableWidgetItem as _Item
        from PyQt6.QtGui import QColor as _QColor

        pattern, unique_days = getattr(self, "_pattern_data", ({}, 0))

        if not pattern:
            self._learn_status.setText(
                f"Henuz haftalik oruntu yok | {unique_days} gun kayitli "
                f"(en az {ProfileAdvisor.MIN_DAYS_FOR_AUTO} gun gerekli)"
            )
            return

        self._learn_status.setText(
            f"{unique_days} gun kayitli | "
            f"{'Otomatik mod aktif' if unique_days >= ProfileAdvisor.MIN_DAYS_FOR_AUTO else f'Otomatik mod icin {ProfileAdvisor.MIN_DAYS_FOR_AUTO - unique_days} gun daha gerekli'}"
        )

        all_rps = [v["avg_rps"] for v in pattern.values() if v["avg_rps"] > 0]
        if not all_rps:
            return
        max_rps = max(all_rps)
        avg_rps = sum(all_rps) / len(all_rps)

        for (dow, hour), info in pattern.items():
            rps = info["avg_rps"]
            samples = info["samples"]
            if rps <= 0 or samples < 1:
                continue

            item = _Item(f"{rps:.0f}")
            item.setTextAlignment(0x0004 | 0x0080)  # AlignCenter

            # Renk: 0=mavi(düşük) … max=kırmızı(yüksek)
            ratio = min(rps / max_rps, 1.0) if max_rps > 0 else 0
            r = int(52  + ratio * (239 - 52))    # 52→239
            g = int(211 - ratio * (211 - 68))    # 211→68
            b = int(153 - ratio * (153 - 68))    # 153→68
            item.setBackground(_QColor(r, g, b, 160))

            # Az veri varsa gri tonu
            if samples < 2:
                item.setForeground(_QColor(C_TEXT_DIM))

            self._pattern_table.setItem(dow, hour, item)

    @pyqtSlot(str, str)
    def _on_advisor_log(self, msg: str, level: str) -> None:
        """Danışmandan gelen log mesajlarını UI'daki log widget'ına yazar."""
        try:
            self._advisor_log_widget.append_line(msg, level)
        except Exception:
            pass

    def refresh_sliders_from_profile(self) -> None:
        """DB'deki profil verisine göre kaydırıcıları günceller (danışman güncellemesinden sonra)."""
        profile = self.db.get_traffic_profile()
        for h, sl in enumerate(self._sliders):
            w = profile.get(h, {}).get("weight", 1.0)
            sl.blockSignals(True)
            sl.setValue(int(round(w * 10)))
            sl.blockSignals(False)
            color = C_RED if w > 2.0 else (C_YELLOW if w > 1.3 else C_ACCENT)
            self._hour_vals[h].setText(f"{w:.1f}")
            self._hour_vals[h].setStyleSheet(
                f"color:{color}; font-size:10px; font-weight:600; "
                f"background:transparent; border:none;"
            )
            self._heatmap.update_profile(h, w)


# ── Yoğunluk haritası widget ──────────────────────────────────────────────────
class _HeatmapWidget(QWidget):
    """24 saatlik yoğunluk haritası: profil + canlı + geçmiş ortalaması."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db          = db
        self._profile    = {h: 1.0 for h in range(24)}
        self._live       = {}
        self._hist       = {}
        self._load_profile()
        self.setMinimumHeight(200)

    def _load_profile(self):
        p = self.db.get_traffic_profile()
        self._profile = {h: v["weight"] for h, v in p.items()}

    def update_profile(self, hour: int, weight: float):
        self._profile[hour] = weight
        self.update()

    def update_live(self, hour: int, val: float):
        self._live[hour] = val
        self.update()

    def update_hist(self, hour: int, val: float):
        self._hist[hour] = val
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPen, QFont as _QFont
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        padding_l, padding_r = 40, 10
        padding_b, padding_t = 30, 10
        bar_area_w = w - padding_l - padding_r
        bar_area_h = h - padding_b - padding_t
        bar_w = bar_area_w / 24
        bar_gap = max(1, int(bar_w * 0.15))

        # Maksimum değer hesapla
        all_vals = list(self._profile.values()) + list(self._live.values()) + list(self._hist.values())
        max_val = max(all_vals) if all_vals else 1.0
        if max_val < 0.01:
            max_val = 1.0

        # Arka plan
        painter.fillRect(0, 0, w, h, QColor(C_BG))

        # Y ekseni çizgisi
        pen = QPen(QColor(C_BORDER))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(padding_l, padding_t, padding_l, h - padding_b)
        painter.drawLine(padding_l, h - padding_b, w - padding_r, h - padding_b)

        # Y eksen etiketleri
        font = _QFont("Segoe UI", 8)
        painter.setFont(font)
        painter.setPen(QColor(C_TEXT_DIM))
        for frac in [0.0, 0.5, 1.0]:
            y = int(h - padding_b - frac * bar_area_h)
            painter.drawText(2, y + 4, 34, 12, Qt.AlignmentFlag.AlignRight, f"{max_val*frac:.1f}")
            if frac > 0:
                pen2 = QPen(QColor(C_BORDER))
                pen2.setStyle(Qt.PenStyle.DotLine)
                painter.setPen(pen2)
                painter.drawLine(padding_l, y, w - padding_r, y)
                painter.setPen(QColor(C_TEXT_DIM))

        current_hour = __import__("datetime").datetime.now().hour

        for hour in range(24):
            x = int(padding_l + hour * bar_w)
            bw = int(bar_w - bar_gap)

            # Profil barı
            prof_val = self._profile.get(hour, 1.0)
            prof_h   = int((prof_val / max_val) * bar_area_h)
            alpha    = 200 if hour == current_hour else 140
            painter.fillRect(
                x, h - padding_b - prof_h, bw, prof_h,
                QColor(129, 140, 248, alpha)   # C_ACCENT (#818CF8)
            )

            # Canlı RPS çubuğu (ince, üst kısım)
            if hour in self._live:
                live_h = int((self._live[hour] / max_val) * bar_area_h)
                painter.fillRect(
                    x, h - padding_b - live_h, bw, 4,
                    QColor(52, 211, 153, 220)   # C_GREEN
                )

            # Geçmiş ort. çizgi
            if hour in self._hist:
                hist_y = int(h - padding_b - (self._hist[hour] / max_val) * bar_area_h)
                pen3 = QPen(QColor(252, 211, 77, 180))  # C_YELLOW
                pen3.setWidth(2)
                painter.setPen(pen3)
                if hour > 0 and (hour - 1) in self._hist:
                    prev_y = int(h - padding_b - (self._hist[hour-1] / max_val) * bar_area_h)
                    prev_x = int(padding_l + (hour - 1) * bar_w + bw // 2)
                    painter.drawLine(prev_x, prev_y, x + bw // 2, hist_y)

            # Saat etiketi (her 3 saatte bir)
            if hour % 3 == 0:
                painter.setPen(QColor(C_TEXT_DIM))
                painter.setFont(_QFont("Segoe UI", 8))
                painter.drawText(x, h - padding_b + 4, bw, 20, Qt.AlignmentFlag.AlignHCenter, str(hour))

            # Şu anki saati vurgula
            if hour == current_hour:
                pen4 = QPen(QColor(C_TEXT))
                pen4.setWidth(1)
                painter.setPen(pen4)
                painter.drawRect(x, padding_t, bw, bar_area_h)

        painter.end()


# ─────────────────────────────────────────────
#  DEPLOY PANEL
# ─────────────────────────────────────────────
class DeployPanel(QWidget):
    """Proje yönetim paneli.

    Üç sekme:
      1. Yeni Deploy  — klasör seç → canlı validasyon → PreflightDialog → deploy
      2. Proje Yönetimi — aktif proje seçimi + navigasyon
      3. Güncelle — mevcut projeyi yeni image/port ile yeniden deploy et
    """

    #: Ana pencereye "Ana Sayfa'ya git" veya "Proje Yönetimine git" mesajı gönderir
    navigate_request = pyqtSignal(str)   # "_nav_home" | "_nav_deploy_mgr"
    #: Deploy thread'inden main thread'e sonuç iletir (thread-safe)
    _deploy_done = pyqtSignal(bool, str, str, str, int)  # ok, msg, name, folder, port

    # Proje türü metadatası (ikon, renk, port, açıklama)
    _TYPE_INFO = {
        "python": ("🐍", C_GREEN,    8080, "Python"),
        "node":   ("📦", C_YELLOW,   3000, "Node.js"),
        "static": ("🌐", C_ACCENT,   80,   "Statik HTML"),
        "docker": ("🐳", C_TEXT_DIM, 8080, "Özel Docker"),
        "unknown":("❓", C_RED,      8080, "Tanımlanamadı"),
    }

    def __init__(self, db, ops, parent=None):
        super().__init__(parent)
        self.db  = db
        self.ops = ops
        self._last_analysis: Optional[Dict] = None   # son _analyze_project() sonucu
        self._deploy_done.connect(self._on_deploy_finished, Qt.ConnectionType.QueuedConnection)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)
        lay.addWidget(SectionTitle("Deploy Yönetimi"))

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border:1px solid {C_BORDER}; border-radius:8px; }}
            QTabBar::tab {{ background:{C_SURFACE}; color:{C_TEXT_DIM}; padding:8px 20px;
                            border:1px solid {C_BORDER}; border-bottom:none;
                            border-radius:4px 4px 0 0; }}
            QTabBar::tab:selected {{ background:{C_BG}; color:{C_TEXT};
                                     border-bottom:1px solid {C_BG}; }}
        """)
        tabs.addTab(self._build_new_deploy_tab(),  "🚀  Yeni Deploy")
        tabs.addTab(self._build_project_manager(), "📋  Proje Yönetimi")
        tabs.addTab(self._build_update_tab(),      "🔄  Güncelle")
        lay.addWidget(tabs)
        lay.addStretch()

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 1 — YENİ DEPLOY
    # ═══════════════════════════════════════════════════════════════════════

    def _build_new_deploy_tab(self) -> QWidget:
        """Klasör seç → canlı validasyon → PreflightDialog → deploy log."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # ── Desteklenen Format Rehberi ─────────────────────────────────────
        guide_card = QFrame()
        guide_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(guide_card, blur=16, offset_y=3, alpha=40)
        gc_lay = QVBoxLayout(guide_card)
        gc_lay.setContentsMargins(18, 14, 18, 14)
        gc_lay.setSpacing(8)

        guide_hdr = QLabel("📚  Desteklenen Proje Formatları")
        guide_hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        guide_hdr.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        gc_lay.addWidget(guide_hdr)

        formats = [
            ("🐍", "Python",       C_GREEN,  "requirements.txt  veya  *.py",
             "app.py / main.py → giriş noktası otomatik tespit edilir. "
             "Dockerfile otomatik oluşturulur (python:3.11-slim). "
             "Flask / FastAPI / Django tamamen desteklenir."),
            ("📦", "Node.js",      C_YELLOW, "package.json  zorunlu",
             "index.js veya server.js → giriş noktası. "
             "Dockerfile otomatik oluşturulur (node:20-alpine). "
             "npm start script'i tanımlı olmalı."),
            ("🌐", "Statik HTML",  C_ACCENT, "index.html  kök dizinde",
             "HTML / CSS / JS dosyaları. "
             "Dockerfile otomatik oluşturulur (nginx:alpine). "
             "SPA (React/Vue build output) tam destek."),
            ("🐳", "Özel Docker",  C_TEXT_DIM, "Dockerfile  kök dizinde",
             "Herhangi bir dil / framework. "
             "Dockerfile olduğu gibi kullanılır, hiçbir şey değiştirilmez."),
        ]
        for icon, name, color, req, desc in formats:
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"QFrame {{ background:{C_BG}; border:1px solid rgba(255,255,255,0.05); "
                f"border-radius:10px; }}"
            )
            rf_lay = QHBoxLayout(row_frame)
            rf_lay.setContentsMargins(12, 10, 12, 10)
            rf_lay.setSpacing(12)

            icon_lbl = QLabel(icon)
            icon_lbl.setFont(QFont("Segoe UI", 18))
            icon_lbl.setFixedWidth(30)
            icon_lbl.setStyleSheet("background:transparent; border:none;")

            col = QVBoxLayout()
            col.setSpacing(2)

            name_req = QHBoxLayout()
            name_req.setSpacing(8)
            name_l = QLabel(name)
            name_l.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            name_l.setStyleSheet(f"color:{color}; background:transparent; border:none;")
            req_l  = QLabel(req)
            req_l.setFont(QFont("Courier New", 10))
            req_l.setStyleSheet(
                f"color:{C_TEXT_DIM}; background:rgba(255,255,255,0.04); "
                f"border:1px solid rgba(255,255,255,0.06); border-radius:4px; "
                f"padding:1px 6px;"
            )
            name_req.addWidget(name_l)
            name_req.addWidget(req_l)
            name_req.addStretch()

            desc_l = QLabel(desc)
            desc_l.setFont(QFont("Segoe UI", 10))
            desc_l.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
            desc_l.setWordWrap(True)

            col.addLayout(name_req)
            col.addWidget(desc_l)
            rf_lay.addWidget(icon_lbl)
            rf_lay.addLayout(col, 1)
            gc_lay.addWidget(row_frame)

        lay.addWidget(guide_card)

        # ── Klasör Seçimi ──────────────────────────────────────────────────
        folder_card = QFrame()
        folder_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(folder_card, blur=16, offset_y=3, alpha=40)
        fc_lay = QVBoxLayout(folder_card)
        fc_lay.setContentsMargins(18, 16, 18, 16)
        fc_lay.setSpacing(12)

        hdr1 = QLabel("1️⃣  Uygulama Klasörü")
        hdr1.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr1.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        fc_lay.addWidget(hdr1)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        self._deploy_folder = QLineEdit()
        self._deploy_folder.setPlaceholderText("C:\\projeler\\web-uygulamam")
        self._deploy_folder.setReadOnly(True)
        self._deploy_folder.setFixedHeight(38)
        btn_browse = QPushButton("📁  Klasör Seç")
        btn_browse.setFixedHeight(38)
        btn_browse.setFixedWidth(130)
        btn_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._deploy_folder, 1)
        folder_row.addWidget(btn_browse)
        fc_lay.addLayout(folder_row)

        hdr2 = QLabel("2️⃣  Proje Ayarları")
        hdr2.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr2.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        fc_lay.addWidget(hdr2)

        cfg_row = QHBoxLayout()
        cfg_row.setSpacing(12)
        lbl_name = QLabel("Proje Adı:")
        lbl_name.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._deploy_name = QLineEdit()
        self._deploy_name.setPlaceholderText("blog-sitesi")
        self._deploy_name.setFixedHeight(38)
        lbl_port = QLabel("Port:")
        lbl_port.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._deploy_port = QSpinBox()
        self._deploy_port.setRange(1024, 65535)
        self._deploy_port.setValue(8080)
        self._deploy_port.setFixedHeight(38)
        self._deploy_port.setFixedWidth(90)
        cfg_row.addWidget(lbl_name)
        cfg_row.addWidget(self._deploy_name, 1)
        cfg_row.addWidget(lbl_port)
        cfg_row.addWidget(self._deploy_port)
        fc_lay.addLayout(cfg_row)
        lay.addWidget(folder_card)

        # ── Canlı Validasyon Kartı ─────────────────────────────────────────
        self._validation_card = QFrame()
        self._validation_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(self._validation_card, blur=16, offset_y=3, alpha=40)
        vc_lay = QVBoxLayout(self._validation_card)
        vc_lay.setContentsMargins(18, 16, 18, 16)
        vc_lay.setSpacing(8)

        vc_hdr = QLabel("🔍  Proje Analizi")
        vc_hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        vc_hdr.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        vc_lay.addWidget(vc_hdr)

        self._validation_placeholder = QLabel(
            "Klasör seçtikten sonra otomatik analiz başlar."
        )
        self._validation_placeholder.setFont(QFont("Segoe UI", 11))
        self._validation_placeholder.setStyleSheet(
            f"color:{C_TEXT_DIM}; background:transparent; border:none;"
        )
        vc_lay.addWidget(self._validation_placeholder)

        # Tip badge + özet satırı
        self._val_type_row = QHBoxLayout()
        self._val_type_icon = QLabel("")
        self._val_type_icon.setFont(QFont("Segoe UI", 20))
        self._val_type_icon.setStyleSheet("background:transparent; border:none;")
        self._val_type_icon.setFixedWidth(32)
        self._val_type_icon.hide()
        self._val_summary_lbl = QLabel("")
        self._val_summary_lbl.setFont(QFont("Segoe UI", 11))
        self._val_summary_lbl.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        self._val_summary_lbl.hide()
        self._val_type_row.addWidget(self._val_type_icon)
        self._val_type_row.addWidget(self._val_summary_lbl, 1)
        vc_lay.addLayout(self._val_type_row)

        # İssue listesi scroll area
        self._val_issues_widget = QWidget()
        self._val_issues_widget.setStyleSheet("background:transparent;")
        self._val_issues_lay = QVBoxLayout(self._val_issues_widget)
        self._val_issues_lay.setContentsMargins(0, 0, 0, 0)
        self._val_issues_lay.setSpacing(6)
        vc_lay.addWidget(self._val_issues_widget)
        self._validation_card.setVisible(False)
        lay.addWidget(self._validation_card)

        # ── Log alanı ─────────────────────────────────────────────────────
        log_card = QFrame()
        log_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(log_card, blur=16, offset_y=3, alpha=40)
        lc_lay = QVBoxLayout(log_card)
        lc_lay.setContentsMargins(18, 16, 18, 16)
        lc_lay.setSpacing(8)

        hdr3 = QLabel("3️⃣  Deploy Günlüğü")
        hdr3.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr3.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        lc_lay.addWidget(hdr3)

        self._deploy_log = LogWidget()
        self._deploy_log.setMinimumHeight(220)
        lc_lay.addWidget(self._deploy_log)

        # Deploy butonu
        deploy_btn_row = QHBoxLayout()
        deploy_btn_row.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._btn_deploy = QPushButton("▶   Analiz Et & Deploy Et")
        self._btn_deploy.setObjectName("btn_primary")
        self._btn_deploy.setFixedHeight(46)
        self._btn_deploy.setMinimumWidth(220)
        self._btn_deploy.clicked.connect(self._start_deploy)
        deploy_btn_row.addWidget(self._btn_deploy)
        lc_lay.addLayout(deploy_btn_row)

        # Başarı banner (deploy sonrası gösterilir)
        self._success_banner = QFrame()
        self._success_banner.setStyleSheet(
            f"QFrame {{ background:rgba(48,209,88,0.12); "
            f"border:1px solid {C_GREEN}; border-radius:10px; }}"
        )
        sb_lay = QHBoxLayout(self._success_banner)
        sb_lay.setContentsMargins(14, 10, 14, 10)
        sb_lay.setSpacing(12)
        sb_icon = QLabel("🎉")
        sb_icon.setFont(QFont("Segoe UI", 18))
        sb_icon.setStyleSheet("background:transparent; border:none;")
        sb_text_col = QVBoxLayout()
        sb_text_col.setSpacing(2)
        self._success_name_lbl = QLabel("")
        self._success_name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._success_name_lbl.setStyleSheet(f"color:{C_GREEN}; background:transparent; border:none;")
        self._success_url_lbl = QLabel("")
        self._success_url_lbl.setFont(QFont("Segoe UI", 11))
        self._success_url_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        sb_text_col.addWidget(self._success_name_lbl)
        sb_text_col.addWidget(self._success_url_lbl)
        sb_btn_col = QVBoxLayout()
        sb_btn_col.setSpacing(6)
        self._btn_go_home = QPushButton("🚀  Ana Sayfa'ya Git")
        self._btn_go_home.setObjectName("btn_primary")
        self._btn_go_home.setFixedHeight(36)
        self._btn_go_home.clicked.connect(lambda: self.navigate_request.emit("_nav_home"))
        self._btn_go_mgr  = QPushButton("📋  Proje Yönetimine Git")
        self._btn_go_mgr.setFixedHeight(36)
        self._btn_go_mgr.clicked.connect(lambda: self.navigate_request.emit("_nav_deploy_mgr"))
        sb_btn_col.addWidget(self._btn_go_home)
        sb_btn_col.addWidget(self._btn_go_mgr)
        sb_lay.addWidget(sb_icon)
        sb_lay.addLayout(sb_text_col, 1)
        sb_lay.addLayout(sb_btn_col)
        self._success_banner.setVisible(False)
        lc_lay.addWidget(self._success_banner)

        # Hata Yardımcısı (deploy başarısız olunca görünür)
        self._help_panel = QFrame()
        self._help_panel.setStyleSheet(
            f"QFrame {{ background:rgba(248,113,113,0.08); "
            f"border:1px solid rgba(248,113,113,0.35); border-radius:12px; }}"
        )
        hp_lay = QVBoxLayout(self._help_panel)
        hp_lay.setContentsMargins(16, 12, 16, 12)
        hp_lay.setSpacing(8)
        hp_hdr = QHBoxLayout()
        hp_icon = QLabel("🤖")
        hp_icon.setFont(QFont("Segoe UI", 16))
        hp_icon.setStyleSheet("background:transparent; border:none;")
        hp_title = QLabel("Deploy Yardımcısı")
        hp_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hp_title.setStyleSheet(f"color:{C_RED}; background:transparent; border:none;")
        hp_hdr.addWidget(hp_icon)
        hp_hdr.addWidget(hp_title)
        hp_hdr.addStretch()
        hp_lay.addLayout(hp_hdr)
        self._help_category = QLabel("")
        self._help_category.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._help_category.setStyleSheet(f"color:{C_YELLOW}; background:transparent; border:none;")
        hp_lay.addWidget(self._help_category)
        self._help_steps = QLabel("")
        self._help_steps.setFont(QFont("Segoe UI", 10))
        self._help_steps.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        self._help_steps.setWordWrap(True)
        hp_lay.addWidget(self._help_steps)
        self._help_cmd = QFrame()
        self._help_cmd.setStyleSheet(
            f"QFrame {{ background:{C_BG}; border:1px solid {C_BORDER}; border-radius:6px; }}"
        )
        hc_lay = QHBoxLayout(self._help_cmd)
        hc_lay.setContentsMargins(10, 6, 10, 6)
        self._help_cmd_lbl = QLabel("")
        self._help_cmd_lbl.setFont(QFont("Consolas, Courier New", 10))
        self._help_cmd_lbl.setStyleSheet(f"color:{C_ACCENT}; background:transparent; border:none;")
        self._help_cmd_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_btn = QPushButton("Kopyala")
        copy_btn.setFixedHeight(26)
        copy_btn.setFixedWidth(70)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self._help_cmd_lbl.text()))
        hc_lay.addWidget(self._help_cmd_lbl, 1)
        hc_lay.addWidget(copy_btn)
        hp_lay.addWidget(self._help_cmd)
        self._help_panel.setVisible(False)
        lc_lay.addWidget(self._help_panel)

        lay.addWidget(log_card)
        lay.addStretch()

        scroll.setWidget(inner)
        return scroll

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 2 — PROJE YÖNETİMİ
    # ═══════════════════════════════════════════════════════════════════════

    def _build_project_manager(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        # Aktif proje bilgisi
        active_card = QFrame()
        active_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(active_card, blur=16, offset_y=3, alpha=40)
        ac_lay = QHBoxLayout(active_card)
        ac_lay.setContentsMargins(18, 14, 18, 14)
        ac_lay.setSpacing(12)

        active_icon = QLabel("⚡")
        active_icon.setFont(QFont("Segoe UI", 22))
        active_icon.setStyleSheet("background:transparent; border:none;")
        ac_text = QVBoxLayout()
        ac_text.setSpacing(2)
        ac_title = QLabel("Aktif Proje")
        ac_title.setFont(QFont("Segoe UI", 10))
        ac_title.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._active_project_lbl = QLabel("—")
        self._active_project_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._active_project_lbl.setStyleSheet(
            f"color:{C_GREEN}; background:transparent; border:none;"
        )
        ac_text.addWidget(ac_title)
        ac_text.addWidget(self._active_project_lbl)
        ac_lay.addWidget(active_icon)
        ac_lay.addLayout(ac_text, 1)
        lay.addWidget(active_card)

        # Proje listesi
        list_card = QFrame()
        list_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(list_card, blur=16, offset_y=3, alpha=40)
        lc_lay = QVBoxLayout(list_card)
        lc_lay.setContentsMargins(18, 16, 18, 16)
        lc_lay.setSpacing(10)

        list_hdr = QLabel("Deploy Edilmiş Projeler")
        list_hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        list_hdr.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        lc_lay.addWidget(list_hdr)

        self._project_list = QListWidget()
        self._project_list.setMinimumHeight(200)
        self._project_list.setStyleSheet(
            f"QListWidget {{ background:{C_BG}; border:1px solid {C_BORDER}; "
            f"border-radius:8px; color:{C_TEXT}; padding:4px; }}"
            f"QListWidget::item {{ padding:10px 8px; border-radius:6px; }}"
            f"QListWidget::item:selected {{ background:{C_ACCENT}; color:#fff; }}"
            f"QListWidget::item:hover {{ background:{C_SURFACE2}; }}"
        )
        lc_lay.addWidget(self._project_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_set_active = QPushButton("✅  Aktif Yap")
        self._btn_set_active.setObjectName("btn_primary")
        self._btn_set_active.setFixedHeight(38)
        self._btn_set_active.clicked.connect(self._set_active_project)
        btn_refresh_list = QPushButton("🔄  Yenile")
        btn_refresh_list.setFixedHeight(38)
        btn_refresh_list.clicked.connect(self._refresh_project_list)
        self._btn_delete_proj = QPushButton("🗑  Sil")
        self._btn_delete_proj.setObjectName("btn_danger")
        self._btn_delete_proj.setFixedHeight(38)
        self._btn_delete_proj.clicked.connect(self._delete_project)
        btn_row.addWidget(self._btn_set_active)
        btn_row.addWidget(btn_refresh_list)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_delete_proj)
        lc_lay.addLayout(btn_row)

        self._proj_status_lbl = QLabel("")
        self._proj_status_lbl.setFont(QFont("Segoe UI", 10))
        self._proj_status_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._proj_status_lbl.setWordWrap(True)
        lc_lay.addWidget(self._proj_status_lbl)
        lay.addWidget(list_card)
        lay.addStretch()

        scroll.setWidget(inner)
        QTimer.singleShot(500, self._refresh_project_list)
        return scroll

    def _refresh_project_list(self):
        if not hasattr(self, '_project_list'):
            return
        self._project_list.clear()
        projects = self.db.get_all_projects()
        active_name = self.db.get_setting("active_project_name", "autoscaleops-app")
        active_port = self.db.get_setting("active_project_port", "8080")
        if hasattr(self, '_active_project_lbl'):
            self._active_project_lbl.setText(
                f"{active_name}  —  port {active_port}"
            )
        for p in projects:
            name      = p["name"]
            port      = p["port"]
            is_active = p.get("is_active", 0)
            date_str  = (p.get("deployed_at") or "")[:10]
            folder    = p.get("folder", "")
            # Proje tipini tahmin et
            try:
                a = _analyze_project(folder) if folder else {"type": "unknown"}
                type_icon = {"python": "🐍", "node": "📦", "static": "🌐",
                             "docker": "🐳", "unknown": "❓"}.get(a["type"], "❓")
            except Exception:
                type_icon = "📦"
            marker = "  ✅ AKTİF" if is_active else ""
            item = QListWidgetItem(
                f"{type_icon}  {name}{marker}   •   port {port}   •   {date_str}"
            )
            if is_active:
                item.setForeground(QColor(C_GREEN))
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._project_list.addItem(item)

    def _set_active_project(self):
        selected = self._project_list.currentItem()
        if not selected:
            self._proj_status_lbl.setText("Lütfen listeden bir proje seçin.")
            return
        proj      = selected.data(Qt.ItemDataRole.UserRole)
        name      = proj["name"]
        port      = proj["port"]
        service   = proj["service_name"]
        is_active = proj.get("is_active", 0)
        if is_active:
            self._proj_status_lbl.setText(f"'{name}' zaten aktif proje.")
            return
        instance = self.ops.get_instance()
        if not instance:
            self._proj_status_lbl.setText(
                "Instance bulunamadı — sistem çalışıyor mu? Ana Sayfa'dan Başlat'a basın."
            )
            return
        namespace = instance["namespace"]
        self._btn_set_active.setEnabled(False)
        self._proj_status_lbl.setText(f"'{name}' aktif yapılıyor…")

        def do():
            self.db.set_active_project(name)
            _write_active_project_json(name, port, service)
            ok, msg = self.ops.switch_active_project(name, port, service, namespace)
            # UI güncellemeleri main thread'de yapılmalı (Qt kuralı)
            if ok:
                QTimer.singleShot(0, lambda: (
                    self._btn_set_active.setEnabled(True),
                    self._proj_status_lbl.setText(
                        f"✅  '{name}' aktif — port {port}.  "
                        f"AI ölçekleme bu proje için aktif."
                    ),
                    self._refresh_project_list()
                ))
            else:
                QTimer.singleShot(0, lambda: (
                    self._btn_set_active.setEnabled(True),
                    self._proj_status_lbl.setText(f"❌  Hata: {msg}")
                ))

        threading.Thread(target=do, daemon=True).start()

    def _delete_project(self):
        selected = self._project_list.currentItem()
        if not selected:
            return
        proj = selected.data(Qt.ItemDataRole.UserRole)
        name = proj["name"]
        if proj.get("is_active", 0):
            self._proj_status_lbl.setText(
                "Aktif projeyi silemezsiniz. Önce başka bir projeyi aktif yapın."
            )
            return
        reply = QMessageBox.question(
            self, "Projeyi Sil",
            f"'{name}' projesi listeden kaldırılsın mı?\n"
            f"(Kubernetes deployment silinmez, sadece listeden kaldırılır.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.db.delete_project(name):
                self._refresh_project_list()
                self._proj_status_lbl.setText(f"'{name}' listeden kaldırıldı.")
            else:
                self._proj_status_lbl.setText("Silme başarısız.")

    # ═══════════════════════════════════════════════════════════════════════
    # TAB 3 — GÜNCELLE
    # ═══════════════════════════════════════════════════════════════════════

    def _build_update_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        info_card = QFrame()
        info_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(info_card, blur=16, offset_y=3, alpha=40)
        ic_lay = QVBoxLayout(info_card)
        ic_lay.setContentsMargins(18, 16, 18, 16)
        ic_lay.setSpacing(12)

        ic_hdr = QLabel("🔄  Mevcut Projeyi Yeniden Deploy Et")
        ic_hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        ic_hdr.setStyleSheet(f"color:{C_TEXT}; background:transparent; border:none;")
        ic_lay.addWidget(ic_hdr)

        note = QLabel(
            "Aktif projenin Docker image'ını, portunu veya replica sayısını "
            "değiştirip yeniden deploy edin."
        )
        note.setFont(QFont("Segoe UI", 10))
        note.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        note.setWordWrap(True)
        ic_lay.addWidget(note)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        lbl_img = QLabel("Docker Image:")
        lbl_img.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._upd_image = QLineEdit()
        self._upd_image.setPlaceholderText("autoscaleops-app:latest")
        self._upd_image.setFixedHeight(36)
        row1.addWidget(lbl_img)
        row1.addWidget(self._upd_image, 1)
        ic_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        lbl_port = QLabel("Port:")
        lbl_port.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._upd_port = QSpinBox()
        self._upd_port.setRange(1024, 65535)
        self._upd_port.setValue(8080)
        self._upd_port.setFixedHeight(36)
        self._upd_port.setFixedWidth(100)
        lbl_rep = QLabel("Replica:")
        lbl_rep.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
        self._upd_replicas = QSpinBox()
        self._upd_replicas.setRange(1, 20)
        self._upd_replicas.setValue(2)
        self._upd_replicas.setFixedHeight(36)
        self._upd_replicas.setFixedWidth(80)
        row2.addWidget(lbl_port)
        row2.addWidget(self._upd_port)
        row2.addSpacing(16)
        row2.addWidget(lbl_rep)
        row2.addWidget(self._upd_replicas)
        row2.addStretch()
        ic_lay.addLayout(row2)

        self._btn_redeploy = QPushButton("🔄  Yeniden Deploy Et")
        self._btn_redeploy.setObjectName("btn_primary")
        self._btn_redeploy.setFixedHeight(44)
        self._btn_redeploy.clicked.connect(self._start_redeploy)
        ic_lay.addWidget(self._btn_redeploy)
        lay.addWidget(info_card)

        log_card = QFrame()
        log_card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid rgba(255,255,255,0.07); "
            f"border-radius:14px; }}"
        )
        _add_shadow(log_card, blur=16, offset_y=3, alpha=40)
        lc2 = QVBoxLayout(log_card)
        lc2.setContentsMargins(18, 16, 18, 16)
        self._update_log = LogWidget()
        self._update_log.setMinimumHeight(200)
        lc2.addWidget(self._update_log)
        lay.addWidget(log_card)
        lay.addStretch()

        scroll.setWidget(inner)
        QTimer.singleShot(800, self._load_current_values)
        return scroll

    # ═══════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Uygulama Klasörü Seç")
        if not folder:
            return
        self._deploy_folder.setText(folder)
        suggested = Path(folder).name.lower().replace(" ", "-").replace("_", "-")
        if not self._deploy_name.text().strip():
            self._deploy_name.setText(suggested)
        # Canlı analiz
        self._run_validation(folder)

    def _run_validation(self, folder: str):
        """Klasörü analiz edip validasyon kartını günceller."""
        analysis = _analyze_project(folder)
        self._last_analysis = analysis

        # Port önerisi
        if self._deploy_port.value() == 8080:
            self._deploy_port.setValue(analysis.get("suggested_port", 8080))

        # Tipi göster
        type_key  = analysis.get("type", "unknown")
        type_icon, type_color, _, type_name = self._TYPE_INFO.get(
            type_key, ("❓", C_RED, 8080, "Bilinmiyor")
        )
        self._val_type_icon.setText(type_icon)
        self._val_type_icon.show()

        issues   = analysis.get("issues", [])
        errors   = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]

        if errors:
            summary = f"{type_name} projesi  •  {len(errors)} kritik sorun, {len(warnings)} uyarı"
            s_color = C_RED
        elif warnings:
            summary = f"{type_name} projesi  •  {len(warnings)} uyarı var"
            s_color = C_YELLOW
        else:
            summary = f"{type_name} projesi  •  Tüm kontroller geçildi ✅"
            s_color = C_GREEN

        self._val_summary_lbl.setText(summary)
        self._val_summary_lbl.setStyleSheet(
            f"color:{s_color}; background:transparent; border:none;"
        )
        self._val_summary_lbl.show()
        self._validation_placeholder.hide()

        # Sorun listesini temizle ve yeniden doldur
        while self._val_issues_lay.count():
            item = self._val_issues_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ICONS = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
        COLS  = {"error": C_RED, "warning": C_YELLOW, "info": C_TEXT_DIM}
        for iss in issues:
            sev    = iss["severity"]
            color  = COLS.get(sev, C_TEXT_DIM)
            icon   = ICONS.get(sev, "ℹ️")
            iss_f  = QFrame()
            iss_f.setStyleSheet(
                f"QFrame {{ background:{C_BG}; border-left:3px solid {color}; "
                f"border-radius:0 8px 8px 0; }}"
            )
            iff_lay = QHBoxLayout(iss_f)
            iff_lay.setContentsMargins(10, 7, 10, 7)
            iff_lay.setSpacing(10)
            ic_l = QLabel(icon)
            ic_l.setFont(QFont("Segoe UI", 13))
            ic_l.setFixedWidth(20)
            ic_l.setStyleSheet("background:transparent; border:none;")
            txt_col = QVBoxLayout()
            txt_col.setSpacing(1)
            title_l = QLabel(iss["title"])
            title_l.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            title_l.setStyleSheet(f"color:{color}; background:transparent; border:none;")
            detail_l = QLabel(iss["detail"])
            detail_l.setFont(QFont("Segoe UI", 10))
            detail_l.setStyleSheet(f"color:{C_TEXT_DIM}; background:transparent; border:none;")
            detail_l.setWordWrap(True)
            txt_col.addWidget(title_l)
            txt_col.addWidget(detail_l)
            iff_lay.addWidget(ic_l)
            iff_lay.addLayout(txt_col, 1)
            self._val_issues_lay.addWidget(iss_f)

        self._validation_card.setVisible(True)

    def _start_deploy(self):
        folder = self._deploy_folder.text().strip()
        name   = self._deploy_name.text().strip()
        port   = self._deploy_port.value()

        if not folder or not name:
            self._deploy_log.append_line("❌  Klasör ve proje adı zorunlu.", "error")
            return
        if not Path(folder).exists():
            self._deploy_log.append_line("❌  Klasör bulunamadı.", "error")
            return

        # KRITIK: Adı Docker/K8s uyumlu formata dönüştür (Türkçe harf, boşluk vb.)
        # deploy_app() içinde de yapılıyor ama DB kaydetme burada name'i kullandığından
        # önce sanitize etmek şart — aksi hâlde K8s servisi "yeni-klasor-service" iken
        # DB "yeni-klasör-service" kaydeder ve port-forward asla bulunamaz.
        safe_name = _sanitize_docker_name(name)
        if safe_name != name:
            self._deploy_log.append_line(
                f"ℹ️  Proje adı düzeltildi: '{name}' → '{safe_name}' (Docker/K8s uyumu)",
                "info"
            )
            self._deploy_name.setText(safe_name)
            name = safe_name

        # Eğer validasyon yoksa çalıştır, varsa mevcut sonucu kullan
        analysis = self._last_analysis or _analyze_project(folder)

        # PreflightDialog
        dlg = PreflightDialog(analysis, name, self)
        dlg.exec()
        if not dlg.confirmed:
            return  # Kullanıcı iptal etti

        # Deploy başlat
        self._btn_deploy.setEnabled(False)
        self._success_banner.setVisible(False)
        self._deploy_log.clear()
        self._deploy_log.append_line(
            f"{'='*56}", "info"
        )
        self._deploy_log.append_line(
            f"  Deploy Başlatıldı — {name}  (port {port})", "info"
        )
        self._deploy_log.append_line(
            f"{'='*56}", "info"
        )

        def do():
            # Sadece iş mantığı — UI'a dokunma
            ok, msg = self.ops.deploy_app(folder, name, port, self._deploy_log.append_line)
            if ok:
                # DB güncellemeleri thread'den yapılabilir (mutex'li SQLite)
                # name zaten sanitize edildi → K8s servis adıyla eşleşir
                self.db.add_project(name, folder, port, f"{name}-service", f"{name}:latest")
                self.db.set_active_project(name)
                self.db.set_setting("active_project_port",    str(port))
                self.db.set_setting("active_project_name",    name)
                self.db.set_setting("active_project_service", f"{name}-service")
                _write_active_project_json(name, port, f"{name}-service")
                instance = self.ops.get_instance()
                ns = instance.get("namespace", "autoscaleops")
                self.ops.stop_port_forwards()
                self.ops.start_port_forwards(ns)
            # Sonucu main thread'e sinyal ile ilet
            self._deploy_done.emit(ok, msg, name, folder, port)

        threading.Thread(target=do, daemon=True).start()

    @pyqtSlot(bool, str, str, str, int)
    def _on_deploy_finished(self, ok: bool, msg: str, name: str, folder: str, port: int):
        """Deploy worker'ından gelen sonucu main thread'de işler."""
        self._btn_deploy.setEnabled(True)
        if ok:
            self._refresh_project_list()
            self._success_name_lbl.setText(f"{name} basariyla deploy edildi!")
            self._success_url_lbl.setText(
                f"Adres: http://localhost:{port}  •  Ana Sayfa'dan Baslat'a basarak erisebilirsiniz."
            )
            self._success_banner.setVisible(True)
            self._help_panel.setVisible(False)
        else:
            self._deploy_log.append_line(f"\n Deploy basarisiz: {msg}", "error")
            self._show_deploy_help(msg)

    def _start_redeploy(self):
        image    = self._upd_image.text().strip()
        port     = self._upd_port.value()
        replicas = self._upd_replicas.value()
        self._btn_redeploy.setEnabled(False)
        self._update_log.clear()
        self._update_log.append_line("Yeniden deploy başlıyor…", "info")

        def do():
            active_name = self.db.get_setting("active_project_name", "autoscaleops-app")
            ok, msg = self.ops.redeploy_active_project(
                active_name, image, port, replicas, self._update_log.append_line
            )
            self._btn_redeploy.setEnabled(True)
            if not ok:
                self._update_log.append_line(f"❌  Hata: {msg}", "error")

        threading.Thread(target=do, daemon=True).start()

    def _load_current_values(self):
        instance = self.ops.get_instance()
        if not instance:
            return
        namespace   = instance.get("namespace", "autoscaleops")
        active_name = self.db.get_setting("active_project_name", "autoscaleops-app")
        active_port = int(self.db.get_setting("active_project_port", "8080"))
        self._upd_port.setValue(active_port)
        ok, out = run_ps(
            f"kubectl get deployment {active_name}-deployment -n {namespace} "
            f"-o jsonpath='{{{{.spec.template.spec.containers[0].image}}}}' 2>&1"
        )
        if ok and out.strip():
            self._upd_image.setText(out.strip())
        ok2, out2 = run_ps(
            f"kubectl get deployment {active_name}-deployment -n {namespace} "
            f"-o jsonpath='{{{{.spec.replicas}}}}' 2>&1"
        )
        if ok2 and out2.strip():
            try:
                self._upd_replicas.setValue(int(out2.strip()))
            except Exception:
                pass

    # ─── Deploy Yardımcısı ──────────────────────────────────────────────────

    # Hata pattern → (kategori, adımlar, kopyalanacak komut)
    _DEPLOY_ERRORS = [
        (
            ["invalid tag", "invalid reference format", "unicode", "turkce", "special char"],
            "Hata: Türkçe/Özel Karakterli Proje Adı",
            "Docker image tag sadece küçük harf, rakam ve tire içerebilir.\n"
            "Çözüm: Proje Adı alanına yalnızca İngilizce karakter girin (örn: 'yeni-klasor').\n"
            "Uygulama artık bunu otomatik dönüştürüyor — klasörü yeniden seçin.",
            ""
        ),
        (
            ["docker desktop", "docker daemon", "error during connect", "docker is not running",
             "docker baslatilam", "docker kapal"],
            "Hata: Docker Desktop Kapalı",
            "Docker Desktop arka planda çalışmıyor.\n"
            "1. Sistem tepsisinde Docker balina ikonunu arayın.\n"
            "2. Yoksa Docker Desktop'u manuel başlatın.\n"
            "3. Balina ikonu yeşil olunca tekrar deneyin.",
            "& 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'"
        ),
        (
            ["minikube", "cluster", "not running", "connection refused", "no server"],
            "Hata: Kubernetes Cluster Çalışmıyor",
            "Minikube cluster'ı başlatılmamış veya kapanmış.\n"
            "1. Ana Sayfa'dan 'Cluster Başlat' butonuna tıklayın.\n"
            "2. Cluster hazır olduktan sonra deploy'u tekrar çalıştırın.",
            "minikube start -p autoscaleops --driver=docker"
        ),
        (
            ["port is already allocated", "port bind", "address already in use"],
            "Hata: Port Kullanımda",
            "Belirttiğiniz port başka bir uygulama tarafından kullanılıyor.\n"
            "1. Farklı bir port numarası deneyin (örn: 8081, 3000, 5000).\n"
            "2. Veya aşağıdaki komutla hangi process kullandığını bulun:",
            "netstat -ano | findstr :8080"
        ),
        (
            ["image not found", "manifest unknown", "repository does not exist", "not found"],
            "Hata: Docker Image Bulunamadı",
            "Build edilen image Kubernetes'in Docker ortamına aktarılamadı.\n"
            "1. Minikube docker-env aktif değilse image görünmez.\n"
            "2. Deploy'u tekrar başlatın — otomatik düzeltilmesi gerekir.\n"
            "3. Sorun devam ederse cluster'ı yeniden başlatın.",
            "& minikube -p autoscaleops docker-env --shell powershell | Invoke-Expression"
        ),
        (
            ["oomkilled", "out of memory", "memory limit", "evicted"],
            "Hata: Bellek Yetersiz",
            "Kubernetes pod'u bellek sınırı nedeniyle sonlandırıldı.\n"
            "1. Minikube'a daha fazla RAM ayırın (varsayılan: 6 GB).\n"
            "2. Uygulamanızın bellek kullanımını optimize edin.",
            "minikube start -p autoscaleops --driver=docker --memory=8192"
        ),
        (
            ["helm", "chart", "release", "already exists"],
            "Hata: Helm Release Çakışması",
            "Aynı isimde bir Helm release zaten mevcut.\n"
            "1. Projeyi farklı bir adla deploy edin.\n"
            "2. Veya mevcut release'i silip tekrar deneyin:",
            "helm uninstall <proje-adi> -n autoscaleops"
        ),
        (
            ["timeout", "timed out", "deadline exceeded", "rollout"],
            "Hata: Pod Hazır Olmadı (Timeout)",
            "Pod'lar belirtilen sürede ayağa kalkmadı.\n"
            "1. Uygulama başlatma süreniz 3 dakikayı aşıyor olabilir.\n"
            "2. Pod loglarına bakarak asıl hatayı bulun:",
            "kubectl logs -l app=<proje-adi> -n autoscaleops --tail=50"
        ),
        (
            ["dockerfile", "no such file", "not found in context", "unable to prepare context"],
            "Hata: Dockerfile Oluşturulamadı",
            "Uygulama Dockerfile'ı oluşturamadı veya okuyamadı.\n"
            "1. Klasörde geçerli bir requirements.txt, package.json veya index.html var mı?\n"
            "2. Klasöre yazma iznin var mı?\n"
            "3. Farklı bir klasör seçin.",
            ""
        ),
    ]

    def _show_deploy_help(self, error_msg: str):
        """Hata metnini analiz et, uygun yardım kartını göster."""
        if not hasattr(self, '_help_panel'):
            return
        err_lower = error_msg.lower()
        matched = None
        for patterns, category, steps, cmd in self._DEPLOY_ERRORS:
            if any(p in err_lower for p in patterns):
                matched = (category, steps, cmd)
                break
        if matched is None:
            matched = (
                "Bilinmeyen Hata",
                "Bu hata otomatik tanınamadı.\n"
                "1. Deploy günlüğündeki kırmızı satırı kopyalayıp aratın.\n"
                "2. Cluster ve Docker Desktop'un çalıştığından emin olun.\n"
                "3. Sorunu çözemezseniz günlüğü paylaşarak destek isteyin.",
                "kubectl get events -n autoscaleops --sort-by=.lastTimestamp"
            )
        category, steps, cmd = matched
        self._help_category.setText(f"Tespit: {category}")
        self._help_steps.setText(steps)
        if cmd:
            self._help_cmd_lbl.setText(cmd)
            self._help_cmd.setVisible(True)
        else:
            self._help_cmd.setVisible(False)
        self._help_panel.setVisible(True)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
def main():
    # Ensure app dir exists
    APP_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)

    # ── Tek instance kontrolü ────────────────────────────────────────────────
    # Eğer uygulama zaten açıksa, mevcut pencereyi öne getir ve çık.
    SINGLE_INSTANCE_KEY = "AutoScaleOps_SingleInstance_v2"

    # Önce mevcut bir instance var mı diye bak
    socket_check = QLocalSocket()
    socket_check.connectToServer(SINGLE_INSTANCE_KEY)
    if socket_check.waitForConnected(500):
        # Başka bir instance çalışıyor — ona "öne gel" sinyali gönder
        socket_check.write(b"SHOW")
        socket_check.waitForBytesWritten(500)
        socket_check.disconnectFromServer()
        # Bu instance kapansın
        sys.exit(0)
    socket_check.deleteLater()

    # İlk instance — local server aç, sonraki instance'ları dinle
    local_server = QLocalServer()
    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)   # stale socket temizle
    local_server.listen(SINGLE_INSTANCE_KEY)

    # ── Uygulama başlat ──────────────────────────────────────────────────────
    # Apply global stylesheet
    app.setStyleSheet(STYLESHEET)

    # Set font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    controller = AppController()
    controller.show()

    # Başka bir instance bağlanırsa pencereyi öne getir
    def _on_new_connection():
        conn = local_server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(300)
            conn.readAll()   # "SHOW" mesajını oku (içerik önemli değil)
            conn.disconnectFromServer()
        # Pencereyi öne getir
        controller.setWindowState(
            controller.windowState() & ~Qt.WindowState.WindowMinimized
        )
        controller.show()
        controller.raise_()
        controller.activateWindow()

    local_server.newConnection.connect(_on_new_connection)

    ret = app.exec()
    local_server.close()
    sys.exit(ret)


if __name__ == "__main__":
    main()
