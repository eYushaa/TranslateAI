"""Uygulama veri dizinleri."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def data_dir() -> Path:
    """Ayar, geçmiş ve günlük dosyalarının tutulduğu dizin (%APPDATA%\\TranslateAI)."""
    override = os.environ.get("TRANSLATEAI_HOME") or os.environ.get("AITRANSLATOR_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def settings_path() -> Path:
    return data_dir() / "settings.json"


def history_path() -> Path:
    return data_dir() / "history.jsonl"


def log_path() -> Path:
    return data_dir() / "translateai.log"


def secrets_path() -> Path:
    return data_dir() / "secrets.dpapi.json"


def app_dir() -> Path:
    """Uygulamanın çalıştığı dizin (paketlenmiş .exe için yürütülebilir dosya dizini, aksi hâlde çalışma dizini)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def models_dir() -> Path:
    """Yerel .gguf modellerinin bulunduğu dizin (<app_dir>\\models)."""
    override = os.environ.get("TRANSLATEAI_MODELS_DIR") or os.environ.get("AITRANSLATOR_MODELS_DIR")
    base = Path(override) if override else app_dir() / "models"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return base
