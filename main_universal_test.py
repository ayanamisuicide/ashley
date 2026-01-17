#!/usr/bin/env python3
"""
Тестовый загрузчик SONYA - всегда запускает GUI
"""

import sys
import os

def main():
    """Главная функция загрузчика."""
    print("SONYA 3.0 - GUI Test Mode")
    print("=" * 40)

    try:
        print("Zapuskayu GUI...")
        from gui import AppManagerGUI
        print("Import AppManagerGUI - OK")
        app = AppManagerGUI()
        print("GUI initsializirovan, zapuskayu mainloop...")
        app.run()
    except Exception as e:
        print(f"❌ Ошибка запуска GUI: {e}")
        print(f"Тип ошибки: {type(e)}")
        import traceback
        traceback.print_exc()
        input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()