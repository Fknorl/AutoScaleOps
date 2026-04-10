# ═══════════════════════════════════════════════════════════════════════════
# TunnelManager — ngrok + Cloudflare Tunnel Management
# AutoScaleOps · core/tunnel_manager.py
#
# Usage (from autoscaleops_app.py SystemOps):
#   tm = TunnelManager()
#   ok, url = tm.start_ngrok(token="...", port=8080)
#   ok, url = tm.start_cloudflare(port=8080, domain="app.example.com")
#   tm.stop()
#   url = tm.get_url()
#
# NOTE: autoscaleops_app.py::SystemOps already embeds the tunnel logic
# inline. This module exists as the standalone authoritative implementation
# that can be imported by other components (dashboard, control-panel, etc.)
# ═══════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)


def _run_ps(cmd: str, timeout: int = 10) -> str:
    """PowerShell komutunu çalıştır, stdout döndür."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout
        )
        return r.stdout.strip()
    except Exception as e:
        logger.error("PS error: %s", e)
        return ""


class TunnelManager:
    """ngrok ve Cloudflare tunnel yöneticisi."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._url: Optional[str] = None
        self._kind: Optional[str] = None   # "ngrok" | "cloudflare"

    # ── PUBLIC API ───────────────────────────────────────────────────────────

    def start_ngrok(
        self,
        port: int = 8080,
        token: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        ngrok HTTP tünel başlat.

        Args:
            port:  Expose edilecek local port (varsayılan 8080).
            token: ngrok auth token (free tier için opsiyonel).

        Returns:
            (True, public_url) başarılıysa,
            (False, error_msg) başarısızsa.
        """
        self.stop()
        if token:
            _run_ps(f"ngrok config add-authtoken {token} 2>&1")

        try:
            self._proc = subprocess.Popen(
                ["ngrok", "http", str(port), "--log", "stdout", "--log-format", "json"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )
            self._kind = "ngrok"

            # ngrok API üzerinden URL al (maks 10 saniye bekle)
            for _ in range(10):
                time.sleep(1)
                url = self._fetch_ngrok_url()
                if url:
                    self._url = url
                    logger.info("ngrok tunnel started: %s", url)
                    return True, url

            return False, "ngrok başlatıldı ancak URL algılanamadı — token eksik olabilir veya ngrok PATH'te değil"
        except FileNotFoundError:
            return False, (
                "ngrok bulunamadı — lütfen kurun:\n"
                "  1. https://ngrok.com/download adresinden Windows ZIP indirin\n"
                "  2. ngrok.exe dosyasını C:\\ngrok\\ içine koyun\n"
                "  3. PATH'e ekleyin: Sistem Değişkenleri → Path → C:\\ngrok"
            )
        except Exception as e:
            return False, str(e)

    def start_cloudflare(
        self,
        port: int = 8080,
        domain: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Cloudflare Tunnel başlat.

        Domain olmadan: otomatik *.trycloudflare.com URL (ücretsiz, geçici).
        Domain ile:     kalıcı URL (Cloudflare hesabı + DNS ayarı gerekli).

        Args:
            port:   Expose edilecek local port (varsayılan 8080).
            domain: Opsiyonel özel domain (örn. "app.example.com").

        Returns:
            (True, public_url) başarılıysa,
            (False, error_msg) başarısızsa.
        """
        self.stop()
        try:
            self._proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )
            self._kind = "cloudflare"

            # cloudflared stdout'undan URL'yi parse et (maks 20 saniye)
            url: Optional[str] = None
            start = time.time()
            while time.time() - start < 20:
                line = self._proc.stdout.readline()
                if not line:
                    break
                m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
                if m:
                    url = m.group(0)
                    break

            if url:
                self._url = f"https://{domain}" if domain else url
                logger.info("Cloudflare tunnel started: %s", self._url)
                return True, self._url

            return False, (
                "cloudflared başlatıldı ancak URL algılanamadı — "
                "birkaç saniye bekleyip tekrar deneyin"
            )
        except FileNotFoundError:
            return False, (
                "cloudflared bulunamadı — lütfen kurun:\n"
                "  https://developers.cloudflare.com/cloudflare-one/connections/"
                "connect-apps/install-and-setup"
            )
        except Exception as e:
            return False, str(e)

    def stop(self) -> None:
        """Aktif tüneli durdur, tüm ngrok/cloudflared süreçlerini temizle."""
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        self._url = None
        self._kind = None
        _run_ps("Get-Process -Name ngrok        -ErrorAction SilentlyContinue | Stop-Process -Force 2>&1")
        _run_ps("Get-Process -Name cloudflared  -ErrorAction SilentlyContinue | Stop-Process -Force 2>&1")
        logger.info("Tunnel stopped")

    def get_url(self) -> Optional[str]:
        """Aktif tünel URL'ini döndür (ngrok ise API'den taze al)."""
        if self._kind == "ngrok":
            fresh = self._fetch_ngrok_url()
            if fresh:
                self._url = fresh
        return self._url

    def is_running(self) -> bool:
        """Tünel aktif mi?"""
        if self._proc is None:
            return False
        return self._proc.poll() is None

    # ── PRIVATE ──────────────────────────────────────────────────────────────

    def _fetch_ngrok_url(self) -> Optional[str]:
        """ngrok local API (port 4040) üzerinden public URL'i al."""
        try:
            r = requests.get("http://localhost:4040/api/tunnels", timeout=3)
            for t in r.json().get("tunnels", []):
                if "public_url" in t:
                    return t["public_url"]
        except Exception:
            pass
        return None
