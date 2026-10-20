"""
Иконка приложения в системном трее Windows.

Реализовано на ctypes (Win32 API) без внешних библиотек:
  - Shell_NotifyIconW — добавление/удаление иконки;
  - скрытое окно и цикл сообщений — обработка кликов;
  - TrackPopupMenu — контекстное меню с пунктами «Открыть» и «Выход».

На других ОС трей не создаётся: is_supported() вернёт False.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:  # pragma: no cover - трей только для Windows
    _user32 = _shell32 = _kernel32 = None


# Сообщения и константы Win32
WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_TRAYICON = 0x8000 + 1  # WM_APP + 1

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800

TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONINFORMATION = 0x00000040
MB_SETFOREGROUND = 0x00010000

ERROR_CLASS_ALREADY_EXISTS = 1410

ID_OPEN = 1001
ID_EXIT = 1002

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


if sys.platform == "win32":
    _user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    _user32.RegisterClassW.restype = wintypes.ATOM

    _user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    _user32.CreateWindowExW.restype = wintypes.HWND

    _user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    _user32.DefWindowProcW.restype = ctypes.c_ssize_t

    _user32.DestroyWindow.argtypes = [wintypes.HWND]
    _user32.DestroyWindow.restype = wintypes.BOOL

    _user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
    ]
    _user32.GetMessageW.restype = ctypes.c_int

    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.restype = ctypes.c_ssize_t

    _user32.PostQuitMessage.argtypes = [ctypes.c_int]
    _user32.PostMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    _user32.PostMessageW.restype = wintypes.BOOL

    _user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    _user32.LoadImageW.restype = wintypes.HANDLE

    _user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
    _user32.LoadIconW.restype = wintypes.HICON

    _user32.DestroyIcon.argtypes = [wintypes.HICON]
    _user32.DestroyIcon.restype = wintypes.BOOL

    _user32.CreatePopupMenu.argtypes = []
    _user32.CreatePopupMenu.restype = wintypes.HMENU

    _user32.AppendMenuW.argtypes = [
        wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR,
    ]
    _user32.AppendMenuW.restype = wintypes.BOOL

    _user32.TrackPopupMenu.argtypes = [
        wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.HWND, ctypes.POINTER(wintypes.RECT),
    ]
    _user32.TrackPopupMenu.restype = wintypes.UINT

    _user32.DestroyMenu.argtypes = [wintypes.HMENU]
    _user32.DestroyMenu.restype = wintypes.BOOL

    _user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    _user32.GetCursorPos.restype = wintypes.BOOL

    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL

    _user32.MessageBoxW.argtypes = [
        wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT,
    ]
    _user32.MessageBoxW.restype = ctypes.c_int

    _shell32.Shell_NotifyIconW.argtypes = [
        wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW),
    ]
    _shell32.Shell_NotifyIconW.restype = wintypes.BOOL

    _kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    _kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def show_message(title: str, message: str, error: bool = False) -> None:
    """Показывает системное окно сообщения (полезно в режиме без консоли)."""
    if _user32 is None:
        return
    flags = MB_OK | MB_SETFOREGROUND | (MB_ICONERROR if error else MB_ICONINFORMATION)
    try:
        _user32.MessageBoxW(None, message, title, flags)
    except OSError:
        logger.exception("Could not show message box")


class TrayIcon:
    """Иконка в системном трее с контекстным меню."""

    _CLASS_NAME = "PasswordManagerTrayWindow"

    def __init__(
        self,
        icon_path: Path,
        tooltip: str,
        on_open: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._icon_path = Path(icon_path)
        self._tooltip = tooltip[:127]
        self._on_open = on_open
        self._on_exit = on_exit

        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._started = False
        self._hwnd: Optional[int] = None
        self._hicon: Optional[int] = None
        self._owns_icon = False

        # Ссылку на WNDPROC нельзя терять, иначе Python соберёт её как мусор.
        self._wndproc = WNDPROC(self._handle_message) if _user32 is not None else None

    @staticmethod
    def is_supported() -> bool:
        """Трей поддерживается только в Windows."""
        return _user32 is not None

    def start(self, timeout: float = 3.0) -> bool:
        """Запускает поток с иконкой. Возвращает False, если трей не создан."""
        if not self.is_supported() or self._thread is not None:
            return False

        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self._thread.start()

        if not self._ready.wait(timeout):
            logger.warning("Tray icon did not start in time")
            return False

        return self._started

    def stop(self, timeout: float = 3.0) -> None:
        """Закрывает окно трея и дожидается завершения потока."""
        hwnd = self._hwnd
        if hwnd and _user32 is not None:
            try:
                _user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            except OSError:
                logger.exception("Could not close tray window")

        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    # ---------- Внутренняя реализация ----------

    def _load_icon(self) -> Optional[int]:
        if self._icon_path.exists():
            handle = _user32.LoadImageW(
                None,
                str(self._icon_path),
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE,
            )
            if handle:
                self._owns_icon = True
                return handle
            logger.warning("Could not load tray icon: %s", self._icon_path)

        fallback = _user32.LoadIconW(
            None, ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), wintypes.LPCWSTR)
        )
        return fallback or None

    def _add_icon(self, hwnd: int) -> bool:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_TIP
        data.uCallbackMessage = WM_TRAYICON
        data.szTip = self._tooltip

        self._hicon = self._load_icon()
        if self._hicon:
            data.uFlags |= NIF_ICON
            data.hIcon = self._hicon

        return bool(_shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)))

    def _remove_icon(self, hwnd: int) -> None:
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = hwnd
        data.uID = 1
        _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))

        if self._hicon and self._owns_icon:
            _user32.DestroyIcon(self._hicon)
        self._hicon = None
        self._owns_icon = False

    def _show_menu(self, hwnd: int) -> None:
        menu = _user32.CreatePopupMenu()
        if not menu:
            return

        command = 0
        try:
            _user32.AppendMenuW(menu, MF_STRING, ID_OPEN, "Открыть в браузере")
            _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            _user32.AppendMenuW(menu, MF_STRING, ID_EXIT, "Выход")

            point = wintypes.POINT()
            _user32.GetCursorPos(ctypes.byref(point))
            _user32.SetForegroundWindow(hwnd)
            command = _user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                point.x,
                point.y,
                0,
                hwnd,
                None,
            )
            _user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        finally:
            _user32.DestroyMenu(menu)

        if command == ID_OPEN:
            self._call(self._on_open)
        elif command == ID_EXIT:
            self._call(self._on_exit)
            _user32.DestroyWindow(hwnd)

    def _call(self, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            logger.exception("Tray callback failed")

    def _handle_message(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self._call(self._on_open)
            elif lparam == WM_RBUTTONUP:
                self._show_menu(hwnd)
            return 0

        if msg == WM_CLOSE:
            _user32.DestroyWindow(hwnd)
            return 0

        if msg == WM_DESTROY:
            self._remove_icon(hwnd)
            _user32.PostQuitMessage(0)
            return 0

        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self) -> None:
        try:
            instance = _kernel32.GetModuleHandleW(None)

            window_class = WNDCLASSW()
            window_class.lpfnWndProc = self._wndproc
            window_class.hInstance = instance
            window_class.lpszClassName = self._CLASS_NAME

            if not _user32.RegisterClassW(ctypes.byref(window_class)):
                error = ctypes.get_last_error()
                if error != ERROR_CLASS_ALREADY_EXISTS:
                    logger.warning("RegisterClassW failed: %s", error)
                    self._ready.set()
                    return

            hwnd = _user32.CreateWindowExW(
                0,
                self._CLASS_NAME,
                "Password Manager",
                0,
                0, 0, 0, 0,
                None, None, instance, None,
            )
            if not hwnd:
                logger.warning("CreateWindowExW failed: %s", ctypes.get_last_error())
                self._ready.set()
                return

            self._hwnd = hwnd

            if not self._add_icon(hwnd):
                logger.warning("Shell_NotifyIconW failed: %s", ctypes.get_last_error())
                _user32.DestroyWindow(hwnd)
                self._ready.set()
                return

            self._started = True
            self._ready.set()
            logger.info("Tray icon created")

            message = wintypes.MSG()
            while True:
                result = _user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                _user32.TranslateMessage(ctypes.byref(message))
                _user32.DispatchMessageW(ctypes.byref(message))
        except Exception:
            logger.exception("Tray thread failed")
            self._ready.set()
        finally:
            self._hwnd = None
            self._started = False
            logger.info("Tray icon stopped")
