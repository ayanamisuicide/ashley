#!/usr/bin/env python3
"""
SONYA 3.0 Universal Launcher
Запускает GUI, если доступно. Иначе запускает Telegram-бота.
Можно форсировать режим: --gui или --bot
"""

import sys


def _can_use_gui() -> bool:
    """Check if tkinter + customtkinter are available."""
    try:
        import tkinter as tk  # noqa: F401
        import customtkinter  # noqa: F401
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


def run_bot() -> None:
    print("SONYA 3.0 - Telegram Bot Mode")
    print("=" * 40)
    print("Запускаю Telegram бота...")
    print("Если хотите GUI: python gui.py  (или --gui)")
    print()

    from bot import main as bot_main
    bot_main()


def run_gui() -> None:
    print("SONYA 3.0 - GUI Mode")
    print("=" * 40)
    print("Запускаю GUI...")
    print()

    from gui import AppManagerGUI
    app = AppManagerGUI()
    app.run()


def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]

    force_gui = "--gui" in args
    force_bot = "--bot" in args

    try:
        if force_gui and force_bot:
            print("Ошибка: нельзя одновременно --gui и --bot")
            sys.exit(2)

        if force_gui:
            if not _can_use_gui():
                print("GUI недоступен в этой системе. Запускаю бота вместо GUI.")
                run_bot()
            else:
                run_gui()
            return

        if force_bot:
            run_bot()
            return

        if _can_use_gui():
            run_gui()
        else:
            run_bot()

    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")
        try:
            from app_manager import get_manager
            manager = get_manager()
            manager.close_all_apps()
            manager.save_pids()
        except Exception:
            pass
        print("Спасибо за использование SONYA 💖")

    except Exception as e:
        print(f"Ошибка запуска: {e}")
        print("Проверь .env (TELEGRAM_BOT_TOKEN и ADMIN_ID) и зависимости.")
        try:
            input("Нажмите Enter для выхода...")
        except Exception:
            pass


if __name__ == "__main__":
    main()
