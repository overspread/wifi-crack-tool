# -*- coding: UTF-8 -*-
"""
WiFi密码暴力破解工具
Author: 白恒aead
Repositories: https://github.com/baihengaead/wifi-crack-tool
Version: 1.3.0 (Refactored)

优化内容:
- 模块化重构，拆分为 core/ 和 ui/ 模块
- 使用 pathlib 处理路径
- 添加统一日志系统
- 提取常量到独立模块
- 使用 itertools.islice 优化密码读取
- 使用 QWaitCondition 替代忙等待
- 完善类型注解
"""
import sys
import platform
import ctypes
from pathlib import Path

from PySide6.QtWidgets import QApplication
from pywifi import PyWiFi

from ui.main_window import MainWindow
from core.wifi_tool import WifiCrackTool
from core.constants import Colors


def acquire_windows_mutex():
    """
    Acquire Windows mutex for single instance check
    
    :return: Mutex handle or None if already running
    """
    import win32api
    import win32security
    import win32event
    
    MUTEX_NAME = "Global/wifi_crack_tool_mutex"
    
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = False
    mutex = win32event.CreateMutex(sa, False, MUTEX_NAME)
    last_error = win32api.GetLastError()
    
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        return None
    elif last_error != 0:
        raise ctypes.WinError(last_error)
    
    return mutex


def acquire_linux_lock():
    """
    Acquire Linux file lock for single instance check
    
    :return: Lock file descriptor or None if already running
    """
    import os
    import fcntl
    
    LOCKFILE = "/tmp/wifi_crack_tool.lock"
    
    lock = os.open(LOCKFILE, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock
    except IOError:
        return None


def release_linux_lock(lock):
    """
    Release Linux file lock
    
    :param lock: Lock file descriptor
    """
    import os
    import fcntl
    
    LOCKFILE = "/tmp/wifi_crack_tool.lock"
    
    fcntl.flock(lock, fcntl.LOCK_UN)
    os.close(lock)
    os.remove(LOCKFILE)


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    system = platform.system()
    window = None
    mutex_or_lock = None
    
    try:
        if system == 'Windows':
            print('当前系统是 Windows')
            
            # Single instance check for single adapter
            if len(PyWiFi().interfaces()) <= 1:
                mutex_or_lock = acquire_windows_mutex()
            
            window = MainWindow(mutex_or_lock)
            
        elif system == 'Linux':
            print('当前系统是 Linux')
            
            # Single instance check for single adapter
            if len(PyWiFi().interfaces()) <= 1:
                mutex_or_lock = acquire_linux_lock()
            
            window = MainWindow(mutex_or_lock)
            
        elif system == 'Darwin':
            print('当前系统是 macOS, 暂不支持')
            sys.exit()
            
        else:
            print(f'当前系统为 {system}, 暂不支持')
            sys.exit()
        
        # Initialize tool and connect signals
        tool = WifiCrackTool(window)
        window.init_signals(tool)
        window.bind_events(tool)
        
        # Show initialization message
        window.show_msg.send(f"初始化完成！\n", Colors.BLACK)
        
        # Show window and run app
        window.show()
        app.exec()
        
        # Save settings on exit
        tool.save_settings()
        
    finally:
        # Cleanup
        if system == 'Windows' and mutex_or_lock is not None:
            import win32api
            win32api.CloseHandle(mutex_or_lock)
        elif system == 'Linux' and mutex_or_lock is not None:
            release_linux_lock(mutex_or_lock)
    
    sys.exit()


if __name__ == "__main__":
    main()