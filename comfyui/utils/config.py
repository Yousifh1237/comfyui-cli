"""Configuration management for comfyui-cli."""

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8188,
    "ssl": False,
    "default_output_dir": "./output",
    "poll_interval": 1.0,
    "timeout": 600.0,
}

CONFIG_FILENAME = ".comfyui-cli.json"


def get_config_path() -> Path:
    """Get the config file path (user home directory)."""
    return Path.home() / CONFIG_FILENAME


def load_config() -> dict[str, Any]:
    """Load configuration from file, falling back to defaults."""
    config = dict(DEFAULT_CONFIG)
    path = get_config_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to file."""
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_server_args(config: dict) -> dict:
    """Extract server connection arguments from config."""
    return {
        "host": config.get("host", DEFAULT_CONFIG["host"]),
        "port": config.get("port", DEFAULT_CONFIG["port"]),
        "use_ssl": config.get("ssl", DEFAULT_CONFIG["ssl"]),
    }
