# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
"""
Improved Gaming-Style GUI with logging and statistics.
"""

import customtkinter as ctk  # type: ignore
import logging
from typing import Dict, Tuple, Any, Optional
from datetime import datetime
from app_manager import get_manager

# Геймерская цветовая схема
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


class TextHandler(logging.Handler):
    """Custom logging handler for CTkTextbox."""
    
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    
    def emit(self, record):
        msg = self.format(record)
        
        def append():
            self.text_widget.configure(state="normal")
            self.text_widget.insert("end", msg + "\n")
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        
        # Schedule GUI update
        self.text_widget.after(0, append)


class AppManagerGUI:
    """Gaming-style GUI application with logging and statistics."""

    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root: Any = ctk.CTk()
        self.root.title("🎮 SONYA GAMING CONTROL 🎮")
        self.root.geometry("900x900")
        self.root.resizable(False, False)
        self.root.configure(fg_color=COLORS["bg_dark"])

        # Инициализация менеджера
        self.manager = get_manager()
        
        # GUI элементы
        self.app_buttons: Dict[str, Tuple[Any, Any]] = {}
        self.status_labels: Dict[str, Any] = {}
        self.status_indicators: Dict[str, Any] = {}
        
        # Флаг для отслеживания закрытия окна
        self._is_closing = False
        
        # Настройка логирования
        self.setup_logging()
        
        # Создание интерфейса
        self.create_ui()
        
        # Обновление статусов
        self.update_statuses()
        
        # Автообновление каждые 5 секунд
        self.schedule_update()
        
        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_logging(self):
        """Setup logging to GUI."""
        self.logger = logging.getLogger("gui_logger")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
    
    def schedule_update(self):
        """Schedule periodic status updates."""
        if self._is_closing:
            return
        
        try:
            # Проверяем, что окно еще существует
            if not self.root.winfo_exists():
                self._is_closing = True
                return
            
            self.update_statuses()
            
            # Планируем следующее обновление только если окно не закрывается
            if not self._is_closing:
                self.root.after(5000, self.schedule_update)  # Каждые 5 секунд
        except Exception as e:
            # Если окно уже уничтожено, просто выходим
            self._is_closing = True
            self.logger.debug(f"Окно закрыто, прекращаем обновления: {e}")

    def create_ui(self):
        """Create the main UI."""
        main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # === HEADER ===
        header_frame = ctk.CTkFrame(main_container, fg_color=COLORS["bg_card"], corner_radius=15)
        header_frame.pack(fill="x", pady=(0, 15))

        title_label = ctk.CTkLabel(
            header_frame,
            text="⚡ SONYA CONTROL PANEL ⚡",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        title_label.pack(pady=15)

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Gaming Applications Manager with Statistics",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_dim"]
        )
        subtitle_label.pack(pady=(0, 15))

        # === TABS ===
        self.tabview = ctk.CTkTabview(
            main_container,
            width=840,
            height=650,
            fg_color=COLORS["bg_card"],
            segmented_button_fg_color=COLORS["bg_dark"],
            segmented_button_selected_color=COLORS["accent_blue"],
            segmented_button_selected_hover_color=COLORS["accent_purple"]
        )
        self.tabview.pack(fill="both", expand=True, pady=(0, 15))

        # Вкладки
        self.tab_apps = self.tabview.add("Applications")
        self.tab_stats = self.tabview.add("Statistics")
        self.tab_logs = self.tabview.add("Logs")

        # Создаем вкладки
        self.create_apps_tab()
        self.create_stats_tab()
        self.create_logs_tab()

        # === CONTROL PANEL ===
        control_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        control_frame.pack(fill="x", pady=(0, 15))

        refresh_btn = ctk.CTkButton(
            control_frame,
            text="🔄 REFRESH STATUS",
            command=self.update_statuses,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45,
            corner_radius=10,
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["accent_purple"],
            border_width=2,
            border_color=COLORS["accent_blue"]
        )
        refresh_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        close_all_btn = ctk.CTkButton(
            control_frame,
            text="🛑 TERMINATE ALL",
            command=self.close_all_apps,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45,
            corner_radius=10,
            fg_color=COLORS["danger"],
            hover_color="#dc2626",
            border_width=2,
            border_color=COLORS["danger"]
        )
        close_all_btn.pack(side="left", fill="x", expand=True)

        # === STATUS BAR ===
        self.status_bar_frame: Any = ctk.CTkFrame(
            main_container,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            height=50
        )
        self.status_bar_frame.pack(fill="x")

        self.status_bar: Any = ctk.CTkLabel(
            self.status_bar_frame,
            text="⚡ System Ready",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        self.status_bar.pack(pady=15)

    def create_apps_tab(self):
        """Create applications management tab."""
        scroll_frame = ctk.CTkScrollableFrame(
            self.tab_apps,
            fg_color="transparent",
            scrollbar_button_color=COLORS["accent_blue"],
            scrollbar_button_hover_color=COLORS["accent_purple"]
        )
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Получаем все приложения
        for app_name, app_config in self.manager.config.get_all_apps().items():
            self.create_app_card(scroll_frame, app_name, app_config)

    def create_app_card(self, parent: Any, app_name: str, app_config: Dict):
        """Create a single app card."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card_hover"],
            corner_radius=12,
            border_width=2,
            border_color=COLORS["bg_card"]
        )
        card.pack(fill="x", pady=8, padx=5)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=15)

        # Top frame
        top_frame = ctk.CTkFrame(inner, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 10))

        left_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="x", expand=True)

        icon_label = ctk.CTkLabel(
            left_frame,
            text=app_config.get("icon", "📱"),
            font=ctk.CTkFont(size=32),
            width=40
        )
        icon_label.pack(side="left", padx=(0, 15))

        text_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        name_label = ctk.CTkLabel(
            text_frame,
            text=app_config.get("name", app_name.upper()),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text_main"],
            anchor="w"
        )
        name_label.pack(anchor="w")

        # Показываем путь если есть
        path = app_config.get("path", "")
        if path:
            path_label = ctk.CTkLabel(
                text_frame,
                text=f"Path: {path[:50]}..." if len(path) > 50 else f"Path: {path}",
                font=ctk.CTkFont(size=10),
                text_color=COLORS["text_dim"],
                anchor="w"
            )
            path_label.pack(anchor="w")
        else:
            error_label = ctk.CTkLabel(
                text_frame,
                text="⚠ Not found - configure in app_config.json",
                font=ctk.CTkFont(size=10),
                text_color=COLORS["warning"],
                anchor="w"
            )
            error_label.pack(anchor="w")

        # Status
        status_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        status_frame.pack(side="right")

        indicator = ctk.CTkFrame(
            status_frame,
            width=12,
            height=12,
            corner_radius=6,
            fg_color=COLORS["danger"]
        )
        indicator.pack(side="left", padx=(0, 8))
        self.status_indicators[app_name] = indicator

        status_label = ctk.CTkLabel(
            status_frame,
            text="OFFLINE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["danger"]
        )
        status_label.pack(side="left")
        self.status_labels[app_name] = status_label

        # Buttons
        button_frame = ctk.CTkFrame(inner, fg_color="transparent")
        button_frame.pack(fill="x")

        # Определяем цвет кнопки
        color_map = {
            "dota": COLORS["accent_blue"],
            "spotify": "#1db954",
            "discord": "#5865f2",
            "vscode": "#007acc"
        }
        btn_color = color_map.get(app_name, COLORS["accent_purple"])

        launch_btn = ctk.CTkButton(
            button_frame,
            text="▶ LAUNCH",
            command=lambda: self.launch_app_gui(app_name),
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            corner_radius=8,
            fg_color=btn_color,
            hover_color=self.darken_color(btn_color),
            border_width=0
        )
        launch_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        close_btn = ctk.CTkButton(
            button_frame,
            text="■ STOP",
            command=lambda: self.close_app_gui(app_name),
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            corner_radius=8,
            fg_color=COLORS["danger"],
            hover_color="#dc2626",
            border_width=0
        )
        close_btn.pack(side="left", fill="x", expand=True)

        self.app_buttons[app_name] = (launch_btn, close_btn)

    def create_stats_tab(self):
        """Create statistics tab."""
        scroll_frame = ctk.CTkScrollableFrame(
            self.tab_stats,
            fg_color="transparent",
            scrollbar_button_color=COLORS["accent_blue"]
        )
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Заголовок
        title = ctk.CTkLabel(
            scroll_frame,
            text="📊 APPLICATION USAGE STATISTICS",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        title.pack(pady=(10, 20))

        # Статистика для каждого приложения
        stats = self.manager.get_stats()
        
        for app_name, app_stats in stats.items():
            app_config = self.manager.config.get_app_config(app_name)
            if not app_config:
                continue
            
            self.create_stats_card(scroll_frame, app_name, app_config, app_stats)

    def create_stats_card(self, parent, app_name: str, app_config: Dict, app_stats: Dict):
        """Create statistics card for an app."""
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card_hover"], corner_radius=12)
        card.pack(fill="x", pady=8, padx=5)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", padx=20, pady=15)

        # Header
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        icon = ctk.CTkLabel(
            header,
            text=app_config.get("icon", "📱"),
            font=ctk.CTkFont(size=24)
        )
        icon.pack(side="left", padx=(0, 10))

        name = ctk.CTkLabel(
            header,
            text=app_config.get("name", app_name.upper()),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_main"]
        )
        name.pack(side="left")

        # Stats
        stats_frame = ctk.CTkFrame(inner, fg_color="transparent")
        stats_frame.pack(fill="x")

        # Launches
        launches = app_stats.get("launches", 0)
        launches_label = ctk.CTkLabel(
            stats_frame,
            text=f"🚀 Launches: {launches}",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"]
        )
        launches_label.pack(anchor="w", pady=2)

        # Total time
        total_time = app_stats.get("total_time", 0)
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        
        time_label = ctk.CTkLabel(
            stats_frame,
            text=f"⏱ Total Time: {time_str}",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"]
        )
        time_label.pack(anchor="w", pady=2)

        # Last launch
        last_launch = app_stats.get("last_launch")
        if last_launch:
            try:
                dt = datetime.fromisoformat(last_launch)
                last_str = dt.strftime("%d.%m.%Y %H:%M")
                last_label = ctk.CTkLabel(
                    stats_frame,
                    text=f"📅 Last Launch: {last_str}",
                    font=ctk.CTkFont(size=13),
                    text_color=COLORS["text_dim"]
                )
                last_label.pack(anchor="w", pady=2)
            except Exception:
                pass

    def create_logs_tab(self):
        """Create logs tab."""
        container = ctk.CTkFrame(self.tab_logs, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Заголовок
        title = ctk.CTkLabel(
            container,
            text="📜 SYSTEM LOGS",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["accent_blue"]
        )
        title.pack(pady=(10, 15))

        # Log text widget
        self.log_text = ctk.CTkTextbox(
            container,
            fg_color=COLORS["bg_dark"],
            text_color=COLORS["text_main"],
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        # Добавляем handler для логов
        text_handler = TextHandler(self.log_text)
        self.logger.addHandler(text_handler)

        # Также добавляем в основной логгер app_manager
        app_logger = logging.getLogger("app_manager")
        app_logger.addHandler(text_handler)

        self.logger.info("GUI запущен успешно")

    def darken_color(self, color: str) -> str:
        """Darken a hex color."""
        color = color.lstrip('#')
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r, g, b = int(r * 0.8), int(g * 0.8), int(b * 0.8)
        return f"#{r:02x}{g:02x}{b:02x}"

    def launch_app_gui(self, app_name: str):
        """Launch app from GUI with error handling."""
        try:
            success = self.manager.launch_app(app_name)
            self.update_statuses()
            
            if success:
                try:
                    app_config = self.manager.config.get_app_config(app_name)
                    name = app_config.get("name", app_name) if app_config else app_name
                except Exception as e:
                    self.logger.warning(f"Ошибка получения конфига для {app_name}: {e}")
                    name = app_name
                
                self.status_bar.configure(
                    text=f"⚡ {name} launched successfully!",
                    text_color=COLORS["success"]
                )
                self.logger.info(f"{name} запущен")
            else:
                self.status_bar.configure(
                    text=f"❌ Failed to launch {app_name}",
                    text_color=COLORS["danger"]
                )
                self.logger.error(f"Не удалось запустить {app_name}")
        except Exception as e:
            self.logger.error(f"Критическая ошибка при запуске {app_name}: {e}")
            self.status_bar.configure(
                text=f"❌ Error launching {app_name}",
                text_color=COLORS["danger"]
            )

    def close_app_gui(self, app_name: str):
        """Close app from GUI with error handling."""
        try:
            success = self.manager.close_app(app_name)
            self.update_statuses()
            
            if success:
                try:
                    app_config = self.manager.config.get_app_config(app_name)
                    name = app_config.get("name", app_name) if app_config else app_name
                except Exception as e:
                    self.logger.warning(f"Ошибка получения конфига для {app_name}: {e}")
                    name = app_name
                
                self.status_bar.configure(
                    text=f"🛑 {name} terminated",
                    text_color=COLORS["warning"]
                )
                self.logger.info(f"{name} закрыт")
            else:
                self.status_bar.configure(
                    text=f"❌ Failed to terminate {app_name}",
                    text_color=COLORS["danger"]
                )
                self.logger.error(f"Не удалось закрыть {app_name}")
        except Exception as e:
            self.logger.error(f"Критическая ошибка при закрытии {app_name}: {e}")
            self.status_bar.configure(
                text=f"❌ Error terminating {app_name}",
                text_color=COLORS["danger"]
            )

    def update_statuses(self):
        """Update all app statuses with error handling."""
        if self._is_closing:
            return
        
        try:
            # Проверяем, что окно еще существует
            if not self.root.winfo_exists():
                self._is_closing = True
                return
            
            for app_name in self.status_labels:
                if self._is_closing:
                    return
                
                try:
                    running = self.manager.is_running(app_name)
                    
                    if running:
                        self.status_labels[app_name].configure(
                            text="ONLINE",
                            text_color=COLORS["success"]
                        )
                        self.status_indicators[app_name].configure(
                            fg_color=COLORS["success"]
                        )
                    else:
                        self.status_labels[app_name].configure(
                            text="OFFLINE",
                            text_color=COLORS["danger"]
                        )
                        self.status_indicators[app_name].configure(
                            fg_color=COLORS["danger"]
                        )
                except Exception as e:
                    if not self._is_closing:
                        self.logger.warning(f"Ошибка обновления статуса для {app_name}: {e}")
                    # Устанавливаем статус OFFLINE при ошибке
                    try:
                        if not self._is_closing:
                            self.status_labels[app_name].configure(
                                text="ERROR",
                                text_color=COLORS["warning"]
                            )
                    except Exception:
                        pass
            
            # Обновляем вкладку статистики
            if not self._is_closing:
                try:
                    self.refresh_stats_tab()
                except Exception as e:
                    if not self._is_closing:
                        self.logger.warning(f"Ошибка обновления статистики: {e}")
        except Exception as e:
            if not self._is_closing:
                self.logger.error(f"Критическая ошибка обновления статусов: {e}")

    def refresh_stats_tab(self):
        """Refresh statistics tab."""
        # Очищаем и пересоздаем
        for widget in self.tab_stats.winfo_children():
            widget.destroy()
        self.create_stats_tab()

    def close_all_apps(self):
        """Close all running apps with error handling."""
        try:
            closed = self.manager.close_all_apps()
            self.update_statuses()
            
            if closed:
                app_names = []
                for app in closed:
                    try:
                        app_config = self.manager.config.get_app_config(app)
                        name = app_config.get("name", app) if app_config else app
                        app_names.append(name)
                    except Exception as e:
                        self.logger.warning(f"Ошибка получения имени для {app}: {e}")
                        app_names.append(app)
                
                self.status_bar.configure(
                    text=f"🛑 Terminated: {', '.join(app_names)}",
                    text_color=COLORS["warning"]
                )
                self.logger.info(f"Закрыто: {', '.join(app_names)}")
            else:
                self.status_bar.configure(
                    text="⚠ No applications were running",
                    text_color=COLORS["text_dim"]
                )
                self.logger.info("Нечего закрывать")
        except Exception as e:
            self.logger.error(f"Критическая ошибка закрытия всех приложений: {e}")
            self.status_bar.configure(
                text="❌ Error closing applications",
                text_color=COLORS["danger"]
            )

    def on_closing(self):
        """Handle window closing."""
        self._is_closing = True
        try:
            self.logger.info("Закрытие приложения...")
            self.manager.close_all_apps()
            self.manager.save_pids()
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии: {e}")
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass
    
    def run(self):
        """Run the GUI main loop."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing()
        except Exception as e:
            self.logger.error(f"Ошибка в главном цикле: {e}")
            self.on_closing()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = AppManagerGUI()
    app.run()