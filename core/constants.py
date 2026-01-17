# -*- coding: utf-8 -*-
"""
Constants for WiFi Crack Tool
"""


class Colors:
    """Color constants for log messages"""
    BLACK = "black"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    ORANGE = "orange"


class Messages:
    """Message text constants"""
    # Initialization
    INIT_COMPLETE = "初始化完成！\n"
    
    # Connection
    DISCONNECT_SUCCESS = "现有连接断开成功！\n\n"
    DISCONNECT_FAILED = "[错误]现有连接断开失败！\n\n"
    DISCONNECTING = "正在断开现有连接...\n"
    
    # Scan
    SCAN_COMPLETE = "扫描完成！\n"
    SCANNING_WIFI = "正在使用网卡[{name}]扫描WiFi...\n"
    NO_WNIC_FOUND = "未找到任何无线网卡！\n请确保你的电脑拥有无线网卡再继续使用。"
    WNIC_FOUND = "已搜索到无线网卡（数量:{count}）\n"
    
    # Crack
    CRACK_TERMINATED = "破解已终止.\n"
    CRACK_PAUSED = "破解已暂停.\n"
    CRACK_SUCCESS = "连接成功，密码：{pwd}\n\n"
    CRACK_FAILED = "所有连接尝试失败，密码是{pwd}\n\n"
    CRACK_COMPLETE = "破解失败，已尝试完密码本中所有可能的密码"
    AUTO_CRACK_START = "开始自动破解已扫描到的所有WiFi\n"
    AUTO_CRACK_COMPLETE = "自动破解已完成！\n"
    ALL_CRACKED = "所有WiFi都已破解成功，无需再次破解\n"
    
    # Resume
    RESUME_FROM = "从第 {position} 行开始继续破解...\n"
    
    # Password file
    NO_PWD_FILE = "(无)"
    PWD_FILE_LABEL = "正在使用密码本：{filename}"
    
    # Settings
    SCAN_TIME_SET = "扫描间隔时间已设置为 {time} 秒\n"
    CONNECT_TIME_SET = "连接间隔时间已设置为 {time} 秒\n"


class Defaults:
    """Default configuration values"""
    SCAN_TIME = 8.0
    CONNECT_TIME = 3.0
    PWD_TXT_PATH = "passwords.txt"
    CONNECT_TIMEOUT = 1.0
    CHECK_INTERVAL = 0.05
    MAX_RETRIES = 3  # 重试次数，用于网络问题
    AUTH_FAIL_THRESHOLD = 0.8  # 认证失败判定阈值（秒）
    
    # WiFi 可用性检测配置
    WIFI_CHECK_INTERVAL = 10  # 每N次密码尝试检测一次WiFi可用性
    WIFI_SCAN_WAIT_TIME = 4.0  # 扫描等待时间（秒）
    WIFI_SCAN_RETRY_WAIT = 1.0  # 扫描重试等待时间（秒）
    WIFI_DISCONNECT_WAIT = 0.5  # 断开连接等待时间（秒）
    WIFI_CHECK_RETRY_COUNT = 2  # WiFi可用性检测扫描次数
    WIFI_UNAVAILABLE_ROLLBACK = 11  # WiFi不可用时回退的密码数
    
    # 连接检测配置
    CHECK_INTERVAL_FAST = 0.03  # 连接中时快速检测间隔（秒）
    CHECK_INTERVAL_SLOW = 0.08  # 等待时慢速检测间隔（秒）
    DISCONNECT_WAIT_TIMEOUT = 1.0  # 断开连接等待超时（秒）
    DISCONNECT_CHECK_INTERVAL = 0.05  # 断开连接检测间隔（秒）
    POST_FAIL_WAIT = 0.1  # 连接失败后等待时间（秒）
    
    # 密码验证配置
    MIN_PASSWORD_LENGTH = 8  # WiFi密码最小长度
    MAX_PASSWORD_LENGTH = 63  # WiFi密码最大长度
    
    # Directory names
    CONFIG_DIR = "config"
    LOG_DIR = "log"
    DICT_DIR = "dict"
    
    # File names
    SETTINGS_FILE = "settings.json"
    RESUME_FILE = "resume.json"
    PWD_DICT_FILE = "pwdict.json"


class SecurityTypes:
    """WiFi security types"""
    AUTO = "——自动——"
    TYPES = ['WPA', 'WPAPSK', 'WPA2', 'WPA2PSK', 'WPA3', 'WPA3SAE', 'OPEN']
