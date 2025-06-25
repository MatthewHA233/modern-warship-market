"""
PC端回放(不可用)器 - 在PC上回放录制的按键操作
"""

import json
import time
import threading
import keyboard
import ctypes
import ctypes.wintypes
from game_config import *

# Windows API常量
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# 虚拟键码映射
VK_CODE = {
    'w': 0x57,
    'a': 0x41, 
    's': 0x53,
    'd': 0x44,
    'z': 0x5A,
    'x': 0x58,
    'q': 0x51,
    'e': 0x45,
    '1': 0x31,
    '2': 0x32,
    '3': 0x33,
    '4': 0x34,
    'up': 0x26,      # VK_UP
    'down': 0x28,    # VK_DOWN
    'left': 0x25,    # VK_LEFT
    'right': 0x27,   # VK_RIGHT
}

class PCReplayer:
    """PC端回放(不可用)器类"""
    
    def __init__(self):
        self.replaying = False
        self.replay_thread = None
        
        # 初始化Windows API
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        
    def load_and_replay(self, recording_file: str):
        """加载并回放录制文件"""
        try:
            # 加载录制文件
            with open(recording_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            actions = data.get('actions', [])
            if not actions:
                print("录制文件中没有动作数据")
                return False
            
            print(f"开始回放录制文件: {recording_file}")
            print(f"共 {len(actions)} 个动作")
            print("按 ESC 键可以随时停止回放")
            
            # 启动回放线程
            self.replay_thread = threading.Thread(
                target=self._replay_actions, 
                args=(actions,), 
                daemon=True
            )
            self.replaying = True
            self.replay_thread.start()
            
            return True
            
        except Exception as e:
            print(f"加载录制文件失败: {str(e)}")
            return False
    
    def _replay_actions(self, actions):
        """回放动作序列"""
        try:
            print("回放开始，1秒后开始执行...")
            
            # 尝试激活游戏窗口
            print("正在查找并激活游戏窗口...")
            if not self.activate_game_window():
                print("警告: 未能自动激活游戏窗口，请手动切换到游戏")
            
            time.sleep(1)  # 给用户准备时间
            
            start_time = time.time()
            active_threads = []  # 跟踪所有活动线程
            
            # 为每个动作创建独立的执行线程，避免累积延迟
            for action in actions:
                if not self.replaying:
                    break
                    
                # 为每个动作安排独立的执行时间
                thread = self._schedule_action(action, start_time)
                active_threads.append(thread)
            
            print(f"所有动作已安排执行，共 {len(active_threads)} 个线程")
            
            # 等待所有线程完成或用户停止
            while self.replaying and active_threads:
                # 移除已完成的线程
                active_threads = [t for t in active_threads if t.is_alive()]
                time.sleep(0.1)  # 100ms检查间隔
                
            if active_threads:
                print("回放被用户停止")
            else:
                print("所有动作执行完成")
            
        except Exception as e:
            print(f"回放执行出错: {str(e)}")
        finally:
            self.replaying = False
    
    def _schedule_action(self, action, start_time):
        """为单个动作安排执行时间，返回线程对象"""
        def execute_action():
            try:
                # 等待到指定时间点
                target_time = action.get('timestamp', 0)
                if target_time > 0:
                    time.sleep(target_time)
                
                if not self.replaying:
                    return
                    
                # 执行动作
                self._execute_action(action)
                
            except Exception as e:
                print(f"执行动作失败: {str(e)}")
        
        # 启动独立的执行线程
        thread = threading.Thread(target=execute_action, daemon=True)
        thread.start()
        return thread  # 返回线程对象用于跟踪
    
    def _execute_action(self, action):
        """执行单个动作"""
        try:
            action_type = action.get('type')
            key = action.get('key', '')
            
            if action_type == 'tap':
                # 点按动作
                duration = action.get('duration', 50)
                self._simulate_key_press(key, duration)
                
            elif action_type == 'long_press':
                # 长按动作
                duration = action.get('duration', 500)
                self._simulate_key_press(key, duration)
                
            elif action_type == 'view_control':
                # 视角控制
                direction = action.get('direction', '')
                if direction.startswith('view_'):
                    arrow_key = direction.replace('view_', '')
                    self._simulate_key_press(arrow_key, 100)
                    
            print(f"执行动作: {action_type} - {key}")
            
        except Exception as e:
            print(f"执行动作出错: {str(e)}")
    
    def _simulate_key_press(self, key_name: str, duration: int):
        """模拟按键操作"""
        try:
            if not key_name or not self.replaying:
                return
                
            # 获取虚拟键码
            vk_code = VK_CODE.get(key_name.lower())
            
            if vk_code:
                # 方法1：使用Windows API (推荐，适用于游戏)
                success = self._send_key_with_windows_api(key_name, duration, vk_code)
                if success:
                    return
                    
            # 方法2：使用keyboard库 (备用方案)
            self._send_key_with_keyboard_lib(key_name, duration)
                
        except Exception as e:
            print(f"模拟按键失败: {str(e)}")
    
    def _send_key_with_windows_api(self, key_name: str, duration: int, vk_code: int):
        """使用Windows API发送按键"""
        try:
            if duration <= 100:
                # 短按
                self._send_key_windows(vk_code, True)   # 按下
                time.sleep(0.05)  # 50ms持续时间
                self._send_key_windows(vk_code, False)  # 释放
                print(f"Windows API短按: {key_name}")
            else:
                # 长按
                self._send_key_windows(vk_code, True)   # 按下
                time.sleep(duration / 1000.0)          # 持续指定时间
                self._send_key_windows(vk_code, False)  # 释放
                print(f"Windows API长按: {key_name}, 持续 {duration}ms")
            return True
        except Exception as e:
            print(f"Windows API按键失败: {str(e)}")
            return False
    
    def _send_key_with_keyboard_lib(self, key_name: str, duration: int):
        """使用keyboard库发送按键 (备用方案)"""
        try:
            # 转换为keyboard库支持的按键名
            if key_name in ['up', 'down', 'left', 'right']:
                keyboard_key = key_name
            else:
                keyboard_key = key_name.lower()
            
            if duration <= 100:
                # 短按
                keyboard.press_and_release(keyboard_key)
                print(f"keyboard库短按: {keyboard_key}")
            else:
                # 长按
                keyboard.press(keyboard_key)
                time.sleep(duration / 1000.0)
                keyboard.release(keyboard_key)
                print(f"keyboard库长按: {keyboard_key}, 持续 {duration}ms")
                
        except Exception as e:
            print(f"keyboard库按键失败: {str(e)}")
    
    def stop_replay(self):
        """停止回放"""
        self.replaying = False
        if self.replay_thread and self.replay_thread.is_alive():
            print("正在停止回放...")
            # 等待线程结束
            self.replay_thread.join(timeout=1)
        print("回放已停止")
    
    def is_replaying(self):
        """检查是否正在回放"""
        return self.replaying

    def _send_key_windows(self, vk_code, press=True):
        """使用Windows API发送按键事件"""
        try:
            if press:
                # 按下按键
                self.user32.keybd_event(vk_code, 0, 0, 0)
            else:
                # 释放按键
                self.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            print(f"Windows API按键发送失败: {str(e)}")
            return False

    def find_game_window(self, window_title_keywords=None):
        """查找游戏窗口"""
        try:
            if window_title_keywords is None:
                window_title_keywords = ["Warship", "Modern", "game"]
            
            def enum_windows_callback(hwnd, windows):
                if self.user32.IsWindowVisible(hwnd):
                    length = self.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        self.user32.GetWindowTextW(hwnd, buffer, length + 1)
                        title = buffer.value
                        windows.append((hwnd, title))
                return True
            
            windows = []
            self.user32.EnumWindows(enum_windows_callback, windows)
            
            # 查找包含关键词的窗口
            for hwnd, title in windows:
                for keyword in window_title_keywords:
                    if keyword.lower() in title.lower():
                        print(f"找到游戏窗口: {title}")
                        return hwnd, title
            
            return None, None
            
        except Exception as e:
            print(f"查找游戏窗口失败: {str(e)}")
            return None, None
    
    def activate_game_window(self, hwnd=None):
        """激活游戏窗口"""
        try:
            if hwnd is None:
                hwnd, title = self.find_game_window()
                if hwnd is None:
                    print("未找到游戏窗口，请手动切换到游戏窗口")
                    return False
            
            # 激活窗口
            self.user32.SetForegroundWindow(hwnd)
            self.user32.SetFocus(hwnd)
            time.sleep(0.5)  # 等待窗口激活
            print("游戏窗口已激活")
            return True
            
        except Exception as e:
            print(f"激活游戏窗口失败: {str(e)}")
            return False
    
    def test_key_input(self):
        """测试按键输入"""
        try:
            print("=== 按键测试模式 ===")
            print("将测试发送W键到当前活动窗口")
            print("请确保游戏窗口处于活动状态")
            
            # 尝试激活游戏窗口
            self.activate_game_window()
            
            print("3秒后开始测试...")
            time.sleep(3)
            
            # 测试W键
            vk_code = VK_CODE.get('w')
            if vk_code:
                print("发送W键 (Windows API)...")
                self._send_key_windows(vk_code, True)   # 按下
                time.sleep(0.1)                         # 持续100ms
                self._send_key_windows(vk_code, False)  # 释放
                print("W键已发送")
                
                time.sleep(1)
                
                print("发送W键 (keyboard库)...")
                keyboard.press_and_release('w')
                print("W键已发送 (keyboard库)")
            
            print("测试完成！如果游戏中角色没有移动，请检查：")
            print("1. 游戏窗口是否处于活动状态")
            print("2. 游戏是否需要管理员权限运行")
            print("3. 是否有其他软件拦截了按键")
            
        except Exception as e:
            print(f"测试按键失败: {str(e)}")

def check_admin_rights():
    """检查是否以管理员权限运行"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    """PC回放器主函数"""
    import os
    import glob
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.table import Table
    
    console = Console()
    replayer = PCReplayer()
    
    console.print("[bold blue]PC端回放(不可用)器[/bold blue]")
    
    # 检查管理员权限
    if not check_admin_rights():
        console.print("[yellow]注意: 未检测到管理员权限[/yellow]")
        console.print("[yellow]如果游戏无法接收按键，请尝试以管理员身份运行此程序[/yellow]")
        console.print()
    
    # 设置默认目录
    recording_dir = os.path.join(os.path.dirname(__file__), "recording")
    os.makedirs(recording_dir, exist_ok=True)
    
    while True:
        try:
            console.print(f"\n[cyan]录制文件目录: {recording_dir}[/cyan]")
            
            # 查找所有JSON录制文件
            pattern = os.path.join(recording_dir, "*.json")
            json_files = glob.glob(pattern)
            
            if not json_files:
                console.print("[red]未找到录制文件！[/red]")
                console.print(f"请将录制文件(.json)放入: {recording_dir}")
                input("按回车键刷新...")
                continue
            
            # 按修改时间排序（最新的在前面）
            json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # 创建文件列表表格
            table = Table(title="录制文件列表")
            table.add_column("序号", style="cyan", width=4)
            table.add_column("文件名", style="green")
            table.add_column("大小", style="yellow", width=8)
            table.add_column("修改时间", style="blue")
            
            for i, file_path in enumerate(json_files, 1):
                filename = os.path.basename(file_path)
                file_size = f"{os.path.getsize(file_path) / 1024:.1f}KB"
                mod_time = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(file_path)))
                table.add_row(str(i), filename, file_size, mod_time)
            
            console.print(table)
            
            # 显示操作选项
            console.print("\n[yellow]操作选项:[/yellow]")
            console.print("• 输入数字 - 回放对应文件")
            console.print("• t - 测试按键输出")
            console.print("• r - 刷新文件列表")
            console.print("• q - 退出程序")
            
            choice = input("\n请输入选择: ").strip().lower()
            
            if choice == 'q':
                if replayer.is_replaying():
                    replayer.stop_replay()
                console.print("[green]退出程序[/green]")
                break
                
            elif choice == 't':
                # 测试按键
                replayer.test_key_input()
                
            elif choice == 'r':
                # 刷新文件列表
                continue
                
            elif choice.isdigit():
                # 选择文件回放
                file_index = int(choice) - 1
                if 0 <= file_index < len(json_files):
                    selected_file = json_files[file_index]
                    filename = os.path.basename(selected_file)
                    
                    if replayer.is_replaying():
                        console.print("[red]当前正在回放中，请先等待完成[/red]")
                        continue
                    
                    console.print(f"[green]选择文件: {filename}[/green]")
                    console.print("[yellow]即将开始回放，请确保游戏窗口已准备好[/yellow]")
                    
                    confirm = input("确认开始回放? (y/n): ").strip().lower()
                    if confirm in ['y', 'yes', '']:
                        if replayer.load_and_replay(selected_file):
                            console.print("[green]回放已开始！[/green]")
                            console.print("[yellow]按ESC键可随时停止回放[/yellow]")
                            
                            # 等待回放完成，同时监听ESC键
                            try:
                                while replayer.is_replaying():
                                    if keyboard.is_pressed('esc'):
                                        replayer.stop_replay()
                                        console.print("[yellow]用户按ESC停止回放[/yellow]")
                                        break
                                    time.sleep(0.1)
                                
                                if not replayer.is_replaying():
                                    console.print("[green]回放完成[/green]")
                                    
                            except KeyboardInterrupt:
                                replayer.stop_replay()
                                console.print("[yellow]回放被中断[/yellow]")
                        else:
                            console.print("[red]回放启动失败[/red]")
                    else:
                        console.print("[yellow]回放已取消[/yellow]")
                else:
                    console.print("[red]无效的文件序号[/red]")
            else:
                console.print("[red]无效的选择，请重新输入[/red]")
                
        except KeyboardInterrupt:
            if replayer.is_replaying():
                replayer.stop_replay()
            console.print("\n[yellow]程序被中断，退出中...[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]发生错误: {str(e)}[/red]")

if __name__ == "__main__":
    main() 