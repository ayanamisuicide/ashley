"""
Application Manager with statistics tracking and process management.
Управление приложениями с отслеживанием статистики и процессов.
"""

import json
import logging
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import psutil  # type: ignore
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from config import get_config

logger = logging.getLogger("app_manager")
logger.setLevel(logging.INFO)

# Файлы для хранения данных
RUNNING_PIDS_FILE = "running_pids.json"
STATS_DB_FILE = "bot_stats.db"


class AppManager:
    """Manages application lifecycle, statistics, and process tracking."""
    
    def __init__(self):
        """Initialize AppManager with config and load saved data."""
        self.config = get_config()
        self.running_pids: Dict[str, int] = {}
        self._load_pids()
        self._init_stats_db()
        logger.info("AppManager инициализирован")
    
    def _load_pids(self) -> None:
        """Load running PIDs from file."""
        try:
            if Path(RUNNING_PIDS_FILE).exists():
                with open(RUNNING_PIDS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.running_pids = {k: int(v) for k, v in data.items()}
                    logger.info(f"Загружено {len(self.running_pids)} PIDs из файла")
        except json.JSONDecodeError as e:
            logger.error(f"Неверный формат JSON PID файла: {e}")
            self.running_pids = {}
        except Exception as e:
            logger.error(f"Ошибка загрузки PID: {e}")
            self.running_pids = {}
    
    def save_pids(self) -> None:
        """Save running PIDs to file."""
        try:
            with open(RUNNING_PIDS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.running_pids, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения PID: {e}")
    
    def _init_stats_db(self) -> None:
        """Initialize statistics database."""
        try:
            conn = sqlite3.connect(STATS_DB_FILE)
            cursor = conn.cursor()
            
            # Проверяем, существует ли таблица
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='app_stats'
            """)
            table_exists = cursor.fetchone()
            
            if table_exists:
                # Проверяем структуру таблицы
                cursor.execute("PRAGMA table_info(app_stats)")
                columns_info = cursor.fetchall()
                columns = {row[1]: row[2] for row in columns_info}
                
                # Если структура неверная, пересоздаем таблицу
                required_columns = ['app_name', 'launches', 'total_time', 'last_launch', 'last_session_start']
                missing_columns = [col for col in required_columns if col not in columns]
                
                if missing_columns:
                    logger.warning(f"Структура таблицы app_stats неверная (отсутствуют колонки: {missing_columns}), пересоздаем...")
                    # Сохраняем данные если есть
                    try:
                        cursor.execute("SELECT * FROM app_stats")
                        old_data = cursor.fetchall()
                        has_data = len(old_data) > 0
                    except Exception:
                        has_data = False
                    
                    cursor.execute("DROP TABLE IF EXISTS app_stats")
                    conn.commit()
                    table_exists = None
                    
                    if has_data:
                        logger.info("Старые данные будут потеряны при пересоздании таблицы")
            
            if not table_exists:
                # Создаем таблицу с правильной структурой
                cursor.execute("""
                    CREATE TABLE app_stats (
                        app_name TEXT PRIMARY KEY,
                        launches INTEGER DEFAULT 0,
                        total_time REAL DEFAULT 0,
                        last_launch TEXT,
                        last_session_start REAL
                    )
                """)
                conn.commit()
            
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка инициализации БД статистики: {e}")
    
    def _get_process_name(self, app_name: str) -> Optional[str]:
        """Get process name for app from config."""
        return self.config.get_process_name(app_name)
    
    def is_running(self, app_name: str) -> bool:
        """Check if the application is currently running."""
        # Проверяем по сохраненному PID
        pid = self.running_pids.get(app_name)
        if pid:
            if HAS_PSUTIL:
                if psutil.pid_exists(pid):  # type: ignore
                    try:
                        proc = psutil.Process(pid)  # type: ignore
                        if proc.is_running():
                            return True
                    except psutil.NoSuchProcess:  # type: ignore
                        pass
                # PID мертвый, удаляем
                self.running_pids.pop(app_name, None)
                self.save_pids()
            else:
                try:
                    result = subprocess.run(
                        ["tasklist", "/fi", f"pid eq {pid}"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5
                    )
                    if str(pid) in result.stdout:
                        return True
                    else:
                        # PID мертвый, удаляем
                        self.running_pids.pop(app_name, None)
                        self.save_pids()
                except (subprocess.TimeoutExpired, Exception) as e:
                    logger.warning(f"Ошибка проверки PID {pid}: {e}")
        
        # Fallback: проверяем по имени процесса
        proc_name = self._get_process_name(app_name)
        if proc_name:
            if HAS_PSUTIL:
                try:
                    for proc in psutil.process_iter(['name']):  # type: ignore
                        if proc.info.get('name') and proc.info['name'].lower() == proc_name.lower():
                            # Обновляем PID если нашли процесс
                            self.running_pids[app_name] = proc.pid
                            self.save_pids()
                            return True
                except Exception as e:
                    logger.warning(f"Ошибка поиска процесса {proc_name}: {e}")
            else:
                try:
                    result = subprocess.run(
                        ["tasklist", "/fi", f"imagename eq {proc_name}"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5
                    )
                    return proc_name.lower() in result.stdout.lower()
                except (subprocess.TimeoutExpired, Exception) as e:
                    logger.warning(f"Ошибка проверки процесса {proc_name}: {e}")
        
        return False
    
    def launch_app(self, app_name: str) -> bool:
        """Launch the specified application."""
        app_config = self.config.get_app_config(app_name)
        if not app_config:
            logger.error(f"Приложение {app_name} не найдено в конфигурации")
            return False
        
        # Проверяем, не запущено ли уже
        if self.is_running(app_name):
            logger.info(f"Приложение {app_name} уже запущено")
            return False
        
        # Получаем команду запуска
        cmd = self.config.get_app_command(app_name)
        if not cmd:
            logger.error(f"Не удалось получить команду запуска для {app_name}")
            return False
        
        try:
            # Запускаем приложение
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Сохраняем PID
            self.running_pids[app_name] = proc.pid
            self.save_pids()
            
            # Обновляем статистику
            self._record_launch(app_name)
            
            logger.info(f"Приложение {app_name} запущено (PID {proc.pid})")
            return True
            
        except FileNotFoundError:
            logger.error(f"Файл не найден для {app_name}: {cmd[0]}")
            return False
        except PermissionError:
            logger.error(f"Нет прав для запуска {app_name}")
            return False
        except Exception as e:
            logger.error(f"Не удалось запустить {app_name}: {e}")
            return False
    
    def close_app(self, app_name: str) -> bool:
        """Close the specified application."""
        success = False
        pid = self.running_pids.get(app_name)
        
        # Пытаемся закрыть по PID
        if pid:
            try:
                subprocess.run(
                    ["taskkill", "/pid", str(pid), "/f"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10
                )
                logger.info(f"Приложение {app_name} закрыто (PID {pid})")
                success = True
                # Обновляем статистику времени работы
                self._record_session_end(app_name)
            except subprocess.TimeoutExpired:
                logger.warning(f"Таймаут при закрытии {app_name} (PID {pid})")
            except subprocess.CalledProcessError:
                logger.info(f"Не удалось закрыть {app_name} по PID (возможно, уже закрыто)")
            except Exception as e:
                logger.error(f"Ошибка при закрытии {app_name} по PID: {e}")
            finally:
                self.running_pids.pop(app_name, None)
                self.save_pids()
        
        # Если не получилось по PID, пробуем по имени процесса
        if not success:
            proc_name = self._get_process_name(app_name)
            if proc_name:
                try:
                    subprocess.run(
                        ["taskkill", "/f", "/im", proc_name],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10
                    )
                    logger.info(f"Приложение {app_name} закрыто по имени процесса")
                    success = True
                    self._record_session_end(app_name)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Таймаут при закрытии {app_name} по имени")
                except subprocess.CalledProcessError:
                    logger.info(f"Не удалось закрыть {app_name} по имени процесса")
                except Exception as e:
                    logger.error(f"Ошибка при закрытии {app_name} по имени: {e}")
        
        return success
    
    def close_all_apps(self) -> List[str]:
        """Close all running applications and return list of closed apps."""
        closed: List[str] = []
        # Получаем список всех приложений из конфига
        all_apps = list(self.config.get_all_apps().keys())
        
        for app_name in all_apps:
            if self.is_running(app_name):
                if self.close_app(app_name):
                    closed.append(app_name)
        
        return closed
    
    def _record_launch(self, app_name: str) -> None:
        """Record application launch in statistics."""
        try:
            conn = sqlite3.connect(STATS_DB_FILE)
            cursor = conn.cursor()
            
            # Проверяем, есть ли запись
            cursor.execute("SELECT launches FROM app_stats WHERE app_name = ?", (app_name,))
            row = cursor.fetchone()
            
            now = datetime.now().isoformat()
            session_start = time.time()
            
            if row:
                # Обновляем существующую запись
                cursor.execute("""
                    UPDATE app_stats 
                    SET launches = launches + 1,
                        last_launch = ?,
                        last_session_start = ?
                    WHERE app_name = ?
                """, (now, session_start, app_name))
            else:
                # Создаем новую запись
                cursor.execute("""
                    INSERT INTO app_stats (app_name, launches, last_launch, last_session_start)
                    VALUES (?, 1, ?, ?)
                """, (app_name, now, session_start))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка записи статистики запуска для {app_name}: {e}")
    
    def _record_session_end(self, app_name: str) -> None:
        """Record application session end and update total time."""
        try:
            conn = sqlite3.connect(STATS_DB_FILE)
            cursor = conn.cursor()
            
            # Получаем время начала сессии
            cursor.execute("SELECT last_session_start FROM app_stats WHERE app_name = ?", (app_name,))
            row = cursor.fetchone()
            
            if row and row[0]:
                session_start = row[0]
                session_duration = time.time() - session_start
                
                # Обновляем общее время
                cursor.execute("""
                    UPDATE app_stats 
                    SET total_time = total_time + ?,
                        last_session_start = NULL
                    WHERE app_name = ?
                """, (session_duration, app_name))
                
                conn.commit()
            
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка записи статистики закрытия для {app_name}: {e}")
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all applications."""
        stats: Dict[str, Dict[str, Any]] = {}
        
        try:
            conn = sqlite3.connect(STATS_DB_FILE)
            cursor = conn.cursor()
            
            # Получаем статистику для всех приложений из конфига
            all_apps = self.config.get_all_apps()
            
            for app_name in all_apps.keys():
                cursor.execute("""
                    SELECT launches, total_time, last_launch 
                    FROM app_stats 
                    WHERE app_name = ?
                """, (app_name,))
                
                row = cursor.fetchone()
                
                if row:
                    launches, total_time, last_launch = row
                    stats[app_name] = {
                        "launches": launches or 0,
                        "total_time": total_time or 0.0,
                        "last_launch": last_launch or "никогда"
                    }
                else:
                    # Если нет статистики, создаем пустую запись
                    stats[app_name] = {
                        "launches": 0,
                        "total_time": 0.0,
                        "last_launch": "никогда"
                    }
            
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            # Возвращаем пустую статистику для всех приложений
            all_apps = self.config.get_all_apps()
            for app_name in all_apps.keys():
                stats[app_name] = {
                    "launches": 0,
                    "total_time": 0.0,
                    "last_launch": "никогда"
                }
        
        return stats


# Singleton instance
_manager: Optional[AppManager] = None


def get_manager() -> AppManager:
    """Get singleton AppManager instance."""
    global _manager
    if _manager is None:
        _manager = AppManager()
    return _manager


# Обратная совместимость: старые функции (deprecated, но оставляем для совместимости)
def load_pids() -> None:
    """Load PIDs (deprecated, use AppManager)."""
    manager = get_manager()
    manager._load_pids()


def save_pids() -> None:
    """Save PIDs (deprecated, use AppManager)."""
    manager = get_manager()
    manager.save_pids()


def is_running(app_name: str) -> bool:
    """Check if app is running (deprecated, use AppManager)."""
    manager = get_manager()
    return manager.is_running(app_name)


def launch_app(app_name: str) -> bool:
    """Launch app (deprecated, use AppManager)."""
    manager = get_manager()
    return manager.launch_app(app_name)


def close_app(app_name: str) -> bool:
    """Close app (deprecated, use AppManager)."""
    manager = get_manager()
    return manager.close_app(app_name)


def close_all_apps() -> List[str]:
    """Close all apps (deprecated, use AppManager)."""
    manager = get_manager()
    return manager.close_all_apps()
