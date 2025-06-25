#!/usr/bin/env python3
"""
现代战舰代肝脚本 - 启动器
快速启动脚本，检查依赖并启动主程序
"""

import sys
import os

# 获取脚本所在目录作为基础路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def check_dependencies():
    """检查依赖包是否安装"""
    missing_packages = []
    
    # 检查基础依赖
    try:
        import PyQt5
    except ImportError:
        missing_packages.append("PyQt5")
        
    try:
        import cv2
    except ImportError:
        missing_packages.append("opencv-python")
        
    try:
        import numpy
    except ImportError:
        missing_packages.append("numpy")
        
    if missing_packages:
        print("错误：缺少以下依赖包：")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n请运行以下命令安装依赖：")
        print(f"pip install {' '.join(missing_packages)}")
        return False
        
    return True

def check_adb():
    """检查ADB是否可用"""
    import subprocess
    try:
        result = subprocess.run(['adb', 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("ADB检查通过")
            return True
        else:
            print("警告：ADB不可用，请确保已安装Android SDK并添加到PATH")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("错误：未找到ADB命令，请安装Android SDK")
        return False

def check_templates():
    """检查模板文件是否存在"""
    required_templates = ["main_page.png", "fighting.png", "fangshou.png", "no_vip.png", "shengli.png"]
    templates_dir = os.path.join(SCRIPT_DIR, "templates")
    
    missing_templates = []
    for template in required_templates:
        template_path = os.path.join(templates_dir, template)
        if not os.path.exists(template_path):
            missing_templates.append(template)
    
    if missing_templates:
        print("警告：缺少以下模板文件：")
        for template in missing_templates:
            print(f"  - templates/{template}")
        print("\n脚本可能无法正常识别游戏状态")
        print(f"模板目录: {templates_dir}")
        return False
    
    print("模板文件检查通过")
    print(f"模板目录: {templates_dir}")
    return True

def check_recording_files():
    """检查回放文件是否存在"""
    recording_dir = os.path.join(SCRIPT_DIR, "recording")
    
    if not os.path.exists(recording_dir):
        print(f"回放目录不存在，将创建: {recording_dir}")
        os.makedirs(recording_dir, exist_ok=True)
        return False
    
    # 查找JSON文件
    import glob
    pattern = os.path.join(recording_dir, "*.json")
    json_files = glob.glob(pattern)
    
    if json_files:
        print(f"找到 {len(json_files)} 个回放文件:")
        for file_path in json_files[:3]:  # 只显示前3个
            filename = os.path.basename(file_path)
            print(f"  - {filename}")
        if len(json_files) > 3:
            print(f"  ... 还有 {len(json_files) - 3} 个文件")
    else:
        print("警告：未找到回放文件")
        print("请先使用录制功能创建回放文件")
    
    print(f"回放目录: {recording_dir}")
    return len(json_files) > 0

def main():
    """主函数"""
    print("=" * 50)
    print("    现代战舰代肝脚本 - 启动器")
    print("=" * 50)
    print(f"脚本目录: {SCRIPT_DIR}")
    
    # 检查依赖
    print("\n1. 检查Python依赖...")
    if not check_dependencies():
        input("按回车键退出...")
        return
    
    # 检查ADB
    print("\n2. 检查ADB...")
    adb_ok = check_adb()
    
    # 检查模板文件
    print("\n3. 检查模板文件...")
    templates_ok = check_templates()
    
    # 检查回放文件
    print("\n4. 检查回放文件...")
    recording_ok = check_recording_files()
    
    # 检查设备连接
    print("\n5. 检查设备连接...")
    try:
        # 将脚本目录添加到Python路径
        sys.path.insert(0, SCRIPT_DIR)
        import ADBHelper
        
        devices = ADBHelper.getDevicesList()
        if devices:
            print(f"找到 {len(devices)} 个连接的设备:")
            for device in devices:
                print(f"  - {device}")
        else:
            print("警告：未找到连接的设备")
            print("请确保：")
            print("  - USB调试已开启")
            print("  - 设备已连接到电脑")
            print("  - 已信任此电脑")
    except Exception as e:
        print(f"检查设备连接失败: {str(e)}")
    
    print("\n" + "=" * 50)
    
    # 汇总检查结果
    issues = []
    if not adb_ok:
        issues.append("ADB不可用")
    if not templates_ok:
        issues.append("缺少模板文件")
    if not recording_ok:
        issues.append("缺少回放文件")
    
    if issues:
        print("发现以下问题：")
        for issue in issues:
            print(f"  - {issue}")
        print()
        
        if not adb_ok:
            print("警告：ADB不可用，脚本无法控制设备")
            choice = input("是否仍要继续？(y/n): ").lower()
            if choice not in ['y', 'yes']:
                return
    
    # 启动主程序
    print("启动现代战舰代肝脚本...")
    try:
        # 确保能找到主程序
        main_script = os.path.join(SCRIPT_DIR, "warship_auto_battle.py")
        if not os.path.exists(main_script):
            print(f"错误：未找到主程序文件: {main_script}")
            input("按回车键退出...")
            return
        
        # 将脚本目录添加到Python路径
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        
        from warship_auto_battle import main as battle_main
        battle_main()
    except ImportError as e:
        print(f"导入主程序失败: {str(e)}")
        print("请确保 warship_auto_battle.py 文件存在且没有语法错误")
        input("按回车键退出...")
    except Exception as e:
        print(f"启动主程序失败: {str(e)}")
        input("按回车键退出...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n启动器出错: {str(e)}")
        input("按回车键退出...") 