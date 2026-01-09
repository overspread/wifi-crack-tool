# -*- coding: utf-8 -*-
"""
Main Window for WiFi Crack Tool
"""
import sys
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QMessageBox
from PySide6.QtGui import QIcon

from wifi_crack_tool_gui import Ui_MainWindow
from .signals import SignThread, QuestionSignal

if TYPE_CHECKING:
    from core.wifi_tool import WifiCrackTool


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, mutex=None):
        """
        Initialize main window
        
        :param mutex: Mutex for single instance check (Windows/Linux specific)
        """
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Setup icon path
        self.icon_path = self._get_icon_path()
        
        # Check for multiple instances
        from pywifi import PyWiFi
        if len(PyWiFi().interfaces()) <= 1 and mutex is None:
            self.showinfo(
                title=self.windowTitle(),
                message='应用程序的另一个实例已经在运行。\n(p.s.你当前的设备只有一个网卡，不支持多开！)'
            )
            sys.exit()
        
        # Set window icon
        icon = QIcon()
        icon.addFile(self.icon_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.setWindowIcon(icon)
        
        # Initialize control states
        self._init_controls()
        
        # Store log cursor position
        self.log_end = self.ui.txt_log_msg_info.textCursor().MoveOperation.End
        self.log_color = self.ui.txt_log_msg_info.textColor()
        
        # Tool will be set later
        self.tool: Optional['WifiCrackTool'] = None
        
        # Signal objects (initialized after tool is set)
        self.show_msg: Optional[SignThread] = None
        self.clear_msg: Optional[SignThread] = None
        self.add_wifi_items: Optional[SignThread] = None
        self.set_wifi_current_index: Optional[SignThread] = None
        self.set_control_state: Optional[SignThread] = None
        self.reset_controls_state: Optional[SignThread] = None
        self.set_controls_running_state: Optional[SignThread] = None
        self.show_info: Optional[SignThread] = None
        self.show_warning: Optional[SignThread] = None
        self.show_error: Optional[SignThread] = None
        self.ask_question: Optional[QuestionSignal] = None
    
    def _get_icon_path(self) -> str:
        """Get the icon path based on frozen state"""
        if getattr(sys, 'frozen', False):
            return str(Path(sys._MEIPASS) / "images" / "wificrack.ico")  # type: ignore
        return "images/wificrack.ico"
    
    def _init_controls(self) -> None:
        """Initialize control states"""
        from core.constants import SecurityTypes
        
        self.ui.cbo_wifi_name.addItem('——全部——')
        self.ui.cbo_security_type.addItems([SecurityTypes.AUTO] + SecurityTypes.TYPES)
        self.ui.cbo_security_type.setCurrentIndex(0)
        
        # Disable controls initially
        self.ui.cbo_wifi_name.setDisabled(True)
        self.ui.cbo_wnic.setDisabled(True)
        self.ui.btn_refresh_wifi.setDisabled(True)
        self.ui.btn_start.setDisabled(True)
        self.ui.btn_pause_or_resume.setDisabled(True)
        self.ui.btn_stop.setDisabled(True)
        
        self.ui.txt_log_msg_info.setReadOnly(True)
    
    def init_signals(self, tool: 'WifiCrackTool') -> None:
        """
        Initialize signal objects after tool is created
        
        :param tool: WifiCrackTool instance
        """
        self.tool = tool
        
        # Create signal objects for thread-safe GUI updates
        self.show_msg = SignThread(self.ui.centralwidget, tool.show_msg, str, str)
        self.clear_msg = SignThread(self.ui.centralwidget, tool.clear_msg)
        self.add_wifi_items = SignThread(self.ui.centralwidget, self.ui.cbo_wifi_name.addItems, list)
        self.set_wifi_current_index = SignThread(self.ui.centralwidget, self.ui.cbo_wifi_name.setCurrentIndex, int)
        self.set_control_state = SignThread(self.ui.centralwidget, self.set_control_enabled, bool, QWidget)
        self.reset_controls_state = SignThread(self.ui.centralwidget, tool.reset_controls_state)
        self.set_controls_running_state = SignThread(self.ui.centralwidget, tool.set_controls_running_state)
        self.show_info = SignThread(self.ui.centralwidget, self.showinfo, str, str)
        self.show_warning = SignThread(self.ui.centralwidget, self.showwarning, str, str)
        self.show_error = SignThread(self.ui.centralwidget, self.showerror, str, str)
        self.ask_question = QuestionSignal(self.ui.centralwidget)
    
    def bind_events(self, tool: 'WifiCrackTool') -> None:
        """
        Bind UI events to tool methods
        
        :param tool: WifiCrackTool instance
        """
        self.ui.btn_change_pwd_file.clicked.connect(tool.change_pwd_file)
        self.ui.btn_refresh_wifi.clicked.connect(tool.refresh_wifi)
        self.ui.btn_start.clicked.connect(tool.start)
        self.ui.btn_pause_or_resume.clicked.connect(tool.pause)
        self.ui.btn_stop.clicked.connect(tool.stop)
        self.ui.dbl_scan_time.valueChanged.connect(tool.change_scan_time)
        self.ui.dbl_connect_time.valueChanged.connect(tool.change_connect_time)
    
    def set_display_using_pwd_file(self, filename: str = "(无)") -> None:
        """
        Update the password file display label
        
        :param filename: Password file name to display
        """
        self.ui.lbl_using_pwd_file.setText(f"正在使用密码本：{filename}")
    
    def set_control_enabled(self, state: bool, *controls: QWidget) -> None:
        """
        Enable or disable multiple controls
        
        :param state: True to enable, False to disable
        :param controls: Control widgets to modify
        """
        for control in controls:
            control.setEnabled(state)
    
    def _show_message_box(
        self, 
        title: str, 
        message: str, 
        icon: QMessageBox.Icon
    ) -> int:
        """
        Show a message box with common settings
        
        :param title: Message box title
        :param message: Message text
        :param icon: Message box icon
        :return: Result of exec()
        """
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(icon)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        return msg_box.exec()
    
    def showinfo(self, title: str, message: str) -> int:
        """
        Show information message box
        
        :param title: Dialog title
        :param message: Dialog message
        :return: Result of exec()
        """
        return self._show_message_box(title, message, QMessageBox.Icon.Information)
    
    def showwarning(self, title: str, message: str) -> int:
        """
        Show warning message box
        
        :param title: Dialog title  
        :param message: Dialog message
        :return: Result of exec()
        """
        return self._show_message_box(title, message, QMessageBox.Icon.Warning)
    
    def showerror(self, title: str, message: str) -> int:
        """
        Show error message box
        
        :param title: Dialog title
        :param message: Dialog message
        :return: Result of exec()
        """
        return self._show_message_box(title, message, QMessageBox.Icon.Critical)
    
    def ask_user_question(self, title: str, message: str) -> int:
        """
        Show question dialog with Yes/No/Cancel options
        
        :param title: Dialog title
        :param message: Dialog message
        :return: User's button choice
        """
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No | 
            QMessageBox.StandardButton.Cancel
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        return msg_box.exec()
