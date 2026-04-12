"""
autoscaleops.config
-------------------
autoscaleops.yaml dosyasını yükler, doğrular ve her yere dağıtır.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("autoscaleops.yaml")

# ─── Varsayılan değerler ──────────────────────────────────────────────────────

DEFAULTS: dict[str, Any] = {
    "project": {
        "name": "myapp",
        "namespace": "autoscaleops",
    },
    "app": {
        "image": "myapp:latest",
        "port": 8080,
        "replicas": {
            "min": 2,
            "max": 10,
        },
    },
    "metrics": {
        "prometheus_url": "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090",
        "pushgateway_url": "http://pushgateway.monitoring.svc.cluster.local:9091",
        "source_metric": "http_requests_total",
        "prediction_metric": "predicted_rps_30min",
    },
    "arima": {
        "forecast_horizon": 5,
        "ci_level": 0.95,
        "retrain_every": 30,
        "min_data_points": 30,
    },
    "keda": {
        "threshold": 10,
        "polling_interval": 15,
        "cooldown_period": 60,
    },
    "resources": {
        "app": {
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"},
        },
        "predictor": {
            "requests": {"cpu": "200m", "memory": "256Mi"},
            "limits": {"cpu": "1000m", "memory": "1Gi"},
        },
    },
}


# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """İki dict'i derinlemesine birleştirir; override değerleri önceliklidir."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ─── Ana sınıf ────────────────────────────────────────────────────────────────

class AutoScaleOpsConfig:
    """
    Kullanıcının autoscaleops.yaml dosyasını yükler ve doğrular.

    Kullanım:
        cfg = AutoScaleOpsConfig.load()
        print(cfg.project_name)
        print(cfg.arima_ci_level)
    """

    def __init__(self, data: dict):
        self._data = data

    # ── Kolay erişim property'leri ────────────────────────────────────────────

    @property
    def project_name(self) -> str:
        return self._data["project"]["name"]

    @property
    def namespace(self) -> str:
        return self._data["project"]["namespace"]

    @property
    def app_image(self) -> str:
        return self._data["app"]["image"]

    @property
    def app_port(self) -> int:
        return int(self._data["app"]["port"])

    @property
    def min_replicas(self) -> int:
        return int(self._data["app"]["replicas"]["min"])

    @property
    def max_replicas(self) -> int:
        return int(self._data["app"]["replicas"]["max"])

    @property
    def prometheus_url(self) -> str:
        return self._data["metrics"]["prometheus_url"]

    @property
    def pushgateway_url(self) -> str:
        return self._data["metrics"]["pushgateway_url"]

    @property
    def source_metric(self) -> str:
        return self._data["metrics"]["source_metric"]

    @property
    def prediction_metric(self) -> str:
        return self._data["metrics"]["prediction_metric"]

    @property
    def forecast_horizon(self) -> int:
        return int(self._data["arima"]["forecast_horizon"])

    @property
    def ci_level(self) -> float:
        return float(self._data["arima"]["ci_level"])

    @property
    def retrain_every(self) -> int:
        return int(self._data["arima"]["retrain_every"])

    @property
    def min_data_points(self) -> int:
        return int(self._data["arima"]["min_data_points"])

    @property
    def keda_threshold(self) -> int:
        return int(self._data["keda"]["threshold"])

    @property
    def keda_polling_interval(self) -> int:
        return int(self._data["keda"]["polling_interval"])

    @property
    def keda_cooldown(self) -> int:
        return int(self._data["keda"]["cooldown_period"])

    def get(self, *keys, default=None):
        """Nested key erişimi: cfg.get('resources', 'app', 'limits')"""
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)
            if node is default:
                return default
        return node

    def to_env(self) -> dict[str, str]:
        """Predictor pod'una geçirilecek env değişkenleri."""
        return {
            "PROMETHEUS_URL":        self.prometheus_url,
            "PUSHGATEWAY_URL":       self.pushgateway_url,
            "SOURCE_METRIC":         self.source_metric,
            "PREDICTION_METRIC":     self.prediction_metric,
            "FORECAST_HORIZON":      str(self.forecast_horizon),
            "CI_LEVEL":              str(self.ci_level),
            "RETRAIN_EVERY":         str(self.retrain_every),
            "MIN_DATA_POINTS":       str(self.min_data_points),
        }

    # ── Yükleme ───────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "AutoScaleOpsConfig":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"autoscaleops.yaml bulunamadı: {path.resolve()}\n"
                f"Yeni proje oluşturmak için: autoscaleops init"
            )
        with open(path, "r", encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}

        merged = _deep_merge(DEFAULTS, user_data)
        instance = cls(merged)
        instance._validate()
        return instance

    def _validate(self):
        errors = []

        if not self.project_name or self.project_name == "myapp":
            errors.append("project.name henüz değiştirilmemiş ('myapp'). Gerçek uygulama adını gir.")

        if self.min_replicas < 1:
            errors.append("app.replicas.min en az 1 olmalı.")

        if self.max_replicas <= self.min_replicas:
            errors.append("app.replicas.max, min'den büyük olmalı.")

        if not (0.5 <= self.ci_level <= 0.99):
            errors.append("arima.ci_level 0.50 ile 0.99 arasında olmalı.")

        if self.forecast_horizon < 1:
            errors.append("arima.forecast_horizon en az 1 olmalı.")

        if errors:
            msg = "\n".join(f"  • {e}" for e in errors)
            raise ValueError(f"autoscaleops.yaml hataları:\n{msg}")

    def __repr__(self) -> str:
        return (
            f"AutoScaleOpsConfig("
            f"project={self.project_name!r}, "
            f"namespace={self.namespace!r}, "
            f"metric={self.source_metric!r})"
        )
