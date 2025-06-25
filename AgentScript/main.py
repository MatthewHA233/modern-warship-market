#!/usr/bin/env python3
"""
现代战舰战斗录制器 - 主启动脚本
支持GUI和终端两种界面模式
"""

import sys
import os
import argparse
from pathlib import Path
from gui_interface import MainWindow
from terminal_interface import TerminalInterface
from pc_replayer import PCReplayer
from mobile_replayer import MobileReplayer
import glob
from PyQt5.QtWidgets import QApplication

def check_dependencies():
    """检查依赖包是否安装"""
    missing_packages = []
    
    try:
        import rich
    except ImportError:
        missing_packages.append("rich")
        
    try:
        import PyQt5
    except ImportError:
        missing_packages.append("PyQt5")
        
    try:
        import keyboard
    except ImportError:
        missing_packages.append("keyboard")
        
    try:
        import cv2
    except ImportError:
        missing_packages.append("opencv-python")
        
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
        result = subprocess.run(['adb', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("ADB检查通过")
            return True
        else:
            print("警告：ADB不可用，请确保已安装Android SDK并添加到PATH")
            return False
    except FileNotFoundError:
        print("错误：未找到ADB命令，请安装Android SDK")
        return False

def show_welcome():
    """显示欢迎信息"""
    welcome_text = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                 现代战舰战斗录制器 v1.0                        ║
    ║                Modern Warship Battle Recorder                ║
    ║                                                              ║
    ║  功能特点：                                                    ║
    ║  • 实时录制游戏操作序列                                        ║
    ║  • 支持多种操作类型（点击、长按、滑动、视角控制）                ║
    ║  • 提供GUI和终端两种界面                                       ║
    ║  • 详细的操作统计和分析                                        ║
    ║  • 支持录制结果的保存和加载                                    ║
    ║                                                              ║
    ║  使用前请确保：                                                ║
    ║  • 安卓设备已连接并启用USB调试                                 ║
    ║  • 已安装ADB工具                                              ║
    ║  • 游戏处于可操作状态                                          ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(welcome_text)

def run_gui():
    """运行GUI界面"""
    try:
        from gui_interface import main as gui_main
        print("启动GUI界面...")
        gui_main()
    except ImportError as e:
        print(f"启动GUI界面失败：{e}")
        print("请确保已安装PyQt5：pip install PyQt5")
        return False
    except Exception as e:
        print(f"GUI界面运行出错：{e}")
        return False
    return True

def run_terminal():
    """运行终端界面"""
    try:
        from terminal_interface import main as terminal_main
        print("启动终端界面...")
        terminal_main()
    except ImportError as e:
        print(f"启动终端界面失败：{e}")
        print("请确保已安装rich：pip install rich")
        return False
    except Exception as e:
        print(f"终端界面运行出错：{e}")
        return False
    return True

def run_pc_replay():
    """运行PC端回放(不可用)器"""
    try:
        from pc_replayer import main as pc_replay_main
        print("启动PC端回放(不可用)器...")
        pc_replay_main()
    except ImportError as e:
        print(f"启动PC端回放(不可用)器失败：{e}")
        return False
    except Exception as e:
        print(f"PC端回放(不可用)器运行出错：{e}")
        return False
    return True

def interactive_mode():
    """交互式模式选择界面"""
    print("\n请选择界面模式：")
    print("1. GUI界面 (推荐) - 图形化操作界面")
    print("2. 终端界面 - 命令行操作界面")
    print("3. PC端回放(不可用)器 - 在PC上回放录制文件")
    print("0. 退出程序")
    
    while True:
        try:
            choice = input("\n请输入选择 (1/2/3/0): ").strip()
            
            if choice == "1":
                return run_gui()
            elif choice == "2":
                return run_terminal()
            elif choice == "3":
                return run_pc_replay()
            elif choice == "0":
                print("感谢使用，再见！")
                return True
            else:
                print("无效选择，请输入 1、2、3 或 0")
                
        except KeyboardInterrupt:
            print("\n程序被中断，退出中...")
            return True
        except Exception as e:
            print(f"输入处理出错：{e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='现代战舰代肝脚本')
    parser.add_argument('--mode', choices=['gui', 'terminal', 'pc-replay', 'mobile-replay'], 
                       default='gui', help='运行模式')
    parser.add_argument('--file', type=str, help='录制文件路径')
    parser.add_argument('--device', type=str, help='设备ID')
    parser.add_argument('--compensation', type=int, default=150, help='长按补偿时间(ms)')
    
    args = parser.parse_args()
    
    if args.mode == 'gui':
        # GUI模式
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
        
    elif args.mode == 'terminal':
        # 终端模式
        interface = TerminalInterface()
        interface.run()
        
    elif args.mode == 'pc-replay':
        # PC端回放模式
        print("PC端回放模式")
        
        # 设置默认目录
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        if args.file and os.path.exists(args.file):
            # 指定了文件路径
            file_path = args.file
        else:
            # 列出文件让用户选择
            pattern = os.path.join(recording_dir, "*.json")
            json_files = glob.glob(pattern)
            
            if not json_files:
                print("未找到录制文件！")
                print(f"请将录制文件(.json)放入: {recording_dir}")
                return
                
            # 按修改时间排序（最新的在前面）
            json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            print("录制文件列表:")
            for i, file_path in enumerate(json_files, 1):
                filename = os.path.basename(file_path)
                file_size = f"{os.path.getsize(file_path) / 1024:.1f}KB"
                print(f"  {i}. {filename} ({file_size})")
            
            choice = input("请输入文件序号: ").strip()
            if choice.isdigit():
                file_index = int(choice) - 1
                if 0 <= file_index < len(json_files):
                    file_path = json_files[file_index]
                else:
                    print("无效的文件序号")
                    return
            else:
                print("无效的选择")
                return
        
        # 创建PC回放器并执行回放
        replayer = PCReplayer()
        if args.device:
            replayer.set_device(args.device)
        replayer.set_long_press_compensation(args.compensation)
        
        print(f"开始PC端回放: {os.path.basename(file_path)}")
        print(f"长按补偿: +{args.compensation}ms")
        print("按ESC键可随时停止回放")
        
        if replayer.load_and_replay(file_path):
            print("PC端回放已开始！")
        else:
            print("PC端回放启动失败")
            
    elif args.mode == 'mobile-replay':
        # 手机端回放模式
        print("手机端回放模式")
        
        # 设置默认目录
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        if args.file and os.path.exists(args.file):
            # 指定了文件路径
            file_path = args.file
        else:
            # 列出文件让用户选择
            pattern = os.path.join(recording_dir, "*.json")
            json_files = glob.glob(pattern)
            
            if not json_files:
                print("未找到录制文件！")
                print(f"请将录制文件(.json)放入: {recording_dir}")
                return
                
            # 按修改时间排序（最新的在前面）
            json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            print("录制文件列表:")
            for i, file_path in enumerate(json_files, 1):
                filename = os.path.basename(file_path)
                file_size = f"{os.path.getsize(file_path) / 1024:.1f}KB"
                print(f"  {i}. {filename} ({file_size})")
            
            choice = input("请输入文件序号: ").strip()
            if choice.isdigit():
                file_index = int(choice) - 1
                if 0 <= file_index < len(json_files):
                    file_path = json_files[file_index]
                else:
                    print("无效的文件序号")
                    return
            else:
                print("无效的选择")
                return
        
        # 创建手机端回放器
        replayer = MobileReplayer()
        
        # 设置设备
        if args.device:
            replayer.set_device(args.device)
        else:
            # 获取设备列表
            devices = replayer.get_available_devices()
            if not devices:
                print("未找到连接的设备！")
                print("请确保设备已连接并启用USB调试")
                return
            elif len(devices) == 1:
                replayer.set_device(devices[0])
                print(f"自动选择设备: {devices[0]}")
            else:
                print("可用设备:")
                for i, device in enumerate(devices, 1):
                    print(f"  {i}. {device}")
                
                choice = input("请选择设备序号: ").strip()
                if choice.isdigit():
                    device_index = int(choice) - 1
                    if 0 <= device_index < len(devices):
                        replayer.set_device(devices[device_index])
                    else:
                        print("无效的设备序号")
                        return
                else:
                    print("无效的选择")
                    return
        
        # 设置长按补偿
        replayer.set_long_press_compensation(args.compensation)
        
        print(f"开始手机端回放: {os.path.basename(file_path)}")
        print(f"目标设备: {replayer.device_id}")
        print(f"长按补偿: +{args.compensation}ms")
        print("按Ctrl+C可随时停止回放")
        
        try:
            if replayer.load_and_replay(file_path):
                print("手机端回放已开始！")
                # 保持程序运行直到用户停止
                while replayer.is_replaying():
                    import time
                    time.sleep(1)
                print("回放完成")
            else:
                print("手机端回放启动失败")
        except KeyboardInterrupt:
            replayer.stop_replay()
            print("\n回放已停止")

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序被中断，退出中...")
        sys.exit(0)
    except Exception as e:
        print(f"程序运行出错：{e}")
        sys.exit(1) 