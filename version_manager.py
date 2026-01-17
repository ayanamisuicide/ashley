#!/usr/bin/env python3
"""
Version Manager для проекта SONYA.
Автоматически управляет версиями, changelog и обновляет файлы проекта.
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class VersionManager:
    """Управляет версиями и changelog проекта."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.changelog_path = self.project_root / "CHANGELOG.md"
        self.readme_path = self.project_root / "README.md"

    def get_current_version(self) -> str:
        """Получить текущую версию из README.md."""
        with open(self.readme_path, 'r', encoding='utf-8') as f:
            content = f.read()

        version_match = re.search(r'!\[Version\]\([^)]*version-([0-9]+\.[0-9]+\.[0-9]+)-[a-z]+\)', content)
        if version_match:
            return version_match.group(1)

        raise ValueError("Не удалось найти версию в README.md")

    def bump_version(self, bump_type: str = 'patch') -> str:
        """
        Увеличить версию.

        Args:
            bump_type: 'major', 'minor', или 'patch'

        Returns:
            Новая версия
        """
        current = self.get_current_version()
        major, minor, patch = map(int, current.split('.'))

        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        elif bump_type == 'patch':
            patch += 1
        else:
            raise ValueError(f"Неверный тип версии: {bump_type}")

        new_version = f"{major}.{minor}.{patch}"
        return new_version

    def update_readme_version(self, new_version: str, description: str = "") -> None:
        """Обновить версию в README.md."""
        with open(self.readme_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Обновить бейдж версии
        content = re.sub(
            r'!\[Version\]\([^)]*version-[0-9]+\.[0-9]+\.[0-9]+-blue\)',
            f'![Version](https://img.shields.io/badge/version-{new_version}-blue)',
            content
        )

        # Обновить текущую версию в секции версионирования
        content = re.sub(
            r'\*\*Версия:\*\* [0-9]+\.[0-9]+\.[0-9]+',
            f'**Версия:** {new_version}',
            content
        )

        # Обновить информацию в конце файла
        content = re.sub(
            r'\*\*Версия:\*\* [0-9]+\.[0-9]+\.[0-9]+ \([^)]+\)',
            f'**Версия:** {new_version} ({description})' if description else f'**Версия:** {new_version}',
            content
        )

        with open(self.readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def update_readme_stats(self, test_count: int, coverage: int) -> None:
        """Обновить статистику тестов в README.md."""
        with open(self.readme_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Обновить бейдж тестов
        content = re.sub(
            r'!\[Tests\]\([^)]*tests-[0-9]+%20✅[^)]*\)',
            f'![Tests](https://img.shields.io/badge/tests-{test_count}%20✅-brightgreen)',
            content
        )

        # Обновить бейдж покрытия
        content = re.sub(
            r'!\[Coverage\]\([^)]*coverage-[0-9]+%25[^)]*\)',
            f'![Coverage](https://img.shields.io/badge/coverage-{coverage}%25-orange)',
            content
        )

        # Обновить статистику в секции тестирования
        content = re.sub(
            r'\*\*Всего тестов:\*\* [0-9]+ ✅',
            f'**Всего тестов:** {test_count} ✅',
            content
        )

        content = re.sub(
            r'\*\*Покрытие кода:\*\* [0-9]+%',
            f'**Покрытие кода:** {coverage}%',
            content
        )

        # Обновить в конце файла
        content = re.sub(
            r'\*\*Тесты:\*\* [0-9]+ ✅ \| Покрытие: [0-9]+%',
            f'**Тесты:** {test_count} ✅ | Покрытие: {coverage}%',
            content
        )

        with open(self.readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def add_changelog_entry(self, version: str, changes: Dict[str, List[str]],
                          author: str = "Sonya AI Assistant") -> None:
        """Добавить новую запись в changelog."""
        date = datetime.now().strftime("%Y-%m-%d")
        emoji_map = {
            'added': '🎯',
            'changed': '🔧',
            'fixed': '🐛',
            'removed': '❌',
            'security': '🚨'
        }

        # Создать новую запись
        entry_lines = [
            f"## [{version}] - {date} - {author}",
            ""
        ]

        for change_type, change_list in changes.items():
            if change_list:
                emoji = emoji_map.get(change_type, '•')
                entry_lines.append(f"### {emoji} {change_type.title()}")
                for change in change_list:
                    entry_lines.append(f"- {change}")
                entry_lines.append("")

        entry_lines.append("")

        # Прочитать существующий changelog
        if self.changelog_path.exists():
            with open(self.changelog_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Найти место после заголовка
            lines = content.split('\n')
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.startswith('## [') and i > 0:
                    insert_pos = i
                    break

            # Вставить новую запись
            new_content = '\n'.join(lines[:insert_pos]) + '\n' + '\n'.join(entry_lines) + '\n'.join(lines[insert_pos:])
        else:
            # Создать новый changelog
            new_content = "# 📋 Changelog\n\nВсе важные изменения в проекте SONYA - Gaming Applications Manager.\n\n" + '\n'.join(entry_lines)

        with open(self.changelog_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    def create_release(self, bump_type: str = 'patch',
                       changes: Dict[str, List[str]] = None,
                       description: str = "",
                       author: str = "Sonya AI Assistant") -> str:
        """
        Создать новый релиз.

        Args:
            bump_type: Тип увеличения версии ('major', 'minor', 'patch')
            changes: Словарь изменений по типам
            description: Описание релиза
            author: Автор изменений

        Returns:
            Новая версия
        """
        if changes is None:
            changes = {}

        # Получить новую версию
        new_version = self.bump_version(bump_type)

        # Добавить запись в changelog
        self.add_changelog_entry(new_version, changes, author)

        # Обновить README
        self.update_readme_version(new_version, description)

        print(f"✅ Создан релиз {new_version}")
        print(f"📝 Обновлен CHANGELOG.md")
        print(f"📖 Обновлен README.md")

        return new_version

def main():
    """Основная функция для командной строки."""
    import argparse

    parser = argparse.ArgumentParser(description="Version Manager для SONYA")
    parser.add_argument('command', choices=['bump', 'stats', 'current'], help='Команда')
    parser.add_argument('--type', choices=['major', 'minor', 'patch'], default='patch',
                       help='Тип увеличения версии')
    parser.add_argument('--description', default="", help='Описание релиза')
    parser.add_argument('--test-count', type=int, help='Количество тестов')
    parser.add_argument('--coverage', type=int, help='Процент покрытия')

    args = parser.parse_args()

    vm = VersionManager()

    if args.command == 'current':
        print(f"Текущая версия: {vm.get_current_version()}")

    elif args.command == 'bump':
        new_version = vm.bump_version(args.type)
        print(f"Новая версия будет: {new_version}")

    elif args.command == 'stats':
        if args.test_count is not None and args.coverage is not None:
            vm.update_readme_stats(args.test_count, args.coverage)
            print(f"✅ Обновлена статистика: {args.test_count} тестов, {args.coverage}% покрытия")
        else:
            print("Ошибка: укажите --test-count и --coverage")

if __name__ == "__main__":
    main()
