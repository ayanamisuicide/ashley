#!/usr/bin/env python3
"""
SONYA Launcher
- Проверяет зависимости/файлы/.env
- Запускает GUI через main_universal.run_gui() (единая точка входа)
- Если GUI недоступен, запускает main_universal.run_bot()
"""

import sys
from pathlib import Path
import importlib.util
import threading
import time


def is_frozen_exe() -> bool:
    return bool(getattr(sys, "frozen", False))


def module_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def check_dependencies() -> list[str]:
    required = {
        "customtkinter": "customtkinter",
        "telegram": "python-telegram-bot",
        "dotenv": "python-dotenv",
        "psutil": "psutil",
    }

    missing = []
    for module, package in required.items():
        if not module_exists(module):
            missing.append(package)
    return missing


def can_use_tkinter() -> bool:
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


missing = check_dependencies()
if missing:
    print(f"WARNING: Missing packages: {', '.join(missing)}")
    if not is_frozen_exe():
        print("Install them with:")
        print(f"  pip install {' '.join(missing)}")
    else:
        print("Running in EXE mode: dependencies should be bundled inside the build.")


GUI_AVAILABLE = can_use_tkinter()

if not GUI_AVAILABLE:
    print("GUI not available, running in console mode...")
    import main_universal
    main_universal.run_bot()
    sys.exit(0)


import customtkinter as ctk

COLORS = {
    "bg_dark": "#0a0e1a",
    "bg_card": "#151a2e",
    "bg_card_hover": "#1a2038",
    "accent_blue": "#00d4ff",
    "accent_purple": "#a855f7",
    "accent_pink": "#ec4899",
    "text_main": "#ffffff",
    "text_dim": "#94a3b8",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
}


class LauncherGUI:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("SONYA LAUNCHER")
        self.root.geometry("500x450")
        self.root.resizable(False, False)
        self.root.configure(fg_color=COLORS["bg_dark"])

        self.progress_var = ctk.DoubleVar(value=0)
        self.status_var = ctk.StringVar(value="Инициализация...")
        self.error_var = ctk.StringVar(value="")
        self.progress_text_var = ctk.StringVar(value="0%")
        self.launch_complete = False

        self.create_ui()
        self.start_launch()

    def create_ui(self):
        main_frame = ctk.CTkFrame(self.root, fg_color=COLORS["bg_card"], corner_radius=20)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(30, 20))

        title_label = ctk.CTkLabel(
            header_frame,
            text="SONYA LAUNCHER",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["accent_blue"],
        )
        title_label.pack(pady=(0, 5))

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Telegram Bot Manager",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_dim"],
        )
        subtitle_label.pack()

        progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=40, pady=(20, 10))

        self.status_label = ctk.CTkLabel(
            progress_frame,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_main"],
        )
        self.status_label.pack(pady=(0, 15))

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            variable=self.progress_var,
            width=400,
            height=20,
            corner_radius=10,
            fg_color=COLORS["bg_dark"],
            progress_color=COLORS["accent_blue"],
        )
        self.progress_bar.pack()

        self.progress_text_label = ctk.CTkLabel(
            progress_frame,
            textvariable=self.progress_text_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["accent_blue"],
        )
        self.progress_text_label.pack(pady=(5, 0))

        error_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        error_frame.pack(fill="x", padx=40, pady=(10, 20))

        self.error_label = ctk.CTkLabel(
            error_frame,
            textvariable=self.error_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["danger"],
            wraplength=400,
        )
        self.error_label.pack()

        footer_label = ctk.CTkLabel(
            main_frame,
            text="Created with love for Kris",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_dim"],
        )
        footer_label.pack(pady=(10, 20))

    # Thread-safe UI calls
    def _ui(self, fn, *args):
        try:
            self.root.after(0, lambda: fn(*args))
        except Exception:
            pass

    def _set_progress(self, value: float, status: str):
        if self.launch_complete:
            return
        self.progress_var.set(value)
        self.status_var.set(status)
        self.progress_text_var.set(f"{int(value)}%")

    def update_progress(self, value: float, status: str):
        self._ui(self._set_progress, value, status)

    def _set_error(self, error: str):
        if self.launch_complete:
            return
        self.error_var.set(f"ERROR: {error}")

    def show_error(self, error: str):
        self._ui(self._set_error, error)

    def check_env_file(self) -> bool:
        env_path = Path(".env")

        if not env_path.exists():
            self.show_error(".env файл не найден! Создай его из .env.example")
            return False

        try:
            content = env_path.read_text(encoding="utf-8", errors="ignore")

            def get_value(key: str) -> str:
                for line in content.splitlines():
                    if line.strip().startswith(key + "="):
                        return line.split("=", 1)[1].strip()
                return ""

            token = get_value("TELEGRAM_BOT_TOKEN")
            admin_id = get_value("ADMIN_ID")

            errors = []
            if not token or token == "your_bot_token_here":
                errors.append("TELEGRAM_BOT_TOKEN не настроен")

            if not admin_id or admin_id == "your_telegram_id_here" or not admin_id.isdigit():
                errors.append("ADMIN_ID не настроен (должен быть числом)")

            if errors:
                self.show_error("Ошибки в .env:\n" + "\n".join(errors))
                return False

            return True
        except Exception as e:
            self.show_error(f"Ошибка чтения .env: {e}")
            return False

    def animate_progress(self, start_value: float, end_value: float, status: str, duration: float = 1.0):
        if start_value >= end_value:
            self.update_progress(end_value, status)
            return

        steps = max(1, int(end_value - start_value))
        step_duration = duration / steps if steps > 0 else duration

        for i in range(steps + 1):
            self.update_progress(start_value + i, status)
            time.sleep(step_duration)

    def launch_main_app(self):
        """Launch GUI via main_universal (single source of truth)."""
        try:
            import main_universal
            self.launch_complete = True
            self.root.destroy()
            main_universal.run_gui()
        except Exception as e:
            self.show_error(f"Ошибка запуска GUI: {e}")

    def launch_process(self):
        try:
            current_progress = 0

            self.animate_progress(current_progress, 10, "Проверка файлов проекта...", 0.5)
            current_progress = 10
            time.sleep(0.2)

            required_files = ["gui.py", "bot.py", "app_manager.py", "config.py", "responses.py", "main_universal.py"]
            missing_files = [f for f in required_files if not Path(f).exists()]
            if missing_files:
                self.show_error(f"Отсутствуют файлы: {', '.join(missing_files)}")
                return

            self.animate_progress(current_progress, 50, "Проверка конфигурации...", 1.0)
            current_progress = 50
            time.sleep(0.2)

            if not self.check_env_file():
                return

            self.animate_progress(current_progress, 70, "Конфигурация OK ✓", 0.5)
            current_progress = 70

            self.animate_progress(current_progress, 90, "Инициализация конфигурации...", 0.5)
            current_progress = 90
            time.sleep(0.2)

            try:
                from config import get_config
                _ = get_config()
            except Exception as e:
                self.show_error(f"Ошибка инициализации: {e}")
                return

            self.animate_progress(current_progress, 100, "Готово! Запуск...", 0.3)
            time.sleep(0.4)

            self._ui(self.launch_main_app)

        except Exception as e:
            self.show_error(f"Неожиданная ошибка: {e}")

    def start_launch(self):
        thread = threading.Thread(target=self.launch_process, daemon=True)
        thread.start()

    def run(self):
        self.root.mainloop()


def main():
    try:
        app = LauncherGUI()
        app.run()
    except Exception as e:
        print(f"\n❌ Ошибка запуска лаунчера: {e}")
        print("\n💡 Попробуй запустить gui.py напрямую:")
        print("   python gui.py")
        input("\nНажми Enter для выхода...")


if __name__ == "__main__":
    main()
