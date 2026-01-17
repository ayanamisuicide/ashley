"""
Improved Telegram bot with rate limiting and better error handling.
"""

import logging
import os
import sys
import traceback
from datetime import datetime
from functools import wraps
from time import time
from typing import Dict, Any, Callable

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

from responses import responses as bot_responses
from app_manager import get_manager

# Загружаем переменные окружения из .env файла
load_dotenv()

# Fix console encoding for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
        sys.stderr.reconfigure(encoding='utf-8')  # type: ignore
    except AttributeError:
        pass

load_dotenv()

# LOGGING
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.INFO)
logger.propagate = False

_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

file_handler = logging.FileHandler("bot_responses.log", encoding="utf-8")
file_handler.setFormatter(_formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(_formatter)

logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# TOKENS
TOKEN_STR = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN_STR:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не найден в .env файле")
TOKEN: str = TOKEN_STR

ADMIN_ID_STR = os.getenv("ADMIN_ID")
if not ADMIN_ID_STR:
    raise RuntimeError("ADMIN_ID не найден в .env файле")
ADMIN_ID = int(ADMIN_ID_STR)

# USER DATA
users: Dict[int, Dict[str, Any]] = {}
last_command_time: Dict[int, float] = {}

# Rate limiting
RATE_LIMIT_SECONDS = 2


def get_user(user_id: int) -> Dict[str, Any]:
    """Get or create user data."""
    if user_id not in users:
        users[user_id] = {
            "role": "admin" if user_id == ADMIN_ID else "user",
            "last_seen": datetime.now(),
            "command_count": 0
        }
    else:
        users[user_id]["last_seen"] = datetime.now()
    return users[user_id]


def rate_limit(seconds: int = RATE_LIMIT_SECONDS) -> Callable:
    """Rate limiting decorator for commands."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_user is None:
                return
            
            user_id = update.effective_user.id
            now = time()
            
            # Rate limit не применяется к админу
            if user_id != ADMIN_ID:
                if user_id in last_command_time:
                    time_since_last = now - last_command_time[user_id]
                    if time_since_last < seconds:
                        remaining = seconds - time_since_last
                        msg = f"Помедленнее! Подожди {remaining:.1f} сек 😊"
                        if update.message:
                            await update.message.reply_text(msg)
                        logger.warning(f"RATE_LIMIT | {user_id} | {remaining:.1f}s осталось")
                        return
            
            last_command_time[user_id] = now
            return await func(update, context)
        return wrapper
    return decorator


async def reply_log(msg: str, update: Update, user_id: int) -> None:
    """Reply to user and log the message with error handling."""
    if update.message:
        try:
            await update.message.reply_text(msg)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            # Пытаемся отправить через send_message
            try:
                if update.effective_chat:
                    await update.message.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=msg
                    )
            except Exception as e2:
                logger.error(f"Не удалось отправить сообщение через send_message: {e2}")
    logger.info(f"OUT | {user_id} | {msg[:100]}{'...' if len(msg) > 100 else ''}")


@rate_limit()
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages from users."""
    if update.message is None or update.effective_user is None:
        return
    
    message = update.message
    effective_user = update.effective_user
    user_id = effective_user.id
    raw_text = (message.text or "").strip()
    
    if not raw_text:
        logger.info(f"EMPTY | {user_id} | Пустое сообщение")
        return
    
    text = raw_text.lower()
    logger.info(f"IN | {user_id} | {raw_text}")
    
    user_data = get_user(user_id)
    user_data["command_count"] += 1
    
    # Проверка доступа
    if user_id != ADMIN_ID:
        msg = "извини, но нет)"
        await reply_log(msg, update, user_id)
        return
    
    # Получаем менеджер приложений
    manager = get_manager()
    
    words = text.split()
    command = words[0] if words else ""
    target_raw = words[1] if len(words) > 1 else ""
    target = "".join(ch for ch in target_raw if ch.isalnum() or ch in ["_", "-"]).lower()
    
    logger.debug(f"PARSE | {user_id} | command={command} target={target}")
    
    # === КОМАНДЫ ===
    
    # Хелп
    if command in ["хелп", "help"]:
        msg = bot_responses["help"]["admin"]
        await reply_log(msg, update, user_id)
        return
    
    # Ответы
    if command in ["ответы", "responses", "командыответы"]:
        msg = bot_responses["responses"]["admin"]
        await reply_log(msg, update, user_id)
        return
    
    # Статус
    if command in ["ты", "жива", "жива?", "онлайн", "status"]:
        msg = bot_responses["status"]["admin"]
        await reply_log(msg, update, user_id)
        return
    
    # Меню
    if command in ["меню", "menu"]:
        games = "\n".join([f"- {name}" for name in bot_responses["app_menus"]["games"].values()])
        programs = "\n".join([f"- {name}" for name in bot_responses["app_menus"]["programs"].values()])
        msg = f"{bot_responses['menu']['main']['admin']}\n\nИгры:\n{games}\n\nПрограммы:\n{programs}"
        await reply_log(msg, update, user_id)
        return
    
    # Статистика
    if command in ["статистика", "stats", "стата"]:
        try:
            stats = manager.get_stats()
            lines = [bot_responses["menu"]["stats"]["admin"], ""]
            
            for app_name, app_stats in stats.items():
                try:
                    app_config = manager.config.get_app_config(app_name)
                    if not app_config:
                        continue
                    
                    icon = app_config.get("icon", "📱")
                    name = app_config.get("name", app_name)
                    launches = app_stats.get("launches", 0)
                    total_time = app_stats.get("total_time", 0)
                    last_launch = app_stats.get("last_launch", "никогда")
                    
                    # Конвертируем время в читаемый формат
                    hours = total_time // 3600
                    minutes = (total_time % 3600) // 60
                    
                    time_str = f"{int(hours)}ч {int(minutes)}м" if hours > 0 else f"{int(minutes)}м"
                    
                    lines.append(f"{icon} {name}:")
                    lines.append(f"  • Запусков: {launches}")
                    lines.append(f"  • Общее время: {time_str}")
                    
                    if last_launch != "никогда":
                        try:
                            dt = datetime.fromisoformat(last_launch)
                            last_str = dt.strftime("%d.%m.%Y %H:%M")
                            lines.append(f"  • Последний: {last_str}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Ошибка парсинга даты для {app_name}: {e}")
                except Exception as e:
                    logger.error(f"Ошибка обработки статистики для {app_name}: {e}")
                    continue
            
            msg = "\n".join(lines)
            await reply_log(msg, update, user_id)
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await reply_log("Произошла ошибка при получении статистики 💖", update, user_id)
        return
    
    # Запуск приложений
    for app_name in bot_responses["app_commands"]:
        commands = bot_responses["app_commands"][app_name]["commands"]
        if command in commands:
            try:
                if manager.is_running(app_name):
                    app_config = manager.config.get_app_config(app_name)
                    app_display_name = app_config.get("name", app_name) if app_config else app_name
                    msg = bot_responses["already_running"]["admin"].format(app_name=app_display_name)
                else:
                    success = manager.launch_app(app_name)
                    if success:
                        msg = bot_responses["app_commands"][app_name]["responses"]["admin"]
                    else:
                        msg = bot_responses["launch_failure"]["admin"]
                await reply_log(msg, update, user_id)
            except Exception as e:
                logger.error(f"Ошибка запуска {app_name}: {e}")
                await reply_log(bot_responses["launch_failure"]["admin"], update, user_id)
            return
    
    # Закрытие приложений
    if command in ["стоп", "закрой", "выключи"]:
        try:
            if target:
                # Закрыть конкретное приложение
                for app_name in bot_responses["app_close_commands"]:
                    commands = bot_responses["app_close_commands"][app_name]["commands"]
                    if target in commands:
                        try:
                            if manager.is_running(app_name):
                                success = manager.close_app(app_name)
                                if success:
                                    msg = bot_responses["app_close_commands"][app_name]["responses"]["admin"]
                                else:
                                    msg = bot_responses["close_failure"]["admin"]
                            else:
                                app_config = manager.config.get_app_config(app_name)
                                app_display_name = app_config.get("name", app_name) if app_config else app_name
                                msg = bot_responses["not_running"]["admin"].format(app_name=app_display_name)
                            await reply_log(msg, update, user_id)
                        except Exception as e:
                            logger.error(f"Ошибка закрытия {app_name}: {e}")
                            await reply_log(bot_responses["close_failure"]["admin"], update, user_id)
                        return
            
            # Закрыть все приложения
            closed = manager.close_all_apps()
            if closed:
                app_names = []
                for app in closed:
                    try:
                        app_config = manager.config.get_app_config(app)
                        name = app_config.get("name", app) if app_config else app
                        app_names.append(name)
                    except Exception:
                        app_names.append(app)
                msg = f"Закрыто: {', '.join(app_names)} 💖"
            else:
                msg = "Ничего не было запущено, мой любимый 💖"
            await reply_log(msg, update, user_id)
        except Exception as e:
            logger.error(f"Ошибка закрытия приложений: {e}")
            await reply_log("Произошла ошибка при закрытии приложений 💖", update, user_id)
        return
    
    # Fallback
    msg = bot_responses["fallback"]["admin"]
    await reply_log(msg, update, user_id)


@rate_limit()
async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if update.effective_user and update.effective_user.id == ADMIN_ID:
        msg = "Привет, мой любимый Крис 💖\n\nЯ готова управлять твоими приложениями!\nНапиши /help для списка команд."
    else:
        msg = "извини, но нет)"
    
    if update.message:
        await update.message.reply_text(msg)


@rate_limit()
async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if update.effective_user and update.effective_user.id == ADMIN_ID:
        msg = bot_responses["help"]["admin"]
    else:
        msg = "извини, но нет)"
    
    if update.message:
        await update.message.reply_text(msg)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:  # type: ignore
    """Handle errors in the bot with improved error handling."""
    error = context.error  # type: ignore
    tb = "".join(traceback.format_exception(None, error, error.__traceback__))  # type: ignore
    
    # Логируем ошибку
    logger.error(f"EXCEPTION: {error}\n{tb}")
    
    # Обрабатываем специфичные ошибки Telegram API
    try:
        from telegram.error import NetworkError, TimedOut, RetryAfter, TelegramError  # type: ignore
    except ImportError:
        # Если старые версии библиотеки, используем общую обработку
        NetworkError = Exception
        TimedOut = Exception
        RetryAfter = Exception
        TelegramError = Exception
    
    if isinstance(error, NetworkError):
        logger.warning("Ошибка сети Telegram API, повторная попытка...")
        return
    elif isinstance(error, TimedOut):
        logger.warning("Таймаут Telegram API")
        return
    elif isinstance(error, RetryAfter):
        logger.warning(f"Rate limit: нужно подождать {error.retry_after} секунд")
        return
    elif isinstance(error, TelegramError):
        logger.error(f"Ошибка Telegram API: {error}")
    
    # Пытаемся отправить сообщение об ошибке пользователю
    if update and isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=bot_responses["error"]["admin"]
            )
        except NetworkError:
            logger.warning("Не удалось отправить сообщение об ошибке: проблема с сетью")
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


def main() -> None:
    """Main function to start the bot with improved error handling."""
    # Инициализируем менеджер (загружает PIDs и конфиг)
    try:
        manager = get_manager()
    except Exception as e:
        logger.error(f"Критическая ошибка инициализации менеджера: {e}")
        raise
    
    try:
        app = Application.builder().token(TOKEN).build()
        
        # Добавляем обработчики
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)
        
        print(bot_responses["startup"]["admin"])
        logger.info(bot_responses["startup"]["admin"])
        logger.info(f"Админ ID: {ADMIN_ID}")
        
        # Запускаем polling с обработкой ошибок
        try:
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                close_loop=False
            )
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
            raise
        except Exception as e:
            logger.error(f"Ошибка при работе polling: {e}")
            raise
        
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        manager = get_manager()
        manager.close_all_apps()
        manager.save_pids()
        logger.info(bot_responses["shutdown"]["admin"])
        print("\n" + bot_responses["shutdown"]["admin"])
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise