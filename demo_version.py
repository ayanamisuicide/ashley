#!/usr/bin/env python3
"""
Демонстрация работы системы версионирования SONYA
"""

from version_manager import VersionManager

def main():
    print("🎯 Демонстрация системы версионирования SONYA")
    print("=" * 50)

    vm = VersionManager()

    # Показать текущую версию
    current = vm.get_current_version()
    print(f"📋 Текущая версия: {current}")

    # Показать следующую patch версию
    next_patch = vm.bump_version('patch')
    print(f"📋 Следующая patch версия: {next_patch}")

    # Показать следующую minor версию
    next_minor = vm.bump_version('minor')
    print(f"📋 Следующая minor версия: {next_minor}")

    # Показать следующую major версию
    next_major = vm.bump_version('major')
    print(f"📋 Следующая major версия: {next_major}")

    print("\n✅ Система версионирования работает корректно!")
    print("\n📖 Для создания нового релиза используйте:")
    print("   python version_manager.py bump --type patch")
    print("   python version_manager.py bump --type minor")
    print("   python version_manager.py bump --type major")

if __name__ == "__main__":
    main()</content>
</xai:function_call">Создам демонстрационный скрипт для показа работы системы версионирования