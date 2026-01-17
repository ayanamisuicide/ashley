#!/usr/bin/env python3
"""
Универсальный загрузчик SONYA 3.0
Автоматически определяет режим запуска и импортирует нужные модули.
"""

import sys
import os
from pathlib import Path

def main():
    """Главная функция загрузчика - запускает Telegram бота."""
    print("SONYA 3.0 - Telegram Bot Mode")
    print("=" * 40)
    print("Zapuskayu Telegram bota...")
    print("Esli hotite GUI - zapustite otdelno: python gui.py")
    print()

    try:
        # Запускаем бота
        from bot import main as bot_main
        bot_main()
    except KeyboardInterrupt:
        print("\nBot ostanovlen polzovatelem")
        print("Spasibo za ispolzovanie SONYA!")
    except Exception as e:
        print(f"Oshibka zapuska bota: {e}")
        print("Proverte konfiguraciyu .env fayla")
        input("Nazhmite Enter dlya vykhoda...")

if __name__ == "__main__":
    main()