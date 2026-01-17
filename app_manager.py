"""
Configuration manager for application paths and settings.
Автоматически ищет приложения в системе или использует пользовательские пути.
"""

import copy
import json
import os
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger("config_manager")

CONFIG_FILE = "app_config.json"

DEFAULT_CONFIG = {
    "apps": {
        "dota": {
            "name": "Dota 2",
            "icon": "🎮",
            "path": "",
            "args": ["-applaunch", "570"],
            "process_name": "dota2.exe",
            "auto_detect": True,
            "search_paths": [
                r"C:\Program Files (x86)\Steam\steam.exe",
                r"C:\Program Files\Steam\steam.exe",
            ],
        },
        "spotify": {
            "name": "Spotify",
            "icon": "🎵",
            "path": "",
            "args": [],
            "process_name": "Spotify.exe",
            "auto_detect": True,
            "search_paths": [
                r"%APPDATA%\Spotify\Spotify.exe",
                r"C:\Users\{username}\AppData\Roaming\Spotify\Spotify.exe",
            ],
        },
        "discord": {
            "name": "Discord",
            "icon": "💬",
            "path": "",
            "args": [],
            "process_name": "Discord.exe",
            "auto_detect": True,
            "search_paths": [
                r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
                r"C:\Users\{username}\AppData\Local\Discord\app-*\Discord.exe",
            ],
        },
        "vscode": {
            "name": "VS Code",
            "icon": "💻",
            "path": "",
            "args": [],
            "process_name": "Code.exe",
            "auto_detect": True,
            "search_paths": [
                r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ],
        },
    },
    "settings": {
        "rate_limit_seconds": 2,
        "auto_save_pids": True,
        "log_level": "INFO",
    },
}


class ConfigManager:
    """Manages application configuration with auto-detection."""

    def __init__(self):
        self.config = self.load_config()
        changed = self.auto_detect_apps()
        if changed:
            self.save_config()

    def load_config(self) -> Dict:
        """Load configuration from file or create default."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                logger.info(f"Конфигурация загружена из {CONFIG_FILE}")
                return self._merge_with_defaults(config)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка чтения конфигурации: {e}")
                return copy.deepcopy(DEFAULT_CONFIG)
        else:
            logger.info("Создан новый конфиг с настройками по умолчанию")
            return copy.deepcopy(DEFAULT_CONFIG)

    def _merge_with_defaults(self, config: Dict) -> Dict:
        """Merge loaded config with defaults to add new apps/settings."""
        merged = copy.deepcopy(DEFAULT_CONFIG)

        if "settings" in config:
            merged["settings"].update(config["settings"])

        if "apps" in config:
            for app_name, app_data in config["apps"].items():
                if app_name in merged["apps"]:
                    merged["apps"][app_name].update(app_data)
                else:
                    merged["apps"][app_name] = app_data

        return merged

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info(f"Конфигурация сохранена в {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")

    def auto_detect_apps(self) -> bool:
        """Auto-detect installed applications. Returns True if config changed."""
        changed = False
        username = os.getenv("USERNAME", "Administrator")

        for app_name, app_data in self.config["apps"].items():
            if not app_data.get("auto_detect", True):
                continue

            # Если путь уже указан и существует, пропускаем
            if app_data.get("path") and os.path.exists(self._expand_path(app_data["path"])):
                continue

            found_path = self._find_app(app_data.get("search_paths", []), username)
            if found_path:
                self.config["apps"][app_name]["path"] = found_path
                changed = True
                logger.info(f"✓ {app_name}: найден в {found_path}")
            else:
                logger.warning(f"✗ {app_name}: не найден")

        return changed

    def _find_app(self, search_paths: List[str], username: str) -> Optional[str]:
        """Find application in search paths."""
        for path_template in search_paths:
            expanded = self._expand_path(path_template.replace("{username}", username))

            if "*" in expanded:
                parent = str(Path(expanded).parent)
                pattern = Path(expanded).name

                if os.path.exists(parent):
                    for item in Path(parent).glob(pattern):
                        if item.is_file():
                            return str(item)
            else:
                if os.path.exists(expanded):
                    return expanded

        return None

    def _expand_path(self, path: str) -> str:
        return os.path.expandvars(path)

    def get_app_config(self, app_name: str) -> Optional[Dict]:
        return self.config["apps"].get(app_name)

    def get_app_command(self, app_name: str) -> Optional[List[str]]:
        app_config = self.get_app_config(app_name)
        if not app_config or not app_config.get("path"):
            return None

        path = self._expand_path(app_config["path"])
        if not os.path.exists(path):
            logger.error(f"Путь не существует: {path}")
            return None

        return [path] + app_config.get("args", [])

    def get_process_name(self, app_name: str) -> Optional[str]:
        app_config = self.get_app_config(app_name)
        return app_config.get("process_name") if app_config else None

    def get_all_apps(self) -> Dict:
        return self.config["apps"]

    def update_app_path(self, app_name: str, new_path: str) -> bool:
        if app_name in self.config["apps"]:
            if os.path.exists(new_path):
                self.config["apps"][app_name]["path"] = new_path
                self.save_config()
                logger.info(f"Обновлен путь для {app_name}: {new_path}")
                return True
            else:
                logger.error(f"Путь не существует: {new_path}")
                return False
        return False

    def get_setting(self, key: str, default=None):
        return self.config.get("settings", {}).get(key, default)


_config_manager: Optional["ConfigManager"] = None


def get_config() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    config = get_config()
    print("\n=== Конфигурация приложений ===")
    for app_name, app_data in config.get_all_apps().items():
        status = "✓" if app_data.get("path") else "✗"
        print(f"{status} {app_data['name']}: {app_data.get('path', 'не найден')}")

    print("\n=== Команды запуска ===")
    for app_name in config.get_all_apps().keys():
        cmd = config.get_app_command(app_name)
        if cmd:
            print(f"{app_name}: {' '.join(cmd)}")
