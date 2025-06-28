"""
手机端回放器 - 通过ADB在手机上回放录制的操作
"""

import json
import time
import threading
import os
import subprocess
from datetime import datetime
import ADBHelper

class MobileReplayer:
    """手机端回放器类"""
    
    def __init__(self):
        self.replaying = False
        self.replay_thread = None
        self.device_id = ""
        self.long_press_compensation = 150  # 长按补偿时间(ms)，可通过配置修改
        self.start_timing_calibration = 0.2  # 开局起手时间校准(秒)，默认0.2秒
        
    def get_available_devices(self):
        """获取可用设备列表"""
        try:
            devices = ADBHelper.getDevicesList()
            return devices
        except Exception as e:
            print(f"获取设备列表失败: {str(e)}")
            return []
    
    def set_device(self, device_id: str):
        """设置目标设备"""
        self.device_id = device_id
        print(f"已设置目标设备: {device_id}")
        
    def set_start_timing_calibration(self, calibration_seconds: float):
        """设置开局起手时间校准"""
        self.start_timing_calibration = calibration_seconds
        print(f"开局起手时间校准已设置为: {calibration_seconds}秒")
    
    def load_and_replay(self, recording_file: str):
        """加载并回放录制文件"""
        try:
            if not self.device_id:
                print("错误: 未设置目标设备")
                return False
                
            # 加载录制文件
            with open(recording_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            actions = data.get('actions', [])
            if not actions:
                print("录制文件中没有动作数据")
                return False
            
            # 应用开局起手时间校准
            calibrated_actions = self._apply_timing_calibration(actions)
            
            print(f"开始回放录制文件: {recording_file}")
            print(f"目标设备: {self.device_id}")
            print(f"共 {len(calibrated_actions)} 个动作")
            print(f"长按补偿: +{self.long_press_compensation}ms")
            print(f"开局起手时间校准: {self.start_timing_calibration}秒")
            
            # 启动回放线程
            self.replay_thread = threading.Thread(
                target=self._replay_actions, 
                args=(calibrated_actions,), 
                daemon=True
            )
            self.replaying = True
            self.replay_thread.start()
            
            return True
            
        except Exception as e:
            print(f"加载录制文件失败: {str(e)}")
            return False
    
    def _apply_timing_calibration(self, actions):
        """应用开局起手时间校准"""
        try:
            if not actions:
                return actions
            
            # 获取第一个动作的原始时间戳
            first_action_timestamp = actions[0].get('timestamp', 0)
            
            # 计算时间偏移量
            time_offset = self.start_timing_calibration - first_action_timestamp
            
            print(f"原始第一个动作时间戳: {first_action_timestamp:.3f}秒")
            print(f"目标起手时间: {self.start_timing_calibration:.3f}秒")
            print(f"时间偏移量: {time_offset:+.3f}秒")
            
            # 创建校准后的动作列表
            calibrated_actions = []
            for action in actions:
                # 复制动作数据
                calibrated_action = action.copy()
                
                # 调整时间戳
                original_timestamp = action.get('timestamp', 0)
                calibrated_timestamp = original_timestamp + time_offset
                
                # 确保时间戳不为负数
                if calibrated_timestamp < 0:
                    print(f"警告: 校准后时间戳为负数 ({calibrated_timestamp:.3f}秒)，调整为0")
                    calibrated_timestamp = 0
                
                calibrated_action['timestamp'] = calibrated_timestamp
                calibrated_actions.append(calibrated_action)
            
            # 输出校准结果
            print(f"时间校准完成:")
            print(f"  第一个动作: {first_action_timestamp:.3f}秒 -> {calibrated_actions[0]['timestamp']:.3f}秒")
            if len(calibrated_actions) > 1:
                last_original = actions[-1].get('timestamp', 0)
                last_calibrated = calibrated_actions[-1]['timestamp']
                print(f"  最后动作: {last_original:.3f}秒 -> {last_calibrated:.3f}秒")
            
            return calibrated_actions
            
        except Exception as e:
            print(f"应用时间校准失败: {str(e)}")
            return actions  # 发生错误时返回原始动作
    
    def _replay_actions(self, actions):
        """回放动作序列"""
        try:
            print("回放开始，0.1秒后开始执行...")
            time.sleep(0.1)  # 给用户准备时间
            
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
                # 计算动作应该执行的绝对时间
                target_timestamp = action.get('timestamp', 0)
                target_absolute_time = start_time + target_timestamp
                
                # 等待到指定的绝对时间点
                current_time = time.time()
                delay = target_absolute_time - current_time
                
                if delay > 0:
                    time.sleep(delay)
                
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
            source = action.get('source', 'unknown')  # 获取动作来源
            
            # 输出动作信息，包含来源
            action_info = f"{key} ({source})" if source != 'unknown' else key
            
            if action_type == 'tap':
                # 点按动作
                position = action.get('position')
                duration = action.get('duration', 50)
                
                if position:
                    # 使用与录制时完全相同的长按判断逻辑
                    if key in ['a', 'd'] and duration > 100:  # 只有A/D键且持续时间>100ms才认为是长按
                        # 长按操作增加配置的补偿时间
                        compensated_duration = duration + self.long_press_compensation
                        # 使用与录制时相同的ADB命令执行方式
                        x, y = position
                        cmd = f"adb -s {self.device_id} shell input swipe {x} {y} {x} {y} {compensated_duration}"
                        subprocess.run(cmd, shell=True, capture_output=True, timeout=max(2, compensated_duration/1000 + 1))
                        print(f"执行长按: {action_info} -> {position}, 原时长: {duration}ms, 补偿后: {compensated_duration}ms")
                    else:
                        # 普通点击（与录制时一致）
                        ADBHelper.touch(self.device_id, position)
                        print(f"执行点击: {action_info} -> {position}")
                
            elif action_type == 'long_press':
                # 长按动作
                position = action.get('position')
                duration = action.get('duration', 500)
                
                if position:
                    # 长按操作增加配置的补偿时间
                    compensated_duration = duration + self.long_press_compensation
                    # 使用与录制时相同的ADB命令执行方式
                    x, y = position
                    cmd = f"adb -s {self.device_id} shell input swipe {x} {y} {x} {y} {compensated_duration}"
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=max(2, compensated_duration/1000 + 1))
                    print(f"执行长按: {action_info} -> {position}, 原时长: {duration}ms, 补偿后: {compensated_duration}ms")
                
            elif action_type == 'long_press_start':
                # 长按开始（这种情况下需要等待对应的结束动作）
                position = action.get('position')
                if position:
                    ADBHelper.startLongPress(self.device_id, position)
                    print(f"开始长按: {action_info} -> {position}")
                    
            elif action_type == 'long_press_end':
                # 长按结束
                position = action.get('position')
                if position:
                    ADBHelper.endLongPress(self.device_id, position)
                    print(f"结束长按: {action_info} -> {position}")
                    
            elif action_type == 'view_control' or action_type == 'swipe':
                # 视角控制和滑动操作
                if 'start_position' in action and 'end_position' in action:
                    start_pos = action['start_position']
                    end_pos = action['end_position']
                    duration = action.get('duration', 300)
                    direction = action.get('direction', 'unknown')
                    
                    ADBHelper.slide(self.device_id, start_pos, end_pos, duration)
                    print(f"执行滑动: {direction} ({source}) {start_pos} -> {end_pos}, 时长: {duration}ms")
            else:
                # 未知动作类型
                print(f"跳过未知动作类型: {action_type} ({source})")
                    
        except Exception as e:
            print(f"执行动作出错: {str(e)}, 动作: {action}")
    
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
    
    def set_long_press_compensation(self, compensation_ms: int):
        """设置长按补偿时间"""
        self.long_press_compensation = compensation_ms
        print(f"长按补偿时间已设置为: {compensation_ms}ms")

def main():
    """手机端回放器主函数"""
    import glob
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    replayer = MobileReplayer()
    
    console.print("[bold blue]手机端回放器[/bold blue]")
    console.print(f"[yellow]长按补偿: {replayer.long_press_compensation}ms (可通过c+数字修改)[/yellow]")
    console.print(f"[yellow]开局起手时间校准: {replayer.start_timing_calibration}秒[/yellow]")
    
    # 设置默认目录
    recording_dir = os.path.join(os.path.dirname(__file__), "recording")
    os.makedirs(recording_dir, exist_ok=True)
    
    while True:
        try:
            console.print(f"\n[cyan]录制文件目录: {recording_dir}[/cyan]")
            
            # 获取设备列表
            devices = replayer.get_available_devices()
            if not devices:
                console.print("[red]未找到连接的设备！[/red]")
                console.print("请确保设备已连接并启用USB调试")
                input("按回车键刷新...")
                continue
            
            # 显示设备列表
            console.print("\n[green]可用设备:[/green]")
            for i, device in enumerate(devices, 1):
                status = "[green]当前选择[/green]" if device == replayer.device_id else ""
                console.print(f"  {i}. {device} {status}")
            
            # 查找录制文件
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
            console.print("• d + 数字 - 选择设备 (如: d1)")
            console.print("• c + 数字 - 设置长按补偿 (如: c200)")
            console.print("• t + 数字 - 设置开局起手时间校准 (如: t0.2, 单位秒)")
            console.print("• s - 停止当前回放")
            console.print("• r - 刷新列表")
            console.print("• q - 退出程序")
            
            choice = input("\n请输入选择: ").strip().lower()
            
            if choice == 'q':
                if replayer.is_replaying():
                    replayer.stop_replay()
                console.print("[green]退出程序[/green]")
                break
                
            elif choice == 's':
                # 停止回放
                if replayer.is_replaying():
                    replayer.stop_replay()
                    console.print("[yellow]回放已停止[/yellow]")
                else:
                    console.print("[yellow]当前没有正在进行的回放[/yellow]")
                    
            elif choice == 'r':
                # 刷新列表
                continue
                
            elif choice.startswith('d') and len(choice) > 1:
                # 选择设备
                try:
                    device_index = int(choice[1:]) - 1
                    if 0 <= device_index < len(devices):
                        replayer.set_device(devices[device_index])
                        console.print(f"[green]已选择设备: {devices[device_index]}[/green]")
                    else:
                        console.print("[red]无效的设备序号[/red]")
                except ValueError:
                    console.print("[red]无效的设备选择格式[/red]")
                    
            elif choice.startswith('c') and len(choice) > 1:
                # 设置长按补偿
                try:
                    compensation = int(choice[1:])
                    if 0 <= compensation <= 1000:
                        replayer.set_long_press_compensation(compensation)
                        console.print(f"[green]长按补偿已设置为: {compensation}ms[/green]")
                    else:
                        console.print("[red]补偿时间应在0-1000ms之间[/red]")
                except ValueError:
                    console.print("[red]无效的补偿时间格式[/red]")
                    
            elif choice.startswith('t') and len(choice) > 1:
                # 设置开局起手时间校准
                try:
                    calibration = float(choice[1:])
                    if 0.0 <= calibration <= 10.0:
                        replayer.set_start_timing_calibration(calibration)
                        console.print(f"[green]开局起手时间校准已设置为: {calibration}秒[/green]")
                    else:
                        console.print("[red]校准时间应在0.0-10.0秒之间[/red]")
                except ValueError:
                    console.print("[red]无效的校准时间格式[/red]")
                    
            elif choice.isdigit():
                # 选择文件回放
                file_index = int(choice) - 1
                if 0 <= file_index < len(json_files):
                    if not replayer.device_id:
                        console.print("[red]请先选择设备 (使用 d + 数字)[/red]")
                        continue
                        
                    if replayer.is_replaying():
                        console.print("[red]当前正在回放中，请先停止 (输入 s)[/red]")
                        continue
                    
                    selected_file = json_files[file_index]
                    filename = os.path.basename(selected_file)
                    
                    console.print(f"[green]选择文件: {filename}[/green]")
                    console.print(f"[green]目标设备: {replayer.device_id}[/green]")
                    console.print(f"[yellow]长按补偿: {replayer.long_press_compensation}ms (可通过c+数字修改)[/yellow]")
                    console.print(f"[yellow]开局起手时间校准: {replayer.start_timing_calibration}秒[/yellow]")
                    
                    confirm = input("确认开始回放? (y/n): ").strip().lower()
                    if confirm in ['y', 'yes', '']:
                        if replayer.load_and_replay(selected_file):
                            console.print("[green]回放已开始！[/green]")
                            console.print("[yellow]输入 s 可停止回放[/yellow]")
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