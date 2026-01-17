# -*- coding: utf-8 -*-
"""
WiFi Crack Tool - Core functionality with async support
"""
import os
import datetime
import threading
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox

from .constants import Colors, Messages, Defaults
from .config import ConfigManager
from .logger import get_logger, setup_logger
from .crack_async import AsyncCrack
from .async_runner import CancellableTask

if TYPE_CHECKING:
    from ui.main_window import MainWindow


class WifiCrackTool:
    """Main WiFi crack tool controller with async support"""
    
    def __init__(self, win: 'MainWindow'):
        """
        Initialize WiFi Crack Tool
        
        :param win: Main window instance
        """
        self.win = win
        self.ui = win.ui
        
        # Initialize configuration
        self.config = ConfigManager()
        
        # Setup logger
        self.logger = setup_logger(self.config.log_dir)
        
        # Apply saved settings to UI
        self.ui.dbl_scan_time.setValue(self.config.scan_time)
        self.ui.dbl_connect_time.setValue(self.config.connect_time)
        
        # Threading controls (for sync compatibility)
        self.crack_pause_condition = threading.Condition()
        self.paused = False
        self.run = False
        self.pwd_file_changed = False
        
        # Create async crack instance
        self.crack = AsyncCrack(self)
        
        # Async task management
        self._current_task: Optional[CancellableTask] = None
        
        # Update password file display
        pwd_display = self.config.pwd_txt_name if self.config.pwd_file_exists() else Messages.NO_PWD_FILE
        self.win.set_display_using_pwd_file(pwd_display)
        
        # Apply advanced settings to UI (will be called after UI is fully initialized)
        self._apply_advanced_settings()
    
    def _apply_advanced_settings(self) -> None:
        """Apply saved advanced settings to UI controls"""
        try:
            if hasattr(self.ui, 'spn_check_interval'):
                self.ui.spn_check_interval.setValue(self.config.wifi_check_interval)
            if hasattr(self.ui, 'spn_rollback'):
                self.ui.spn_rollback.setValue(self.config.wifi_rollback)
            if hasattr(self.ui, 'spn_max_retries'):
                self.ui.spn_max_retries.setValue(self.config.max_retries)
        except Exception as e:
            self.logger.debug(f"应用高级设置时出错: {e}")
    
    # ======================== Async Task Management ========================
    
    def _start_async_task(self, coro) -> None:
        """
        Start an async task
        
        :param coro: Coroutine to run
        """
        if self._current_task is None:
            self._current_task = CancellableTask()
        
        self._current_task.start(coro)
    
    def _cancel_current_task(self) -> None:
        """Cancel the current async task if running"""
        if self._current_task is not None:
            self._current_task.cancel()
            self.async_crack.cancel()
    
    # ======================== Settings ========================
    
    def change_scan_time(self) -> None:
        """Handle scan time change"""
        value = self.ui.dbl_scan_time.value()
        self.config.scan_time = value
        self.config.save_settings()
        self.win.show_msg.send(Messages.SCAN_TIME_SET.format(time=value), Colors.BLUE)
    
    def change_connect_time(self) -> None:
        """Handle connect time change"""
        value = self.ui.dbl_connect_time.value()
        self.config.connect_time = value
        self.config.save_settings()
        self.win.show_msg.send(Messages.CONNECT_TIME_SET.format(time=value), Colors.BLUE)
    
    def change_check_interval(self) -> None:
        """Handle WiFi check interval change"""
        value = self.ui.spn_check_interval.value()
        self.config.wifi_check_interval = value
        self.config.save_settings()
        self.show_msg(f"WiFi检测间隔已设置为每 {value} 次\n", Colors.BLUE)
    
    def change_rollback(self) -> None:
        """Handle WiFi rollback count change"""
        value = self.ui.spn_rollback.value()
        self.config.wifi_rollback = value
        self.config.save_settings()
        self.show_msg(f"WiFi不可用回退次数已设置为 {value} 次\n", Colors.BLUE)
    
    def change_max_retries(self) -> None:
        """Handle max retries change"""
        value = self.ui.spn_max_retries.value()
        self.config.max_retries = value
        self.config.save_settings()
        self.show_msg(f"连接重试次数已设置为 {value} 次\n", Colors.BLUE)
    
    # ======================== Password File ========================
    
    def change_pwd_file(self) -> bool:
        """
        Open file dialog to select password file
        
        :return: True if file was selected successfully
        """
        try:
            default_dir = "."
            file_path, _ = QFileDialog.getOpenFileName(
                self.win,
                caption='选择密码本',
                dir=os.path.expanduser(default_dir),
                filter="Text files (*.txt)"
            )
            
            if not file_path:
                self.win.showinfo(title='提示', message='未选择密码本')
                self.pwd_file_changed = True
                self.config.pwd_txt_path = ""
                self.win.set_display_using_pwd_file(Messages.NO_PWD_FILE)
                return False
            
            file_path_obj = Path(file_path)
            file_ext = file_path_obj.suffix.lower()
            
            if file_ext != '.txt':
                self.win.showerror(
                    title='选择密码本',
                    message=f'密码本类型错误！\n目前仅支持格式为[txt]的密码本\n您选择的密码本格式为[{file_ext}]'
                )
                self.pwd_file_changed = False
                return False
            
            self.config.pwd_txt_path = file_path
            self.win.set_display_using_pwd_file(file_path_obj.name)
            self.pwd_file_changed = True
            return True
            
        except Exception as e:
            self.logger.error(f"选择密码本时发生错误: {e}")
            self.win.showerror(title='错误警告', message=f'选择密码本时发生未知错误 {e}')
            return False
    
    # ======================== Logging ========================
    
    def show_msg(self, msg: str, color: str = Colors.BLACK) -> None:
        """
        Display log message in GUI and write to file
        
        :param msg: Message text
        :param color: Message color
        """
        dt = datetime.datetime.now()
        timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Write to log file
        log_file = self.config.log_dir / f"wifi_crack_log_{dt.strftime('%Y%m%d')}.txt"
        try:
            with open(log_file, "a", encoding='utf-8') as log:
                log.write(f"{timestamp} >> {msg}")
        except IOError as e:
            self.logger.warning(f"Failed to write log: {e}")
        
        # Update GUI
        self.ui.txt_log_msg_info.moveCursor(self.win.log_end)
        html_msg = msg.replace('\n', '<br/>')
        self.ui.txt_log_msg_info.insertHtml(
            f"<span style='color:{color};'>{timestamp} >> {html_msg}</span><br/>"
        )
        self.ui.txt_log_msg_info.moveCursor(self.win.log_end)
    
    def clear_msg(self) -> None:
        """Clear log messages"""
        self.ui.txt_log_msg_info.setPlainText("")
    
    # ======================== Control States ========================
    
    def reset_controls_state(self) -> None:
        """Reset all controls to default state"""
        try:
            self.ui.cbo_wifi_name.setEnabled(True)
            self.ui.cbo_security_type.setEnabled(True)
            self.ui.cbo_wnic.setEnabled(True)
            self.ui.dbl_scan_time.setEnabled(True)
            self.ui.dbl_connect_time.setEnabled(True)
            self.ui.btn_change_pwd_file.setEnabled(True)
            self.ui.btn_refresh_wifi.setEnabled(True)
            self.ui.btn_start.setEnabled(True)
            self.ui.btn_pause_or_resume.setDisabled(True)
            self.ui.btn_stop.setDisabled(True)
            self.ui.btn_pause_or_resume.setText("暂停")
            
            with self.crack_pause_condition:
                self.paused = False
                self.crack_pause_condition.notify_all()
        except Exception as e:
            self.logger.debug(f"重置控件状态时出错: {e}")
    
    def set_controls_running_state(self) -> None:
        """Set controls to running state"""
        self.ui.cbo_wifi_name.setDisabled(True)
        self.ui.cbo_security_type.setDisabled(True)
        self.ui.cbo_wnic.setDisabled(True)
        self.ui.dbl_scan_time.setDisabled(True)
        self.ui.dbl_connect_time.setDisabled(True)
        self.ui.btn_change_pwd_file.setDisabled(True)
        self.ui.btn_refresh_wifi.setDisabled(True)
        self.ui.btn_start.setDisabled(True)
        self.ui.btn_pause_or_resume.setEnabled(True)
        self.ui.btn_stop.setEnabled(True)
    
    # ======================== WiFi Operations ========================
    
    def refresh_wifi(self) -> None:
        """Refresh WiFi list (async version)"""
        try:
            self.ui.cbo_wifi_name.clear()
            self.ui.cbo_wifi_name.addItem('——全部——')
            self.ui.cbo_wifi_name.setDisabled(True)
            self.ui.btn_refresh_wifi.setDisabled(True)
            self.ui.btn_start.setDisabled(True)
            self.ui.cbo_wnic.setDisabled(True)
            self.ui.dbl_scan_time.setDisabled(True)
            
            # Check for wireless adapters
            from pywifi import PyWiFi
            wifi = PyWiFi()
            wnics = wifi.interfaces()
            
            if not wnics or len(wnics) == 0:
                self.win.show_warning.send(title='警告', message=Messages.NO_WNIC_FOUND)
                self.show_msg(f'[警告]{Messages.NO_WNIC_FOUND}\n\n', Colors.ORANGE)
                self.reset_controls_state()
                return
            
            # Use async version
            self._start_async_task(self.crack.search_wifi())
            
        except Exception as e:
            self.logger.error(f"扫描wifi时发生错误: {e}")
            self.win.showerror(title='错误警告', message=f'扫描wifi时发生未知错误 {e}')
            self.show_msg(f'[错误]扫描wifi时发生未知错误 {e}\n\n', Colors.RED)
            self.reset_controls_state()
    
    # ======================== Crack Operations ========================
    
    def start(self) -> None:
        """Start cracking process (async version)"""
        try:
            # Check password file
            if not self.config.pwd_file_exists():
                reply = self.win.ask_question.send('密码本缺失', '未找到密码本，是否选择密码本文件？')
                
                if reply == QMessageBox.StandardButton.Yes:
                    if not self.change_pwd_file():
                        return
                else:
                    self.win.show_warning.send(title='警告', message='未选择密码本，将无法进行破解！')
                    return
            
            wifi_name = self.ui.cbo_wifi_name.currentText()
            self.run = True
            self.set_controls_running_state()
            
            # Check for resume information
            resume_info = self.config.resume_info
            pwd_file = self.config.pwd_txt_path
            
            if (not self.pwd_file_changed and 
                wifi_name in resume_info and 
                resume_info[wifi_name]['pwd_file'] == pwd_file):
                
                resume_position = resume_info[wifi_name]['position']
                reply = self.win.ask_question.send(
                    '断点续传',
                    f'发现上次破解 [{wifi_name}] 时在密码本第 {resume_position} 行中断，是否从该位置继续？\n\n选择"是"从断点继续，选择"否"从头开始。'
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._start_crack(wifi_name, resume_position)
                    self.pwd_file_changed = False
                    return
                elif reply == QMessageBox.StandardButton.Cancel:
                    self.run = False
                    self.reset_controls_state()
                    self.pwd_file_changed = False
                    return
            
            # Check for password file change for specific WiFi
            if (wifi_name in resume_info and 
                self.ui.cbo_wifi_name.currentIndex() != 0 and 
                resume_info[wifi_name]['pwd_file'] != pwd_file):
                
                reply = self.win.ask_question.send(
                    '密码本变更',
                    f'检测到 [{wifi_name}] 使用的密码本已变更，是否清除之前的断点记录？\n\n选择"是"清除断点并从头开始，选择"否"保留断点信息。'
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.config.clear_resume_info(wifi_name)
            
            # Handle batch crack with resume
            if self.ui.cbo_wifi_name.currentIndex() == 0:
                self._handle_batch_crack_resume()
            else:
                self._start_crack(wifi_name)
            
            self.pwd_file_changed = False
            
        except Exception as e:
            self.logger.error(f"开始运行时发生错误: {e}")
            self.win.showerror(title='错误警告', message=f'开始运行时发生未知错误 {e}')
            self.show_msg(f'[错误]开始运行时发生未知错误 {e}\n\n', Colors.RED)
            self.reset_controls_state()
    
    def _handle_batch_crack_resume(self) -> None:
        """Handle batch crack with resume information"""
        resume_info = self.config.resume_info
        pwd_file = self.config.pwd_txt_path
        
        ssids = self.crack.ssids
        
        # Collect WiFis with resume info
        resume_wifis = []
        for ssid in ssids:
            if (not self.pwd_file_changed and 
                ssid in resume_info and 
                resume_info[ssid]['pwd_file'] == pwd_file):
                resume_wifis.append((ssid, resume_info[ssid]['position']))
        
        if resume_wifis:
            wifi_list = '\n'.join([f'{ssid} (位置: {pos})' for ssid, pos in resume_wifis])
            reply = self.win.ask_question.send(
                '批量断点续传',
                f'发现以下 {len(resume_wifis)} 个WiFi有断点信息:\n{wifi_list}\n\n是否对所有WiFi都从断点继续？\n\n选择"是"对所有WiFi从断点继续，选择"否"全部从头开始。'
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._start_auto_crack(-1)
                return
            elif reply == QMessageBox.StandardButton.Cancel:
                self.run = False
                self.reset_controls_state()
                return
        
        self._start_auto_crack(0)
    
    def _start_crack(self, wifi_name: str, start_position: int = 0) -> None:
        """
        Start crack operation (async or sync based on mode)
        
        :param wifi_name: WiFi name to crack
        :param start_position: Starting position for resume
        """
        if self.ui.cbo_wifi_name.currentIndex() == 0:
            self._start_auto_crack(start_position)
        else:
            self._start_async_task(self.crack.crack(wifi_name, start_position))
    
    def _start_auto_crack(self, start_position: int = 0) -> None:
        """
        Start auto crack operation
        
        :param start_position: Starting position for resume
        """
        self._start_async_task(self.crack.auto_crack(start_position))
    
    def pause(self) -> None:
        """Pause or resume cracking"""
        try:
            with self.crack_pause_condition:
                if self.paused:
                    self.paused = False
                    self.ui.btn_pause_or_resume.setText("暂停")
                    self.show_msg("开始继续破解...")
                    self.crack_pause_condition.notify_all()
                else:
                    self.paused = True
                    self.ui.btn_pause_or_resume.setText("继续")
                    self.show_msg("正在尝试暂停破解...")
                    self.crack_pause_condition.notify_all()
        except Exception as e:
            self.logger.error(f"暂停过程中发生错误: {e}")
            self.win.showerror(title='错误警告', message=f'暂停过程中发生未知错误 {e}')
            self.show_msg(f'[错误]暂停过程中发生未知错误 {e}\n\n', Colors.RED)
            self.reset_controls_state()
    
    def stop(self) -> None:
        """Stop cracking process"""
        try:
            self.run = False
            self.show_msg("正在尝试终止破解...")
            
            # Cancel async task if running
            self._cancel_current_task()
            
            # Save resume info
            if hasattr(self.crack, 'current_ssid') and hasattr(self.crack, 'current_position'):
                self.config.save_resume_info(
                    self.crack.current_ssid,
                    'txt',
                    self.config.pwd_txt_path,
                    self.crack.current_position
                )
            
            with self.crack_pause_condition:
                self.paused = False
                self.crack_pause_condition.notify_all()
                
        except Exception as e:
            self.logger.error(f"停止过程中发生错误: {e}")
            self.win.showerror(title='错误警告', message=f'停止过程中发生未知错误 {e}')
            self.show_msg(f'[错误]停止过程中发生未知错误 {e}\n\n', Colors.RED)
            self.reset_controls_state()
    
    def save_settings(self) -> None:
        """Save current settings to file"""
        self.config.save_settings()
