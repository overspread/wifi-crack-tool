# -*- coding: utf-8 -*-
"""
检查WLAN服务状态的辅助脚本
"""
import subprocess
import sys

def check_wlan_service():
    """检查WLAN AutoConfig服务状态"""
    try:
        # 查询WLAN AutoConfig服务状态
        result = subprocess.run(
            ['sc', 'query', 'WlanSvc'],
            capture_output=True,
            text=True,
            encoding='gbk'
        )
        
        print("=" * 60)
        print("WLAN AutoConfig 服务状态检查")
        print("=" * 60)
        print(result.stdout)
        
        if "RUNNING" in result.stdout:
            print("\n✓ WLAN服务正在运行")
            return True
        elif "STOPPED" in result.stdout:
            print("\n✗ WLAN服务已停止")
            print("\n尝试启动WLAN服务...")
            
            # 尝试启动服务
            start_result = subprocess.run(
                ['sc', 'start', 'WlanSvc'],
                capture_output=True,
                text=True,
                encoding='gbk'
            )
            print(start_result.stdout)
            
            if start_result.returncode == 0:
                print("\n✓ WLAN服务启动成功！")
                return True
            else:
                print("\n✗ WLAN服务启动失败！")
                print("请以管理员身份运行此脚本，或手动启动服务。")
                return False
        else:
            print("\n? 无法确定WLAN服务状态")
            return False
            
    except Exception as e:
        print(f"\n✗ 检查服务时发生错误: {e}")
        return False

def check_network_adapters():
    """检查网络适配器状态"""
    try:
        print("\n" + "=" * 60)
        print("网络适配器状态检查")
        print("=" * 60)
        
        result = subprocess.run(
            ['netsh', 'interface', 'show', 'interface'],
            capture_output=True,
            text=True,
            encoding='gbk'
        )
        
        print(result.stdout)
        
        # 检查WiFi适配器
        if 'Wi-Fi' in result.stdout or 'WLAN' in result.stdout:
            print("\n✓ 找到WiFi适配器")
            
            # 检查WiFi是否已连接或已启用
            if '已连接' in result.stdout or 'Connected' in result.stdout:
                print("✓ WiFi适配器已连接")
            elif '已断开' in result.stdout or 'Disconnected' in result.stdout:
                print("⚠ WiFi适配器已断开连接（但已启用）")
            else:
                print("? WiFi适配器状态未知")
        else:
            print("\n✗ 未找到WiFi适配器")
            
    except Exception as e:
        print(f"\n✗ 检查网络适配器时发生错误: {e}")

if __name__ == "__main__":
    print("正在检查WLAN相关服务和适配器状态...\n")
    
    service_ok = check_wlan_service()
    check_network_adapters()
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)
    
    if not service_ok:
        print("\n建议：")
        print("1. 以管理员身份运行此脚本")
        print("2. 或手动启动WLAN AutoConfig服务：")
        print("   - 按 Win+R，输入 services.msc")
        print("   - 找到 WLAN AutoConfig")
        print("   - 右键点击，选择\"启动\"")
    
    input("\n按回车键退出...")
