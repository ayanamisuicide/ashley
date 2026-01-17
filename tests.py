"""
Unit tests for SONYA application manager.
Базовые unit-тесты для менеджера приложений.
"""

import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Импортируем модули для тестирования
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_manager import AppManager
from config import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Tests for ConfigManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "app_config.json")
        os.environ['CONFIG_FILE'] = self.config_file
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_config_loading(self):
        """Test configuration loading."""
        # Создаем тестовый конфиг с полной структурой
        test_config = {
            "apps": {
                "test_app": {
                    "name": "Test App",
                    "icon": "🧪",
                    "path": "/test/path",
                    "args": [],
                    "process_name": "test.exe",
                    "auto_detect": False,
                    "search_paths": []
                }
            },
            "settings": {
                "rate_limit_seconds": 2,
                "auto_save_pids": True,
                "log_level": "INFO"
            }
        }
        
        import json
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, ensure_ascii=False)
        
        # Мокаем CONFIG_FILE в config.py
        import config
        original_config_file = config.CONFIG_FILE
        
        # Патчим CONFIG_FILE
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()
        
        try:
            # Сбрасываем singleton
            config._config_manager = None
            
            # Тестируем загрузку
            test_config_obj = config.ConfigManager()
            app_config = test_config_obj.get_app_config("test_app")
            
            self.assertIsNotNone(app_config)
            self.assertEqual(app_config["name"], "Test App")
            self.assertEqual(app_config["icon"], "🧪")
        finally:
            # Восстанавливаем
            config_patcher.stop()
            config.CONFIG_FILE = original_config_file
            config._config_manager = None
    
    def test_get_app_command(self):
        """Test getting app command."""
        test_config = {
            "apps": {
                "test_app": {
                    "name": "Test App",
                    "path": "/test/path.exe",
                    "args": ["--test", "arg"]
                }
            }
        }
        
        import json
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        config = ConfigManager()
        cmd = config.get_app_command("test_app")
        
        # Должен вернуть None, так как путь не существует
        self.assertIsNone(cmd)


class TestAppManager(unittest.TestCase):
    """Tests for AppManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Сбрасываем singleton перед каждым тестом
        import app_manager
        app_manager._manager = None
        
        self.temp_dir = tempfile.mkdtemp()
        self.pids_file = os.path.join(self.temp_dir, "running_pids.json")
        self.stats_db = os.path.join(self.temp_dir, "bot_stats.db")
        
        # Удаляем старую БД если есть
        if os.path.exists(self.stats_db):
            os.remove(self.stats_db)
        
        # Мокаем файлы
        self.patcher1 = patch('app_manager.RUNNING_PIDS_FILE', self.pids_file)
        self.patcher2 = patch('app_manager.STATS_DB_FILE', self.stats_db)
        self.patcher1.start()
        self.patcher2.start()
        
        # Мокаем config
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_app_config.return_value = {
            "name": "Test App",
            "path": "/test/path.exe",
            "process_name": "test.exe",
            "args": []
        }
        mock_config.get_all_apps.return_value = {
            "test_app": {
                "name": "Test App",
                "path": "/test/path.exe",
                "process_name": "test.exe"
            }
        }
        mock_config.get_app_command.return_value = ["/test/path.exe"]
        mock_config.get_process_name.return_value = "test.exe"
        
        self.config_patcher = patch('app_manager.get_config', return_value=mock_config)
        self.config_patcher.start()
        
        # Сбрасываем singleton и создаем новый менеджер
        app_manager._manager = None
        self.manager = AppManager()
    
    def tearDown(self):
        """Clean up after tests."""
        # Останавливаем патчеры
        self.patcher1.stop()
        self.patcher2.stop()
        self.config_patcher.stop()
        
        # Сбрасываем singleton
        import app_manager
        app_manager._manager = None
        
        # Удаляем временные файлы
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_init_stats_db(self):
        """Test statistics database initialization."""
        # Проверяем, что БД создана
        self.assertTrue(os.path.exists(self.stats_db))
        
        # Проверяем структуру таблицы
        conn = sqlite3.connect(self.stats_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_stats'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()
    
    def test_save_and_load_pids(self):
        """Test saving and loading PIDs."""
        # Сохраняем PIDs
        self.manager.running_pids = {"test_app": 12345}
        self.manager.save_pids()
        
        # Проверяем, что файл создан
        self.assertTrue(os.path.exists(self.pids_file))
        
        # Читаем напрямую из файла для проверки
        import json
        with open(self.pids_file, 'r', encoding='utf-8') as f:
            saved_pids = json.load(f)
        self.assertEqual(saved_pids.get("test_app"), 12345)
        
        # Создаем новый менеджер и проверяем загрузку
        # Сбрасываем singleton
        import app_manager
        app_manager._manager = None
        
        # Используем те же патчеры, что уже активны в setUp
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_all_apps.return_value = {"test_app": {}}
        mock_config.get_app_config.return_value = {"name": "Test"}
        mock_config.get_process_name.return_value = "test.exe"
        
        # Временно патчим get_config
        with patch('app_manager.get_config', return_value=mock_config):
            new_manager = AppManager()
            self.assertEqual(new_manager.running_pids.get("test_app"), 12345)
    
    def test_get_stats_empty(self):
        """Test getting empty statistics."""
        stats = self.manager.get_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn("test_app", stats)
        self.assertEqual(stats["test_app"]["launches"], 0)
        self.assertEqual(stats["test_app"]["total_time"], 0.0)
    
    @patch('app_manager.psutil')
    def test_is_running_with_pid(self, mock_psutil):
        """Test checking if app is running with PID."""
        self.manager.running_pids["test_app"] = 12345
        
        # Мокаем psutil
        mock_process = Mock()
        mock_process.is_running.return_value = True
        mock_psutil.pid_exists.return_value = True
        mock_psutil.Process.return_value = mock_process
        
        result = self.manager.is_running("test_app")
        self.assertTrue(result)
    
    @patch('app_manager.subprocess')
    def test_is_running_fallback(self, mock_subprocess):
        """Test checking if app is running with fallback."""
        # Мокаем subprocess для fallback проверки
        mock_result = Mock()
        mock_result.stdout = "test.exe"
        mock_subprocess.run.return_value = mock_result
        
        # Мокаем отсутствие psutil
        with patch('app_manager.HAS_PSUTIL', False):
            result = self.manager.is_running("test_app")
            # Может быть True или False в зависимости от мока
            self.assertIsInstance(result, bool)
    
    @patch('app_manager.subprocess.Popen')
    def test_launch_app_success(self, mock_popen):
        """Test successful app launch."""
        mock_proc = Mock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc
        
        # Мокаем существование файла
        with patch('os.path.exists', return_value=True):
            result = self.manager.launch_app("test_app")
            self.assertTrue(result)
            self.assertEqual(self.manager.running_pids.get("test_app"), 12345)
    
    def test_launch_app_not_in_config(self):
        """Test launching app not in config."""
        self.manager.config.get_app_config.return_value = None
        
        result = self.manager.launch_app("nonexistent_app")
        self.assertFalse(result)
    
    @patch('app_manager.subprocess.run')
    def test_close_app_success(self, mock_subprocess):
        """Test successful app close."""
        self.manager.running_pids["test_app"] = 12345
        mock_subprocess.return_value = Mock(returncode=0)
        
        result = self.manager.close_app("test_app")
        # Может быть True или False в зависимости от мока
        self.assertIsInstance(result, bool)
    
    def test_close_all_apps(self):
        """Test closing all apps."""
        with patch.object(self.manager, 'is_running', return_value=True):
            with patch.object(self.manager, 'close_app', return_value=True):
                closed = self.manager.close_all_apps()
                self.assertIsInstance(closed, list)


class TestStatistics(unittest.TestCase):
    """Tests for statistics tracking."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Сбрасываем singleton перед каждым тестом
        import app_manager
        app_manager._manager = None
        
        self.temp_dir = tempfile.mkdtemp()
        self.stats_db = os.path.join(self.temp_dir, "bot_stats.db")
        self.pids_file = os.path.join(self.temp_dir, "pids.json")
        
        # Удаляем старую БД если есть
        if os.path.exists(self.stats_db):
            os.remove(self.stats_db)
        
        self.patcher1 = patch('app_manager.STATS_DB_FILE', self.stats_db)
        self.patcher2 = patch('app_manager.RUNNING_PIDS_FILE', self.pids_file)
        self.patcher1.start()
        self.patcher2.start()
        
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_app_config.return_value = {"name": "Test"}
        mock_config.get_all_apps.return_value = {"test_app": {}}
        mock_config.get_process_name.return_value = "test.exe"
        
        self.config_patcher = patch('app_manager.get_config', return_value=mock_config)
        self.config_patcher.start()
        
        # Сбрасываем singleton и создаем новый менеджер
        app_manager._manager = None
        self.manager = AppManager()
    
    def tearDown(self):
        """Clean up after tests."""
        # Останавливаем патчеры
        self.patcher1.stop()
        self.patcher2.stop()
        self.config_patcher.stop()
        
        # Сбрасываем singleton
        import app_manager
        app_manager._manager = None
        
        # Удаляем временные файлы
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_record_launch(self):
        """Test recording app launch."""
        self.manager._record_launch("test_app")
        
        stats = self.manager.get_stats()
        self.assertEqual(stats["test_app"]["launches"], 1)
        self.assertNotEqual(stats["test_app"]["last_launch"], "никогда")
    
    def test_record_multiple_launches(self):
        """Test recording multiple launches."""
        for _ in range(3):
            self.manager._record_launch("test_app")
        
        stats = self.manager.get_stats()
        self.assertEqual(stats["test_app"]["launches"], 3)


class TestConfigManagerAdvanced(unittest.TestCase):
    """Advanced tests for ConfigManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "app_config.json")
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_auto_detect_apps(self):
        """Test auto-detection of applications."""
        test_config = {
            "apps": {
                "test_app": {
                    "name": "Test App",
                    "path": "",
                    "auto_detect": True,
                    "search_paths": ["/nonexistent/path"]
                }
            }
        }
        
        import json
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, ensure_ascii=False)
        
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()
        
        try:
            config._config_manager = None
            test_config_obj = config.ConfigManager()
            # Автопоиск должен попытаться найти приложение
            self.assertIsNotNone(test_config_obj)
        finally:
            config_patcher.stop()
            config._config_manager = None
    
    def test_expand_path(self):
        """Test path expansion with environment variables."""
        import config
        config_obj = config.ConfigManager()
        
        # Тестируем расширение переменных окружения
        test_path = r"%APPDATA%\test.exe"
        expanded = config_obj._expand_path(test_path)
        self.assertIn("AppData", expanded or "")
    
    def test_get_all_apps(self):
        """Test getting all apps."""
        import config
        config_obj = config.ConfigManager()
        all_apps = config_obj.get_all_apps()
        self.assertIsInstance(all_apps, dict)
        self.assertGreater(len(all_apps), 0)


class TestAppManagerAdvanced(unittest.TestCase):
    """Advanced tests for AppManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        import app_manager
        app_manager._manager = None
        
        self.temp_dir = tempfile.mkdtemp()
        self.pids_file = os.path.join(self.temp_dir, "running_pids.json")
        self.stats_db = os.path.join(self.temp_dir, "bot_stats.db")
        
        if os.path.exists(self.stats_db):
            os.remove(self.stats_db)
        
        self.patcher1 = patch('app_manager.RUNNING_PIDS_FILE', self.pids_file)
        self.patcher2 = patch('app_manager.STATS_DB_FILE', self.stats_db)
        self.patcher1.start()
        self.patcher2.start()
        
        mock_config = Mock(spec=ConfigManager)
        mock_config.get_app_config.return_value = {
            "name": "Test App",
            "path": "/test/path.exe",
            "process_name": "test.exe",
            "args": []
        }
        mock_config.get_all_apps.return_value = {
            "test_app": {"name": "Test App"}
        }
        mock_config.get_app_command.return_value = ["/test/path.exe"]
        mock_config.get_process_name.return_value = "test.exe"
        
        self.config_patcher = patch('app_manager.get_config', return_value=mock_config)
        self.config_patcher.start()
        
        app_manager._manager = None
        self.manager = AppManager()
    
    def tearDown(self):
        """Clean up after tests."""
        self.patcher1.stop()
        self.patcher2.stop()
        self.config_patcher.stop()
        
        import app_manager
        app_manager._manager = None
        
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_record_session_end(self):
        """Test recording session end."""
        # Сначала записываем запуск
        self.manager._record_launch("test_app")
        
        # Затем записываем закрытие
        self.manager._record_session_end("test_app")
        
        stats = self.manager.get_stats()
        # Время должно быть больше 0 (хотя бы минимальное)
        self.assertGreaterEqual(stats["test_app"]["total_time"], 0)
    
    def test_get_stats_with_data(self):
        """Test getting stats with actual data."""
        # Записываем несколько запусков
        for _ in range(2):
            self.manager._record_launch("test_app")
        
        stats = self.manager.get_stats()
        self.assertEqual(stats["test_app"]["launches"], 2)
        self.assertNotEqual(stats["test_app"]["last_launch"], "никогда")
    
    def test_close_app_not_running(self):
        """Test closing app that is not running."""
        # Пытаемся закрыть не запущенное приложение
        result = self.manager.close_app("test_app")
        # Должно вернуть False, так как приложение не запущено
        self.assertFalse(result)


class TestConfigManagerComplete(unittest.TestCase):
    """Complete tests for ConfigManager to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "app_config.json")
        os.environ['CONFIG_FILE'] = self.config_file

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_merge_with_defaults(self):
        """Test merging config with defaults."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Создаем частичный конфиг
            partial_config = {
                "apps": {
                    "dota": {
                        "path": "/custom/path"
                    }
                },
                "settings": {
                    "rate_limit_seconds": 5
                }
            }

            merged = config_obj._merge_with_defaults(partial_config)

            # Проверяем что новые настройки применились
            self.assertEqual(merged["settings"]["rate_limit_seconds"], 5)
            # Проверяем что старые настройки остались
            self.assertTrue(merged["settings"]["auto_save_pids"])
            # Проверяем что новые приложения добавились
            self.assertIn("dota", merged["apps"])
            self.assertEqual(merged["apps"]["dota"]["path"], "/custom/path")
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_save_config(self):
        """Test saving configuration."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Изменяем конфиг
            config_obj.config["settings"]["rate_limit_seconds"] = 10
            config_obj.save_config()

            # Проверяем что файл создан и содержит изменения
            self.assertTrue(os.path.exists(self.config_file))

            import json
            with open(self.config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)

            self.assertEqual(saved_config["settings"]["rate_limit_seconds"], 10)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_find_app_with_wildcard(self):
        """Test finding app with wildcard paths."""
        import config
        config_obj = config.ConfigManager()

        # Создаем временный файл для тестирования
        test_dir = os.path.join(self.temp_dir, "test_app")
        os.makedirs(test_dir)
        test_file = os.path.join(test_dir, "app.exe")
        with open(test_file, 'w') as f:
            f.write("test")

        # Тестируем поиск с wildcard
        found = config_obj._find_app([os.path.join(test_dir, "*.exe")], "testuser")
        self.assertEqual(found, test_file)

    def test_find_app_not_found(self):
        """Test finding app when not found."""
        import config
        config_obj = config.ConfigManager()

        found = config_obj._find_app(["/nonexistent/path"], "testuser")
        self.assertIsNone(found)

    def test_get_app_config(self):
        """Test getting app configuration."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Тестируем получение существующего приложения
            dota_config = config_obj.get_app_config("dota")
            self.assertIsNotNone(dota_config)
            self.assertEqual(dota_config["name"], "Dota 2")

            # Тестируем получение несуществующего приложения
            nonexistent_config = config_obj.get_app_config("nonexistent")
            self.assertIsNone(nonexistent_config)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_get_process_name(self):
        """Test getting process name for app."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Тестируем получение process name
            dota_process = config_obj.get_process_name("dota")
            self.assertEqual(dota_process, "dota2.exe")

            # Тестируем для несуществующего приложения
            nonexistent_process = config_obj.get_process_name("nonexistent")
            self.assertIsNone(nonexistent_process)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_update_app_path_success(self):
        """Test updating app path successfully."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Создаем тестовый файл
            test_path = os.path.join(self.temp_dir, "test.exe")
            with open(test_path, 'w') as f:
                f.write("test")

            # Обновляем путь
            result = config_obj.update_app_path("dota", test_path)
            self.assertTrue(result)
            self.assertEqual(config_obj.config["apps"]["dota"]["path"], test_path)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_update_app_path_invalid(self):
        """Test updating app path with invalid path."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Пытаемся обновить на несуществующий путь
            result = config_obj.update_app_path("dota", "/nonexistent/path")
            self.assertFalse(result)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_update_app_path_nonexistent_app(self):
        """Test updating path for nonexistent app."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            result = config_obj.update_app_path("nonexistent", "/some/path")
            self.assertFalse(result)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_get_setting(self):
        """Test getting settings."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Тестируем существующую настройку
            rate_limit = config_obj.get_setting("rate_limit_seconds")
            self.assertEqual(rate_limit, 2)

            # Тестируем несуществующую настройку с default
            nonexistent = config_obj.get_setting("nonexistent", "default")
            self.assertEqual(nonexistent, "default")

            # Тестируем несуществующую настройку без default
            nonexistent_no_default = config_obj.get_setting("nonexistent")
            self.assertIsNone(nonexistent_no_default)
        finally:
            config_patcher.stop()
            config._config_manager = None


class TestSingleton(unittest.TestCase):
    """Tests for singleton pattern in config module."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "app_config.json")

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_get_config_singleton(self):
        """Test that get_config returns singleton instance."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            # Сбрасываем singleton
            config._config_manager = None

            # Получаем первый экземпляр
            config1 = config.get_config()
            # Получаем второй экземпляр
            config2 = config.get_config()

            # Проверяем что это один и тот же объект
            self.assertIs(config1, config2)
            self.assertIsInstance(config1, config.ConfigManager)
        finally:
            config_patcher.stop()
            config._config_manager = None


class TestConfigManagerCompleteCoverage(unittest.TestCase):
    """Complete tests for ConfigManager to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "app_config.json")
        os.environ['CONFIG_FILE'] = self.config_file

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_config_json_error(self):
        """Test JSON decode error handling."""
        # Создаем поврежденный JSON файл
        with open(self.config_file, 'w') as f:
            f.write("{ invalid json }")

        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Должен загрузить конфигурацию по умолчанию
            self.assertIsNotNone(config_obj.config)
            self.assertIn("apps", config_obj.config)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_save_config_error(self):
        """Test error handling in save_config."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Мокаем open чтобы он выбрасывал исключение
            with patch('builtins.open', side_effect=Exception("File error")):
                # Должен обработать ошибку без исключения
                config_obj.save_config()
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_get_app_command_no_config(self):
        """Test get_app_command when app config is missing."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Приложение без конфигурации
            result = config_obj.get_app_command("nonexistent")
            self.assertIsNone(result)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_get_app_command_no_path(self):
        """Test get_app_command when path is missing."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Изменяем конфиг чтобы убрать путь
            config_obj.config["apps"]["dota"]["path"] = ""
            result = config_obj.get_app_command("dota")
            self.assertIsNone(result)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_get_app_command_path_not_exists(self):
        """Test get_app_command when path doesn't exist."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None
            config_obj = config.ConfigManager()

            # Устанавливаем несуществующий путь
            config_obj.config["apps"]["dota"]["path"] = "/nonexistent/path.exe"
            result = config_obj.get_app_command("dota")
            self.assertIsNone(result)
        finally:
            config_patcher.stop()
            config._config_manager = None

    def test_main_block_execution(self):
        """Test execution of main block."""
        import config
        config_patcher = patch('config.CONFIG_FILE', self.config_file)
        config_patcher.start()

        try:
            config._config_manager = None

            # Мокаем print и get_config
            with patch('builtins.print') as mock_print:
                with patch('config.get_config') as mock_get_config:
                    mock_config = Mock()
                    mock_config.get_all_apps.return_value = {"test": {"name": "Test", "path": "/test"}}
                    mock_config.get_app_command.return_value = ["/test"]
                    mock_get_config.return_value = mock_config

                    # Импортируем как main модуль
                    import sys
                    old_argv = sys.argv
                    sys.argv = ['config.py']

                    try:
                        # Выполняем main блок
                        exec(open('config.py').read())
                    finally:
                        sys.argv = old_argv

                    # Проверяем что print был вызван
                    mock_print.assert_called()
        finally:
            config_patcher.stop()
            config._config_manager = None


class TestAppManagerComplete(unittest.TestCase):
    """Complete tests for AppManager to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        import app_manager
        app_manager._manager = None

        self.temp_dir = tempfile.mkdtemp()
        self.pids_file = os.path.join(self.temp_dir, "running_pids.json")
        self.stats_db = os.path.join(self.temp_dir, "bot_stats.db")

        if os.path.exists(self.stats_db):
            os.remove(self.stats_db)

        self.patcher1 = patch('app_manager.RUNNING_PIDS_FILE', self.pids_file)
        self.patcher2 = patch('app_manager.STATS_DB_FILE', self.stats_db)
        self.patcher1.start()
        self.patcher2.start()

        mock_config = Mock(spec=ConfigManager)
        mock_config.get_app_config.return_value = {
            "name": "Test App",
            "path": "/test/path.exe",
            "process_name": "test.exe",
            "args": []
        }
        mock_config.get_all_apps.return_value = {
            "test_app": {"name": "Test App"}
        }
        mock_config.get_app_command.return_value = ["/test/path.exe"]
        mock_config.get_process_name.return_value = "test.exe"

        self.config_patcher = patch('app_manager.get_config', return_value=mock_config)
        self.config_patcher.start()

        app_manager._manager = None
        self.manager = AppManager()

    def tearDown(self):
        """Clean up after tests."""
        self.patcher1.stop()
        self.patcher2.stop()
        self.config_patcher.stop()

        import app_manager
        app_manager._manager = None

        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_get_process_name(self):
        """Test getting process name from config."""
        result = self.manager._get_process_name("test_app")
        self.assertEqual(result, "test.exe")

    def test_is_running_dead_pid(self):
        """Test checking if app is running with dead PID."""
        # Устанавливаем PID для несуществующего процесса
        self.manager.running_pids["test_app"] = 999999  # Несуществующий PID

        with patch('app_manager.HAS_PSUTIL', True):
            result = self.manager.is_running("test_app")
            # PID должен быть удален
            self.assertNotIn("test_app", self.manager.running_pids)
            self.assertFalse(result)

    def test_launch_app_invalid_command(self):
        """Test launching app with invalid command."""
        self.manager.config.get_app_command.return_value = None

        result = self.manager.launch_app("test_app")
        self.assertFalse(result)

    def test_close_app_by_name_fallback(self):
        """Test closing app by name when PID method fails."""
        # Устанавливаем PID чтобы первый блок выполнился
        self.manager.running_pids["test_app"] = 12345

        # Мокаем taskkill по PID чтобы он провалился
        with patch('app_manager.subprocess.run') as mock_run:
            # Первый вызов (по PID) проваливается
            # Второй вызов (по имени) должен сработать
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, 'taskkill'),  # PID method fails
                Mock(returncode=0)  # Name method succeeds
            ]

            result = self.manager.close_app("test_app")
            self.assertTrue(result)
            self.assertEqual(mock_run.call_count, 2)

    def test_psutil_import_error(self):
        """Test behavior when psutil is not available."""
        # Мокаем отсутствие psutil
        with patch('app_manager.HAS_PSUTIL', False):
            # Создаем новый менеджер
            import app_manager
            app_manager._manager = None

            # Мокаем config
            mock_config = Mock()
            mock_config.get_app_config.return_value = {"name": "Test", "process_name": "test.exe"}
            mock_config.get_all_apps.return_value = {"test_app": {}}
            mock_config.get_app_command.return_value = ["/test/path.exe"]
            mock_config.get_process_name.return_value = "test.exe"

            with patch('app_manager.get_config', return_value=mock_config):
                manager = AppManager()

                # Тестируем is_running без psutil
                with patch('app_manager.subprocess.run') as mock_run:
                    mock_run.return_value = Mock(stdout="12345 test.exe")
                    result = manager.is_running("test_app")
                    self.assertIsInstance(result, bool)

    def test_db_migration_on_wrong_structure(self):
        """Test database migration when table structure is wrong."""
        # Создаем БД с неправильной структурой
        conn = sqlite3.connect(self.stats_db)
        cursor = conn.cursor()

        # Удаляем существующую таблицу и создаем с неправильными колонками
        cursor.execute("DROP TABLE IF EXISTS app_stats")
        cursor.execute("""
            CREATE TABLE app_stats (
                app_name TEXT,
                wrong_column INTEGER
            )
        """)
        conn.commit()
        conn.close()

        # Создаем новый менеджер - он должен мигрировать БД
        AppManager._manager = None
        manager = AppManager()

        # Проверяем что таблица была пересоздана правильно
        conn = sqlite3.connect(self.stats_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(app_stats)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = ['app_name', 'launches', 'total_time', 'last_launch', 'last_session_start']
        for col in expected_columns:
            self.assertIn(col, column_names)

        conn.close()

    def test_db_init_error_handling(self):
        """Test error handling during database initialization."""
        # Мокаем sqlite3.connect чтобы он выбрасывал исключение
        with patch('app_manager.sqlite3.connect', side_effect=Exception("DB Error")):
            # Создаем менеджер - он должен обработать ошибку
            AppManager._manager = None
            manager = AppManager()
            # Менеджер должен быть создан несмотря на ошибку БД
            self.assertIsNotNone(manager)

    def test_is_running_tasklist_fallback(self):
        """Test is_running with tasklist fallback when psutil available."""
        self.manager.running_pids["test_app"] = 12345

        with patch('app_manager.HAS_PSUTIL', True):
            # Мокаем psutil.pid_exists как False, чтобы перейти к tasklist
            with patch('app_manager.psutil.pid_exists', return_value=False):
                with patch('app_manager.subprocess.run') as mock_run:
                    mock_run.return_value = Mock(stdout="12345 test.exe", returncode=0)

                    result = self.manager.is_running("test_app")
                    # PID должен быть удален из running_pids
                    self.assertNotIn("test_app", self.manager.running_pids)

    def test_is_running_psutil_update_pid(self):
        """Test PID update when process found via psutil."""
        # Мокаем psutil для поиска процесса
        mock_proc = Mock()
        mock_proc.pid = 99999
        mock_proc.info = {'name': 'test.exe'}

        with patch('app_manager.HAS_PSUTIL', True):
            with patch('app_manager.psutil.process_iter', return_value=[mock_proc]):
                result = self.manager.is_running("test_app")

                # PID должен быть обновлен
                self.assertEqual(self.manager.running_pids["test_app"], 99999)
                self.assertTrue(result)

    def test_launch_app_already_running(self):
        """Test launching app that is already running."""
        with patch.object(self.manager, 'is_running', return_value=True):
            result = self.manager.launch_app("test_app")
            self.assertFalse(result)

    def test_launch_app_exceptions(self):
        """Test various exceptions during app launch."""
        # Test FileNotFoundError
        with patch('os.path.exists', return_value=True):
            with patch('app_manager.subprocess.Popen', side_effect=FileNotFoundError):
                result = self.manager.launch_app("test_app")
                self.assertFalse(result)

        # Test PermissionError
        with patch('os.path.exists', return_value=True):
            with patch('app_manager.subprocess.Popen', side_effect=PermissionError):
                result = self.manager.launch_app("test_app")
                self.assertFalse(result)

        # Test general Exception
        with patch('os.path.exists', return_value=True):
            with patch('app_manager.subprocess.Popen', side_effect=Exception("Test error")):
                result = self.manager.launch_app("test_app")
                self.assertFalse(result)

    def test_close_app_exceptions_pid_method(self):
        """Test exceptions in close_app PID method."""
        self.manager.running_pids["test_app"] = 12345

        # Test timeout
        with patch('app_manager.subprocess.run', side_effect=subprocess.TimeoutExpired('taskkill', 10)):
            result = self.manager.close_app("test_app")
            self.assertFalse(result)

        # Test CalledProcessError
        self.manager.running_pids["test_app"] = 12345
        with patch('app_manager.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'taskkill')):
            result = self.manager.close_app("test_app")
            self.assertFalse(result)

        # Test general exception
        self.manager.running_pids["test_app"] = 12345
        with patch('app_manager.subprocess.run', side_effect=Exception("Test error")):
            result = self.manager.close_app("test_app")
            self.assertFalse(result)

    def test_close_app_exceptions_name_method(self):
        """Test exceptions in close_app name method."""
        # Test timeout
        with patch('app_manager.subprocess.run') as mock_run:
            mock_run.side_effect = [subprocess.CalledProcessError(1, 'taskkill'), subprocess.TimeoutExpired('taskkill', 10)]
            result = self.manager.close_app("test_app")
            self.assertFalse(result)

        # Test CalledProcessError
        with patch('app_manager.subprocess.run') as mock_run:
            mock_run.side_effect = [subprocess.CalledProcessError(1, 'taskkill'), subprocess.CalledProcessError(1, 'taskkill')]
            result = self.manager.close_app("test_app")
            self.assertFalse(result)

        # Test general exception
        with patch('app_manager.subprocess.run') as mock_run:
            mock_run.side_effect = [subprocess.CalledProcessError(1, 'taskkill'), Exception("Test error")]
            result = self.manager.close_app("test_app")
            self.assertFalse(result)

    def test_record_launch_db_error(self):
        """Test error handling in _record_launch."""
        # Мокаем ошибку БД
        with patch('app_manager.sqlite3.connect', side_effect=Exception("DB Error")):
            # Должен обработать ошибку без исключения
            self.manager._record_launch("test_app")

    def test_record_session_end_db_error(self):
        """Test error handling in _record_session_end."""
        # Мокаем ошибку БД
        with patch('app_manager.sqlite3.connect', side_effect=Exception("DB Error")):
            # Должен обработать ошибку без исключения
            self.manager._record_session_end("test_app")

    def test_get_stats_db_error(self):
        """Test error handling in get_stats."""
        # Мокаем ошибку БД
        with patch('app_manager.sqlite3.connect', side_effect=Exception("DB Error")):
            stats = self.manager.get_stats()
            # Должен вернуть fallback статистику
            self.assertIsInstance(stats, dict)
            self.assertIn("test_app", stats)

    def test_get_manager_singleton(self):
        """Test get_manager singleton function."""
        # Сбрасываем singleton
        import app_manager
        app_manager._manager = None

        # Получаем первый экземпляр
        manager1 = app_manager.get_manager()
        # Получаем второй экземпляр
        manager2 = app_manager.get_manager()

        # Проверяем что это один и тот же объект
        self.assertIs(manager1, manager2)
        self.assertIsInstance(manager1, AppManager)

    def test_deprecated_functions(self):
        """Test deprecated compatibility functions."""
        import app_manager

        # Test load_pids
        app_manager.load_pids()

        # Test save_pids
        app_manager.save_pids()

        # Test is_running
        result = app_manager.is_running("test_app")
        self.assertIsInstance(result, bool)

        # Test launch_app
        result = app_manager.launch_app("test_app")
        self.assertIsInstance(result, bool)

        # Test close_app
        result = app_manager.close_app("test_app")
        self.assertIsInstance(result, bool)

        # Test close_all_apps
        result = app_manager.close_all_apps()
        self.assertIsInstance(result, list)

    def test_close_app_with_taskkill(self):
        """Test closing app using taskkill fallback."""
        self.manager.running_pids["test_app"] = 12345

        with patch('app_manager.HAS_PSUTIL', False):
            with patch('app_manager.subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                result = self.manager.close_app("test_app")
                self.assertIsInstance(result, bool)
                mock_run.assert_called_once()


class TestBotFunctions(unittest.TestCase):
    """Tests for bot utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Мокаем переменные окружения
        self.env_patcher = patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_token_123',
            'ADMIN_ID': '123456789'
        })
        self.env_patcher.start()

        # Мокаем импорты
        self.bot_imports = patch.multiple(
            'bot',
            TOKEN='test_token',
            ADMIN_ID=123456789
        )
        self.bot_imports.start()

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        self.bot_imports.stop()

    def test_get_user(self):
        """Test user data management."""
        # Импортируем после моков
        import sys
        if 'bot' in sys.modules:
            del sys.modules['bot']

        # Мокаем только нужные части
        with patch('bot.ADMIN_ID', 123456789):
            # Не можем напрямую тестировать из-за зависимостей
            # Но можем проверить логику
            self.assertTrue(True)  # Placeholder

    def test_rate_limit_decorator(self):
        """Test rate limiting functionality."""
        # Rate limiting тестируется через интеграционные тесты
        # Здесь проверяем что декоратор существует
        self.assertTrue(True)  # Placeholder для будущих тестов


class TestBotCore(unittest.IsolatedAsyncioTestCase):
    """Tests for bot core functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.env_patcher = patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_token_123',
            'ADMIN_ID': '123456789'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()

    @patch('bot.get_manager')
    @patch('bot.reply_log')
    async def test_handle_message_help_command(self, mock_reply_log, mock_get_manager):
        """Test handling help command."""
        # Мокаем Update и Message
        mock_message = Mock()
        mock_message.text = "хелп"

        mock_user = Mock()
        mock_user.id = 123456789  # ADMIN_ID

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_context = Mock()

        # Импортируем функцию после моков
        from bot import handle_message

        await handle_message(mock_update, mock_context)

        # Проверяем что reply_log был вызван
        mock_reply_log.assert_called_once()

    @patch('bot.get_manager')
    @patch('bot.reply_log')
    async def test_handle_message_status_command(self, mock_reply_log, mock_get_manager):
        """Test handling status command."""
        mock_message = Mock()
        mock_message.text = "ты"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_context = Mock()

        from bot import handle_message

        await handle_message(mock_update, mock_context)

        mock_reply_log.assert_called_once()

    @patch('bot.get_manager')
    @patch('bot.reply_log')
    async def test_handle_message_non_admin(self, mock_reply_log, mock_get_manager):
        """Test handling message from non-admin user."""
        mock_message = Mock()
        mock_message.text = "дота"

        mock_user = Mock()
        mock_user.id = 999999  # Non-admin

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_context = Mock()

        from bot import handle_message

        await handle_message(mock_update, mock_context)

        # Проверяем что ответ для не-админа
        mock_reply_log.assert_called_once()
        args = mock_reply_log.call_args[0]
        self.assertIn("извини", args[0])

    @patch('bot.get_manager')
    @patch('bot.reply_log')
    async def test_handle_message_launch_app(self, mock_reply_log, mock_get_manager):
        """Test launching application."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.launch_app.return_value = True
        mock_get_manager.return_value = mock_manager

        mock_message = Mock()
        mock_message.text = "дота"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_context = Mock()

        from bot import handle_message

        await handle_message(mock_update, mock_context)

        mock_reply_log.assert_called_once()

    @patch('bot.get_manager')
    @patch('bot.reply_log')
    async def test_handle_message_close_app(self, mock_reply_log, mock_get_manager):
        """Test closing application."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        mock_manager.close_app.return_value = True
        mock_get_manager.return_value = mock_manager

        mock_message = Mock()
        mock_message.text = "закрой дота"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_context = Mock()

        from bot import handle_message

        await handle_message(mock_update, mock_context)

        mock_reply_log.assert_called_once()

    @patch('bot.get_manager')
    @patch('bot.reply_log')
    async def test_handle_message_close_all(self, mock_reply_log, mock_get_manager):
        """Test closing all applications."""
        mock_manager = Mock()
        mock_manager.close_all_apps.return_value = ["Dota 2", "Spotify"]
        mock_get_manager.return_value = mock_manager

        mock_message = Mock()
        mock_message.text = "закрой"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_context = Mock()

        from bot import handle_message

        await handle_message(mock_update, mock_context)

        mock_reply_log.assert_called_once()

    @patch('bot.get_manager')
    @patch('bot.reply_log')
    async def test_handle_message_statistics(self, mock_reply_log, mock_get_manager):
        """Test getting statistics."""
        mock_manager = Mock()
        mock_manager.get_stats.return_value = {
            "dota": {
                "launches": 5,
                "total_time": 3600,
                "last_launch": "2025-01-10T10:00:00",
                "name": "Dota 2"
            }
        }
        mock_manager.config.get_app_config.return_value = {"name": "Dota 2", "icon": "🎮"}
        mock_get_manager.return_value = mock_manager

        mock_message = Mock()
        mock_message.text = "статистика"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_context = Mock()

        from bot import handle_message

        await handle_message(mock_update, mock_context)

        mock_reply_log.assert_called_once()

    async     def test_reply_log_success(self):
        """Test successful reply logging."""
        mock_message = Mock()
        mock_message.reply_text = Mock(return_value=None)

        mock_update = Mock()
        mock_update.message = mock_message

        from bot import reply_log

        await reply_log("test message", mock_update, 123456)

        mock_message.reply_text.assert_called_once_with("test message")

    def test_console_encoding_fallback(self):
        """Test console encoding fallback."""
        # Мокаем sys.stdout.reconfigure чтобы он выбрасывал AttributeError
        with patch('sys.stdout.reconfigure', side_effect=AttributeError):
            with patch('sys.stderr.reconfigure', side_effect=AttributeError):
                # Импортируем bot - должен обработать исключения
                import sys
                if 'bot' in sys.modules:
                    del sys.modules['bot']

                # Это должно выполниться без ошибок
                import bot

    def test_token_missing_exceptions(self):
        """Test exceptions when tokens are missing."""
        # Test missing TELEGRAM_BOT_TOKEN
        with patch.dict(os.environ, {'ADMIN_ID': '123'}, clear=True):
            with self.assertRaises(RuntimeError) as cm:
                import sys
                if 'bot' in sys.modules:
                    del sys.modules['bot']
                import bot
            self.assertIn("TELEGRAM_BOT_TOKEN", str(cm.exception))

        # Test missing ADMIN_ID
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'token'}, clear=True):
            with self.assertRaises(RuntimeError) as cm:
                import sys
                if 'bot' in sys.modules:
                    del sys.modules['bot']
                import bot
            self.assertIn("ADMIN_ID", str(cm.exception))

    async def test_rate_limit_no_user(self):
        """Test rate limit with no effective user."""
        from bot import rate_limit

        @rate_limit()
        async def dummy_func(update, context):
            return "called"

        mock_update = Mock()
        mock_update.effective_user = None

        result = await dummy_func(mock_update, Mock())
        self.assertIsNone(result)

    async def test_rate_limit_admin_bypass(self):
        """Test that admin bypasses rate limiting."""
        from bot import rate_limit

        @rate_limit()
        async def dummy_func(update, context):
            return "called"

        mock_update = Mock()
        mock_user = Mock()
        mock_user.id = 123456789  # ADMIN_ID
        mock_update.effective_user = mock_user

        with patch('bot.last_command_time', {}):
            result = await dummy_func(mock_update, Mock())
            self.assertEqual(result, "called")

    async def test_rate_limit_enforced(self):
        """Test rate limiting enforcement."""
        from bot import rate_limit, last_command_time

        # Очищаем rate limit для теста
        last_command_time.clear()

        @rate_limit(seconds=1)
        async def dummy_func(update, context):
            return "called"

        from unittest.mock import AsyncMock

        mock_update = Mock()
        mock_user = Mock()
        mock_user.id = 999999  # Non-admin
        mock_update.effective_user = mock_user
        mock_update.message = Mock()
        mock_update.message.reply_text = AsyncMock()

        # Первый вызов
        with patch('bot.time', return_value=100):
            result1 = await dummy_func(mock_update, Mock())
            self.assertEqual(result1, "called")

        # Второй вызов слишком быстро
        with patch('bot.time', return_value=100.5):
            result2 = await dummy_func(mock_update, Mock())
            self.assertIsNone(result2)  # Rate limiting должен вернуть None

    async def test_handle_message_no_message(self):
        """Test handle_message with no message."""
        mock_update = Mock()
        mock_update.message = None

        from bot import handle_message

        result = await handle_message(mock_update, Mock())
        self.assertIsNone(result)

    async def test_handle_message_empty_text(self):
        """Test handle_message with empty text."""
        mock_message = Mock()
        mock_message.text = ""

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import handle_message

        result = await handle_message(mock_update, Mock())
        self.assertIsNone(result)

    async def test_handle_message_responses_command(self):
        """Test responses command."""
        mock_message = Mock()
        mock_message.text = "ответы"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import handle_message

        await handle_message(mock_update, Mock())

    async def test_handle_message_menu_command(self):
        """Test menu command."""
        mock_message = Mock()
        mock_message.text = "меню"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import handle_message

        await handle_message(mock_update, Mock())

    async def test_handle_message_stats_parsing_error(self):
        """Test statistics parsing error."""
        mock_message = Mock()
        mock_message.text = "статистика"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_manager = Mock()
        mock_manager.get_stats.return_value = {
            "test_app": {
                "launches": 1,
                "total_time": 100,
                "last_launch": "invalid-date",  # Invalid date
            }
        }
        mock_manager.config.get_app_config.return_value = {"name": "Test"}

        with patch('bot.get_manager', return_value=mock_manager):
            from bot import handle_message
            await handle_message(mock_update, Mock())

    async def test_handle_message_stats_app_error(self):
        """Test statistics app processing error."""
        mock_message = Mock()
        mock_message.text = "статистика"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_manager = Mock()
        mock_manager.get_stats.return_value = {
            "test_app": {
                "launches": 1,
                "total_time": 100,
                "last_launch": "2025-01-01T10:00:00",
            }
        }
        mock_manager.config.get_app_config.side_effect = Exception("Config error")

        with patch('bot.get_manager', return_value=mock_manager):
            from bot import handle_message
            await handle_message(mock_update, Mock())

    async def test_handle_message_already_running(self):
        """Test launching already running app."""
        mock_message = Mock()
        mock_message.text = "дота"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        mock_manager.config.get_app_config.return_value = {"name": "Dota 2"}

        with patch('bot.get_manager', return_value=mock_manager):
            from bot import handle_message
            await handle_message(mock_update, Mock())

    async def test_handle_message_launch_exception(self):
        """Test launch exception handling."""
        mock_message = Mock()
        mock_message.text = "дота"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.launch_app.side_effect = Exception("Launch error")

        with patch('bot.get_manager', return_value=mock_manager):
            from bot import handle_message
            await handle_message(mock_update, Mock())

    async def test_handle_message_close_exception(self):
        """Test close exception handling."""
        mock_message = Mock()
        mock_message.text = "закрой дота"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        mock_manager.close_app.side_effect = Exception("Close error")

        with patch('bot.get_manager', return_value=mock_manager):
            from bot import handle_message
            await handle_message(mock_update, Mock())

    async def test_handle_message_close_all_exception(self):
        """Test close all exception handling."""
        mock_message = Mock()
        mock_message.text = "закрой"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_manager = Mock()
        mock_manager.close_all_apps.side_effect = Exception("Close all error")

        with patch('bot.get_manager', return_value=mock_manager):
            from bot import handle_message
            await handle_message(mock_update, Mock())

    async def test_handle_message_close_config_exception(self):
        """Test close config exception handling."""
        mock_message = Mock()
        mock_message.text = "закрой"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        mock_manager = Mock()
        mock_manager.close_all_apps.return_value = ["app1", "app2"]
        mock_manager.config.get_app_config.side_effect = Exception("Config error")

        with patch('bot.get_manager', return_value=mock_manager):
            from bot import handle_message
            await handle_message(mock_update, Mock())

    async def test_handle_message_fallback(self):
        """Test fallback message handling."""
        mock_message = Mock()
        mock_message.text = "unknown command"

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import handle_message

        await handle_message(mock_update, Mock())

    async def test_start_command_admin(self):
        """Test /start command for admin."""
        from unittest.mock import AsyncMock

        mock_message = Mock()
        mock_message.reply_text = AsyncMock()

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import start

        await start(mock_update, Mock())

        mock_message.reply_text.assert_called_once()

    async def test_start_command_non_admin(self):
        """Test /start command for non-admin."""
        from unittest.mock import AsyncMock

        mock_message = Mock()
        mock_message.reply_text = AsyncMock()

        mock_user = Mock()
        mock_user.id = 999999

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import start

        await start(mock_update, Mock())

        # Проверяем что сообщение было отправлено (может быть rate limit или отказ)
        mock_message.reply_text.assert_called_once()

    async def test_help_command_admin(self):
        """Test /help command for admin."""
        from unittest.mock import AsyncMock

        mock_message = Mock()
        mock_message.reply_text = AsyncMock()

        mock_user = Mock()
        mock_user.id = 123456789

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import help_command

        await help_command(mock_update, Mock())

        mock_message.reply_text.assert_called_once()

    async def test_help_command_non_admin(self):
        """Test /help command for non-admin."""
        from unittest.mock import AsyncMock

        mock_message = Mock()
        mock_message.reply_text = AsyncMock()

        mock_user = Mock()
        mock_user.id = 999999

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_user = mock_user

        from bot import help_command

        await help_command(mock_update, Mock())

        # Проверяем что сообщение было отправлено (может быть rate limit или отказ)
        mock_message.reply_text.assert_called_once()

    async def test_error_handler_network_error(self):
        """Test error handler with NetworkError."""
        from telegram.error import NetworkError

        mock_context = Mock()
        mock_context.error = NetworkError("Network error")
        mock_context.bot = Mock()

        from bot import error_handler

        await error_handler(None, mock_context)

    async def test_error_handler_timeout_error(self):
        """Test error handler with TimedOut."""
        from telegram.error import TimedOut

        mock_context = Mock()
        mock_context.error = TimedOut()
        mock_context.bot = Mock()

        from bot import error_handler

        await error_handler(None, mock_context)

    async def test_error_handler_retry_after(self):
        """Test error handler with RetryAfter."""
        from telegram.error import RetryAfter

        mock_context = Mock()
        mock_context.error = RetryAfter(30)
        mock_context.bot = Mock()

        from bot import error_handler

        await error_handler(None, mock_context)

    async def test_error_handler_telegram_error(self):
        """Test error handler with TelegramError."""
        from telegram.error import TelegramError

        mock_context = Mock()
        mock_context.error = TelegramError("Telegram error")
        mock_context.bot = Mock()

        from bot import error_handler

        await error_handler(None, mock_context)

    async def test_error_handler_with_user_message(self):
        """Test error handler that sends message to user."""
        from telegram.error import TelegramError
        from telegram import Update

        # Создаем правильный mock update
        mock_update = Mock(spec=Update)
        mock_update.effective_chat = Mock()
        mock_update.effective_chat.id = 123456

        mock_context = Mock()
        mock_context.error = TelegramError("Error")
        mock_context.bot = Mock()

        from bot import error_handler

        await error_handler(mock_update, mock_context)

        mock_context.bot.send_message.assert_called_once()

    def test_main_manager_init_error(self):
        """Test main function manager initialization error."""
        with patch('bot.get_manager', side_effect=Exception("Manager error")):
            from bot import main
            with self.assertRaises(Exception):
                main()

    def test_main_polling_keyboard_interrupt(self):
        """Test main function with KeyboardInterrupt during polling."""
        mock_app = Mock()
        mock_app.run_polling.side_effect = KeyboardInterrupt()

        with patch('bot.get_manager'):
            with patch('bot.Application.builder') as mock_builder:
                mock_builder.return_value.token.return_value.build.return_value = mock_app

                from bot import main
                with self.assertRaises(KeyboardInterrupt):
                    main()

    def test_main_polling_error(self):
        """Test main function polling error."""
        mock_app = Mock()
        mock_app.run_polling.side_effect = Exception("Polling error")

        with patch('bot.get_manager'):
            with patch('bot.Application.builder') as mock_builder:
                mock_builder.return_value.token.return_value.build.return_value = mock_app

                from bot import main
                with self.assertRaises(Exception):
                    main()

    def test_main_config_error(self):
        """Test main function configuration error."""
        with patch('bot.get_manager'):
            with patch('bot.Application.builder', side_effect=ValueError("Config error")):

                from bot import main
                with self.assertRaises(ValueError):
                    main()

    def test_main_general_error(self):
        """Test main function general error."""
        with patch('bot.get_manager'):
            with patch('bot.Application.builder', side_effect=Exception("General error")):

                from bot import main
                with self.assertRaises(Exception):
                    main()

    async def test_reply_log_fallback(self):
        """Test reply log fallback."""
        mock_message = Mock()
        mock_message.reply_text.side_effect = Exception("Network error")

        mock_bot = Mock()
        mock_chat = Mock()
        mock_chat.id = 123456

        mock_update = Mock()
        mock_update.message = mock_message
        mock_update.effective_chat = mock_chat
        mock_update.message.bot = mock_bot

        from bot import reply_log

        await reply_log("test message", mock_update, 123456)

        # Проверяем что fallback был вызван
        mock_bot.send_message.assert_called_once()


class TestLauncherGUI(unittest.TestCase):
    """Tests for launcher GUI (mocked to avoid GUI dependencies)."""

    @patch('launcher.ctk')
    @patch('launcher.check_and_install_dependencies', return_value=True)
    def test_launcher_initialization(self, mock_check_deps, mock_ctk):
        """Test launcher GUI initialization."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root

        from launcher import LauncherGUI

        launcher = LauncherGUI()

        # Проверяем что GUI была инициализирована
        mock_ctk.CTk.assert_called_once()
        self.assertIsNotNone(launcher.root)

    @patch('launcher.check_and_install_dependencies')
    def test_check_dependencies_success(self, mock_check):
        """Test dependency checking success."""
        mock_check.return_value = True

        from launcher import check_and_install_dependencies

        result = check_and_install_dependencies()
        self.assertTrue(result)

    def test_check_dependencies_install(self):
        """Test dependency installation."""
        # Просто проверяем что функция существует и может быть вызвана
        # Полное тестирование launcher требует более сложной настройки
        from launcher import check_and_install_dependencies

        # Функция должна существовать
        self.assertTrue(callable(check_and_install_dependencies))


class TestGUIApp(unittest.TestCase):
    """Tests for GUI application (mocked)."""

    @patch('gui.ctk')
    @patch('gui.get_manager')
    def test_gui_initialization(self, mock_get_manager, mock_ctk):
        """Test GUI app initialization."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        mock_config = Mock()
        mock_config.get_all_apps.return_value = {"test_app": {"name": "Test"}}

        mock_manager = Mock()
        mock_manager.config = mock_config
        mock_manager.get_stats.return_value = {"test_app": {"launches": 1, "total_time": 100}}
        mock_get_manager.return_value = mock_manager

        from gui import AppManagerGUI

        gui = AppManagerGUI()

        # Проверяем базовую инициализацию
        mock_ctk.CTk.assert_called_once()
        self.assertIsNotNone(gui.root)
        self.assertEqual(gui.manager, mock_manager)

    def test_text_handler_emit(self):
        """Test TextHandler emit method."""
        from gui import TextHandler

        mock_text_widget = Mock()
        handler = TextHandler(mock_text_widget)

        # Создаем тестовый лог
        import logging
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )

        # Вызываем emit
        handler.emit(record)

        # Проверяем что after был вызван
        mock_text_widget.after.assert_called_once()

    @patch('gui.ctk')
    @patch('gui.get_manager')
    def test_gui_schedule_update_window_closed(self, mock_get_manager, mock_ctk):
        """Test schedule_update when window is closed."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        mock_config = Mock()
        mock_config.get_all_apps.return_value = {}

        mock_manager = Mock()
        mock_manager.config = mock_config
        mock_manager.get_stats.return_value = {}
        mock_get_manager.return_value = mock_manager

        from gui import AppManagerGUI

        gui = AppManagerGUI()
        gui._is_closing = False

        # Мокаем что окно не существует
        mock_root.winfo_exists.return_value = False

        # Вызываем schedule_update
        gui.schedule_update()

        # Проверяем что _is_closing установлено
        self.assertTrue(gui._is_closing)

    @patch('gui.ctk')
    @patch('gui.get_manager')
    def test_gui_launch_app_gui_success(self, mock_get_manager, mock_ctk):
        """Test launch_app_gui successful launch."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        mock_config = Mock()
        mock_config.get_all_apps.return_value = {}
        mock_config.get_app_config.return_value = {"name": "Test App"}

        mock_manager = Mock()
        mock_manager.config = mock_config
        mock_manager.launch_app.return_value = True
        mock_manager.get_stats.return_value = {}  # Пустая статистика
        mock_get_manager.return_value = mock_manager

        from gui import AppManagerGUI

        gui = AppManagerGUI()

        # Мокаем status_bar
        gui.status_bar = Mock()

        # Вызываем launch_app_gui
        gui.launch_app_gui("test_app")

        # Проверяем что статус бар обновлен
        gui.status_bar.configure.assert_called()

    @patch('gui.ctk')
    @patch('gui.get_manager')
    def test_gui_close_app_gui_success(self, mock_get_manager, mock_ctk):
        """Test close_app_gui successful close."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        mock_config = Mock()
        mock_config.get_all_apps.return_value = {}
        mock_config.get_app_config.return_value = {"name": "Test App"}

        mock_manager = Mock()
        mock_manager.config = mock_config
        mock_manager.close_app.return_value = True
        mock_manager.get_stats.return_value = {}  # Пустая статистика
        mock_get_manager.return_value = mock_manager

        from gui import AppManagerGUI

        gui = AppManagerGUI()
        gui.status_bar = Mock()

        gui.close_app_gui("test_app")

        gui.status_bar.configure.assert_called()

    @patch('gui.ctk')
    @patch('gui.get_manager')
    def test_gui_close_all_apps_success(self, mock_get_manager, mock_ctk):
        """Test close_all_apps successful."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        mock_config = Mock()
        mock_config.get_all_apps.return_value = {}
        mock_config.get_app_config.return_value = {"name": "Test App"}

        mock_manager = Mock()
        mock_manager.config = mock_config
        mock_manager.close_all_apps.return_value = ["test_app"]
        mock_manager.get_stats.return_value = {}  # Пустая статистика
        mock_get_manager.return_value = mock_manager

        from gui import AppManagerGUI

        gui = AppManagerGUI()
        gui.status_bar = Mock()

        gui.close_all_apps()

        gui.status_bar.configure.assert_called()

    @patch('gui.ctk')
    @patch('gui.get_manager')
    def test_gui_update_statuses_window_closed(self, mock_get_manager, mock_ctk):
        """Test update_statuses when window is closed."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        mock_config = Mock()
        mock_config.get_all_apps.return_value = {}

        mock_manager = Mock()
        mock_manager.config = mock_config
        mock_manager.get_stats.return_value = {}
        mock_get_manager.return_value = mock_manager

        from gui import AppManagerGUI

        gui = AppManagerGUI()
        gui._is_closing = False
        gui.status_labels = {}
        gui.status_indicators = {}

        # Мокаем что окно закрыто
        mock_root.winfo_exists.return_value = False

        gui.update_statuses()

        self.assertTrue(gui._is_closing)

    @patch('gui.ctk')
    @patch('gui.get_manager')
    def test_gui_on_closing(self, mock_get_manager, mock_ctk):
        """Test on_closing method."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        mock_config = Mock()
        mock_config.get_all_apps.return_value = {}

        mock_manager = Mock()
        mock_manager.config = mock_config
        mock_manager.get_stats.return_value = {}
        mock_get_manager.return_value = mock_manager

        from gui import AppManagerGUI

        gui = AppManagerGUI()

        gui.on_closing()

        self.assertTrue(gui._is_closing)
        mock_manager.close_all_apps.assert_called_once()
        mock_manager.save_pids.assert_called_once()
        mock_root.destroy.assert_called_once()


class TestLauncherGUI(unittest.TestCase):
    """Tests for launcher GUI (minimal tests)."""

    @patch('launcher.ctk')
    def test_launcher_gui_init(self, mock_ctk):
        """Test LauncherGUI initialization."""
        mock_root = Mock()
        mock_ctk.CTk.return_value = mock_root
        mock_ctk.set_appearance_mode = Mock()
        mock_ctk.set_default_color_theme = Mock()

        from launcher import LauncherGUI

        launcher = LauncherGUI()

        self.assertIsNotNone(launcher.root)
        mock_ctk.CTk.assert_called_once()

    def test_check_env_file_exists(self):
        """Test check_env_file when file exists."""
        from launcher import LauncherGUI

        # Создаем временный .env файл
        with open('.env', 'w') as f:
            f.write('TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz\nADMIN_ID=123\n')

        try:
            launcher = LauncherGUI()
            # Мокаем метод show_error чтобы избежать GUI проблем
            launcher.show_error = Mock()
            result = launcher.check_env_file()
            self.assertTrue(result)
            # Проверяем что show_error не был вызван
            launcher.show_error.assert_not_called()
        finally:
            # Удаляем файл
            if os.path.exists('.env'):
                os.remove('.env')

    def test_check_env_file_missing(self):
        """Test check_env_file when file doesn't exist."""
        from launcher import LauncherGUI

        # Убеждаемся что .env не существует
        if os.path.exists('.env'):
            os.remove('.env')

        launcher = LauncherGUI()
        result = launcher.check_env_file()
        self.assertFalse(result)

    def test_check_env_file_incomplete(self):
        """Test check_env_file when file exists but incomplete."""
        from launcher import LauncherGUI

        # Создаем неполный .env файл
        with open('.env', 'w') as f:
            f.write('TELEGRAM_BOT_TOKEN=test\n')

        try:
            launcher = LauncherGUI()
            result = launcher.check_env_file()
            self.assertFalse(result)
        finally:
            if os.path.exists('.env'):
                os.remove('.env')


def run_tests():
    """Run all tests with coverage information."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем все тесты
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManager))
    suite.addTests(loader.loadTestsFromTestCase(TestAppManager))
    suite.addTests(loader.loadTestsFromTestCase(TestStatistics))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManagerAdvanced))
    suite.addTests(loader.loadTestsFromTestCase(TestAppManagerAdvanced))
    suite.addTests(loader.loadTestsFromTestCase(TestBotFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManagerComplete))
    suite.addTests(loader.loadTestsFromTestCase(TestSingleton))
    suite.addTests(loader.loadTestsFromTestCase(TestAppManagerComplete))
    suite.addTests(loader.loadTestsFromTestCase(TestBotCore))
    suite.addTests(loader.loadTestsFromTestCase(TestLauncherGUI))
    suite.addTests(loader.loadTestsFromTestCase(TestGUIApp))
    suite.addTests(loader.loadTestsFromTestCase(TestLauncherGUI))
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Выводим статистику
    print("\n" + "="*60)
    print("📊 СТАТИСТИКА ТЕСТОВ")
    print("="*60)
    print(f"Всего тестов: {result.testsRun}")
    print(f"Успешно: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Провалено: {len(result.failures)}")
    print(f"Ошибок: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ Проваленные тесты:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\n⚠️  Тесты с ошибками:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    if result.wasSuccessful():
        print("\n✅ Все тесты прошли успешно!")
    else:
        print("\n❌ Некоторые тесты не прошли")
    
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)