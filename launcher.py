#!/usr/bin/env python3
"""
Improved Launcher with better validation and error handling.
Works even without customtkinter to show installation instructions.
"""

import sys
import os
from pathlib import Path

# Proverka zavisimostey PERED importom GUI
def check_and_install_dependencies():
    """Check dependencies and offer to install them."""
    required = {
        'customtkinter': 'customtkinter',
        'telegram': 'python-telegram-bot',
        'dotenv': 'python-dotenv',
        'psutil': 'psutil'
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        # In exe mode, just warn and continue
        print(f"WARNING: Missing packages: {', '.join(missing)}")
        print("This is exe mode - dependencies should be included...")
        # Don't return False, continue to GUI
    
    return True

# Proveryaem zavisimosti pered importom
if not check_and_install_dependencies():
    sys.exit(1)

# Proveryaem tkinter pered importom customtkinter
try:
    import tkinter
    tkinter.Tk().withdraw()
    tkinter.Tk().destroy()
    GUI_AVAILABLE = True
except:
    print("GUI not available, running in console mode...")
    GUI_AVAILABLE = False

if not GUI_AVAILABLE:
    # Zapuskaem v konsolnom rezhime bez GUI
    import main_universal
    main_universal.main()
    sys.exit(0)

# Teper mozhno importirovat customtkinter
import threading
import time
from typing import List
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
    """Beautiful launcher GUI with validation."""

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
        """Create the UI."""
        main_frame = ctk.CTkFrame(
            self.root, fg_color=COLORS["bg_card"], corner_radius=20)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(30, 20))

        title_label = ctk.CTkLabel(
            header_frame,
            text="SONYA LAUNCHER",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        title_label.pack(pady=(0, 5))

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Telegram Bot Manager",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_dim"]
        )
        subtitle_label.pack()

        # Progress section
        progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        progress_frame.pack(fill="x", padx=40, pady=(20, 10))

        self.status_label = ctk.CTkLabel(
            progress_frame,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_main"]
        )
        self.status_label.pack(pady=(0, 15))

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            variable=self.progress_var,
            width=400,
            height=20,
            corner_radius=10,
            fg_color=COLORS["bg_dark"],
            progress_color=COLORS["accent_blue"]
        )
        self.progress_bar.pack()

        self.progress_text_label = ctk.CTkLabel(
            progress_frame,
            textvariable=self.progress_text_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["accent_blue"]
        )
        self.progress_text_label.pack(pady=(5, 0))

        # Error section
        error_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        error_frame.pack(fill="x", padx=40, pady=(10, 20))

        self.error_label = ctk.CTkLabel(
            error_frame,
            textvariable=self.error_var,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["danger"],
            wraplength=400
        )
        self.error_label.pack()

        # Footer
        footer_label = ctk.CTkLabel(
            main_frame,
            text="Created with love for Kris",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_dim"]
        )
        footer_label.pack(pady=(10, 20))

    def update_progress(self, value: float, status: str):
        """Update progress bar and status."""
        try:
            if not self.launch_complete:
                self.progress_var.set(value)
                self.status_var.set(status)
                self.progress_text_var.set(f"{int(value)}%")
                self.root.update()
        except:
            pass

    def animate_progress(self, start_value: float, end_value: float, status: str, duration: float = 1.0):
        """Animate progress from start to end value."""
        if start_value >= end_value:
            self.update_progress(end_value, status)
            return

        steps = int(end_value - start_value)
        step_duration = duration / steps if steps > 0 else duration

        for i in range(steps + 1):
            current_value = start_value + i
            self.update_progress(current_value, status)
            time.sleep(step_duration)

    def show_error(self, error: str):
        """Show error message."""
        try:
            if not self.launch_complete:
                self.error_var.set(f"ERROR: {error}")
                self.root.update()
        except:
            pass

    def check_env_file(self) -> bool:
        """Check if .env file exists and has required variables."""
        env_path = Path('.env')
        
        if not env_path.exists():
            self.show_error(".env файл не найден! Создай его из .env.example")
            return False

        # Читаем и проверяем содержимое
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Проверяем наличие и валидность переменных
            errors = []
            
            if 'TELEGRAM_BOT_TOKEN=' not in content:
                errors.append("TELEGRAM_BOT_TOKEN отсутствует")
            elif 'TELEGRAM_BOT_TOKEN=your_bot_token_here' in content or \
                 'TELEGRAM_BOT_TOKEN=' in content and not any(c.isdigit() for c in content.split('TELEGRAM_BOT_TOKEN=')[1].split('\n')[0]):
                errors.append("TELEGRAM_BOT_TOKEN не настроен")
            
            if 'ADMIN_ID=' not in content:
                errors.append("ADMIN_ID отсутствует")
            elif 'ADMIN_ID=your_telegram_id_here' in content or \
                 'ADMIN_ID=' in content and not content.split('ADMIN_ID=')[1].split('\n')[0].strip().isdigit():
                errors.append("ADMIN_ID не настроен (должен быть числом)")
            
            if errors:
                self.show_error("Ошибки в .env:\n" + "\n".join(errors))
                return False
            
            return True
            
        except Exception as e:
            self.show_error(f"Ошибка чтения .env: {e}")
            return False

    def launch_main_app(self):
        """Launch the main GUI application."""
        try:
            from gui import AppManagerGUI
            app = AppManagerGUI()
            self.root.destroy()
            app.run()
        except Exception as e:
            self.show_error(f"Ошибка запуска: {e}")

    def launch_process(self):
        """Main launch process."""
        try:
            current_progress = 0

            # Step 1: Check files
            self.animate_progress(current_progress, 10, "Проверка файлов проекта...", 0.5)
            current_progress = 10
            time.sleep(0.3)
            
            required_files = ['gui.py', 'bot.py', 'app_manager.py', 'config.py', 'responses.py']
            missing_files = [f for f in required_files if not Path(f).exists()]
            
            if missing_files:
                self.show_error(f"Отсутствуют файлы: {', '.join(missing_files)}")
                return

            # Step 2: Check .env
            self.animate_progress(current_progress, 50, "Проверка конфигурации...", 1.0)
            current_progress = 50
            time.sleep(0.5)
            
            if not self.check_env_file():
                return
            
            self.animate_progress(current_progress, 70, "Конфигурация OK ✓", 0.5)
            current_progress = 70

            # Step 3: Initialize config
            self.animate_progress(current_progress, 90, "Инициализация конфигурации...", 0.5)
            current_progress = 90
            time.sleep(0.3)
            
            try:
                from config import get_config
                config = get_config()
                self.animate_progress(current_progress, 100, "Готово! Запуск...", 0.3)
            except Exception as e:
                self.show_error(f"Ошибка инициализации: {e}")
                return

            # Step 4: Launch
            time.sleep(0.5)
            self.root.after(100, self.launch_main_app)

        except Exception as e:
            self.show_error(f"Неожиданная ошибка: {e}")

    def start_launch(self):
        """Start the launch process in background thread."""
        thread = threading.Thread(target=self.launch_process, daemon=True)
        thread.start()

    def run(self):
        self.root.mainloop()


def main():
    """Main launcher function."""
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