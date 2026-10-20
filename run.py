"""
Точка входа для запуска приложения Password Manager.

Приложение работает как локальный сервер и показывает иконку в системном трее
Windows: через неё можно открыть интерфейс в браузере или завершить работу.
Сборка без консольного окна: build.bat (PyInstaller, ключ --noconsole).
"""
# pyinstaller --noconfirm --clean --onefile --noconsole --name PasswordManager --icon "assets/icon.ico" --add-data "static;static" --add-data "assets;assets" --collect-submodules uvicorn run.py

import logging
import logging.handlers
import socket
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import HOST, ICON_PATH, LOG_FILE, PORT, STATIC_DIR
from app.routers import api
from app.storage import initialize_files
from app.tray import TrayIcon, show_message

# Браузер открываем только при обычном запуске (python run.py или EXE),
# но не при импорте модуля сервером разработки.
_OPEN_BROWSER = __name__ == "__main__"

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """
    Логирование в файл рядом с приложением и в консоль, если она есть.

    В сборке без консоли sys.stderr равен None, поэтому вывод в него не добавляем.
    """
    handlers: list[logging.Handler] = []

    try:
        handlers.append(
            logging.handlers.RotatingFileHandler(
                LOG_FILE,
                maxBytes=1_000_000,
                backupCount=2,
                encoding="utf-8",
            )
        )
    except OSError:
        pass

    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )


def _port_in_use(port: int) -> bool:
    """Проверяет, занят ли порт (например, уже запущенным экземпляром)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return True
    return False


def _open_browser() -> None:
    """Открывает браузер после старта сервера."""
    try:
        webbrowser.open(f"http://127.0.0.1:{PORT}/")
        logger.info("Browser opened automatically")
    except Exception as e:
        logger.warning(f"Could not open browser: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления жизненным циклом приложения.
    """
    # Инициализация файлов
    initialize_files()
    logger.info("Password Manager started: http://127.0.0.1:%s/", PORT)

    if _OPEN_BROWSER:
        # Небольшая задержка, чтобы сервер успел начать принимать соединения.
        timer = threading.Timer(1.0, _open_browser)
        timer.daemon = True
        timer.start()

    yield  # Приложение работает

    logger.info("Shutting down...")


# Создание FastAPI приложения
app = FastAPI(
    title="Password Manager",
    description="Менеджер паролей с шифрованием данных",
    version="2.0",
    lifespan=lifespan
)

# Подключение роутеров
app.include_router(api.router)

# Подключение статических файлов
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Отдаёт favicon из static/, с SVG-заглушкой на случай его отсутствия."""
    icon_path = STATIC_DIR / "favicon.ico"
    if icon_path.exists():
        return FileResponse(icon_path, media_type="image/x-icon")

    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🔑</text></svg>'
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
def root():
    """
    Главная страница приложения.
    """
    index_html = STATIC_DIR / "index.html"
    try:
        html_content = index_html.read_text(encoding="utf-8")
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        logger.error("index.html not found: %s", index_html)
        return HTMLResponse(
            content=f"<html><body><h1>Error: HTML file not found</h1><p>Expected at: {index_html}</p></body></html>",
            status_code=404
        )
    except OSError as e:
        logger.error("Error serving HTML: %s", e)
        return HTMLResponse(
            content="<html><body><h1>Error loading HTML</h1></body></html>",
            status_code=500
        )


def main() -> None:
    """Запускает сервер и иконку в системном трее."""
    _configure_logging()

    logger.info("=" * 60)
    logger.info("Starting Password Manager v2.0")
    logger.info("=" * 60)

    if _port_in_use(PORT):
        message = (
            f"Порт {PORT} уже занят.\n\n"
            "Скорее всего, Password Manager уже запущен — "
            "проверьте значок в системном трее."
        )
        logger.error(message)
        show_message("Password Manager", message, error=True)
        return

    # Запуск сервера.
    # Передаём объект приложения, а не строку "run:app": в onefile-сборке
    # повторный импорт модуля не нужен и может привести к двойной инициализации.
    # log_config=None: сообщения uvicorn идут в наши обработчики (файл + консоль).
    config = uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        log_config=None,
    )
    server = uvicorn.Server(config)

    tray = None
    if TrayIcon.is_supported():
        tray = TrayIcon(
            icon_path=ICON_PATH,
            tooltip=f"Password Manager — http://127.0.0.1:{PORT}/",
            on_open=lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/"),
            on_exit=lambda: setattr(server, "should_exit", True),
        )
        if not tray.start():
            logger.warning("Tray icon is unavailable, running without it")
            tray = None

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        if tray is not None:
            tray.stop()
        logger.info("Password Manager stopped")


# Точка входа
if __name__ == "__main__":
    main()
