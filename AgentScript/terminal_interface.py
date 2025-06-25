import os
import time
import threading
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.columns import Columns
from rich.align import Align
from rich import box
from action_recorder import ActionRecorder
from keyboard_listener import KeyboardListener
import ADBHelper
from pc_replayer import PCReplayer
from mobile_replayer import MobileReplayer
import glob

class TerminalInterface:
    """Rich终端界面类"""
    
    def __init__(self):
        self.console = Console()
        self.recorder = ActionRecorder()
        self.keyboard_listener = KeyboardListener(self.recorder)
        self.pc_replayer = PCReplayer()
        self.mobile_replayer = MobileReplayer()
        self.devices = []
        self.current_device = ""
        self.recording_mode = 'adb'  # 'adb' 或 'pc'
        self.running = False
        self.live_display = None
        
    def show_banner(self):
        """显示程序横幅"""
        banner_text = """
        ╔══════════════════════════════════════════════════════════════╗
        ║                 现代战舰战斗录制器 v1.0                        ║
        ║                Modern Warship Battle Recorder                ║
        ║                                                              ║
        ║                    基于Rich的终端界面                          ║
        ╚══════════════════════════════════════════════════════════════╝
        """
        
        self.console.print(Panel(
            Align.center(banner_text),
            style="bold blue",
            border_style="bright_blue"
        ))
        
    def show_help(self):
        """显示帮助信息"""
        help_table = Table(title="按键映射说明", box=box.ROUNDED)
        help_table.add_column("功能", style="cyan", width=15)
        help_table.add_column("按键", style="magenta", width=10)
        help_table.add_column("操作类型", style="green", width=10)
        help_table.add_column("说明", style="yellow")
        
        # 移动控制
        help_table.add_row("前进", "W", "点按", "战舰前进")
        help_table.add_row("后退", "S", "点按", "战舰后退")
        help_table.add_row("左转", "A", "长按", "战舰左转")
        help_table.add_row("右转", "D", "长按", "战舰右转")
        
        # 武器控制
        help_table.add_row("1号武器", "1", "点按", "发射主武器")
        help_table.add_row("2号武器", "2", "点按", "发射副武器")
        help_table.add_row("3号武器", "3", "点按", "发射导弹")
        help_table.add_row("4号武器", "4", "点按", "发射鱼雷")
        
        # 特殊功能
        help_table.add_row("回血", "Q", "点按", "使用回血道具")
        help_table.add_row("热诱弹", "E", "点按", "释放热诱弹")
        
        # 视角控制
        help_table.add_row("慢速视角", "Z", "模式切换", "切换到慢速视角模式")
        help_table.add_row("快速视角", "X", "模式切换", "切换到快速视角模式")
        help_table.add_row("视角控制", "方向键", "滑动", "控制视角方向")
        
        self.console.print(help_table)
        
    def refresh_devices(self):
        """刷新设备列表"""
        with self.console.status("[bold green]正在搜索设备..."):
            self.devices = ADBHelper.getDevicesList()
            
        if self.devices:
            self.console.print(f"[green]找到 {len(self.devices)} 个设备:")
            for i, device in enumerate(self.devices):
                self.console.print(f"  {i+1}. {device}")
        else:
            self.console.print("[red]未找到连接的设备")
            
    def select_device(self):
        """选择设备"""
        if not self.devices:
            self.console.print("[red]没有可用设备")
            return False
            
        if len(self.devices) == 1:
            self.current_device = self.devices[0]
            self.console.print(f"[green]自动选择设备: {self.current_device}")
            return True
            
        # 多个设备时让用户选择
        while True:
            try:
                choice = Prompt.ask(
                    "请选择设备",
                    choices=[str(i+1) for i in range(len(self.devices))],
                    default="1"
                )
                self.current_device = self.devices[int(choice) - 1]
                self.console.print(f"[green]已选择设备: {self.current_device}")
                return True
            except (ValueError, IndexError):
                self.console.print("[red]无效选择，请重试")
                
    def create_status_layout(self):
        """创建状态显示布局"""
        layout = Layout()
        
        # 创建录制状态面板
        recording_status = "正在录制" if self.recorder.is_recording() else "未录制"
        status_color = "green" if self.recorder.is_recording() else "red"
        
        # 录制时间
        current_time = self.recorder.get_current_time()
        hours = int(current_time // 3600)
        minutes = int((current_time % 3600) // 60)
        seconds = int(current_time % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # 动作数量
        action_count = len(self.recorder.get_actions())
        
        # 视角模式
        view_mode = self.keyboard_listener.get_view_mode()
        mode_text = "慢速" if view_mode == "slow" else "快速"
        
        # 当前按下的按键
        pressed_keys = self.keyboard_listener.get_pressed_keys()
        keys_text = ", ".join(pressed_keys) if pressed_keys else "无"
        
        status_table = Table(box=box.ROUNDED, title="录制状态")
        status_table.add_column("项目", style="cyan")
        status_table.add_column("值", style="white")
        
        status_table.add_row("录制状态", f"[{status_color}]{recording_status}[/{status_color}]")
        status_table.add_row("录制模式", f"{'PC模式' if self.recording_mode == 'pc' else 'ADB模式'}")
        status_table.add_row("录制时间", time_str)
        status_table.add_row("动作数量", str(action_count))
        status_table.add_row("视角模式", mode_text)
        status_table.add_row("当前设备", self.current_device or "未选择")
        status_table.add_row("按下按键", keys_text)
        
        # 最近动作
        recent_actions = self.recorder.get_actions()[-5:] if self.recorder.get_actions() else []
        
        if recent_actions:
            actions_table = Table(box=box.ROUNDED, title="最近动作")
            actions_table.add_column("时间", style="yellow", width=8)
            actions_table.add_column("类型", style="green", width=12)
            actions_table.add_column("按键", style="magenta", width=6)
            actions_table.add_column("位置", style="cyan")
            
            for action in recent_actions:
                time_str = f"{action['timestamp']:.1f}s"
                action_type = action['type']
                key = action.get('key', '')
                
                if 'position' in action:
                    pos_text = f"{action['position']}"
                elif 'start_position' in action:
                    pos_text = f"{action['start_position']} -> {action['end_position']}"
                else:
                    pos_text = ""
                    
                actions_table.add_row(time_str, action_type, key, pos_text)
        else:
            actions_table = Panel("暂无录制动作", title="最近动作")
            
        # 组合布局
        layout.split_column(
            Layout(status_table, name="status"),
            Layout(actions_table, name="actions")
        )
        
        return layout
        
    def start_live_display(self):
        """启动实时状态显示"""
        def update_display():
            while self.running:
                try:
                    layout = self.create_status_layout()
                    if self.live_display:
                        self.live_display.update(layout)
                    time.sleep(0.5)  # 每0.5秒更新一次
                except Exception as e:
                    # 忽略更新错误，继续运行
                    pass
                    
        # 启动更新线程
        update_thread = threading.Thread(target=update_display, daemon=True)
        update_thread.start()
        
    def start_recording(self):
        """开始录制"""
        # 根据录制模式进行不同的处理
        if self.recording_mode == 'adb':
            # ADB模式需要设备
            if not self.current_device:
                self.console.print("[red]请先选择设备")
                return False
                
            # 如果有现有数据，询问是否清空
            clear_existing = True
            if len(self.recorder.get_actions()) > 0:
                clear_existing = Confirm.ask(
                    "检测到现有录制数据，是否清空后开始新录制？(选择No将继续在现有数据基础上录制)"
                )
                
            self.console.print("[green]开始ADB录制...")
            self.recorder.start_recording(self.current_device, clear_existing)
            
            # 询问是否需要回放PC录制
            if Confirm.ask("是否需要在录制时回放PC端录制的船体操控？"):
                # 设置默认目录
                recording_dir = os.path.join(os.path.dirname(__file__), "recording")
                os.makedirs(recording_dir, exist_ok=True)
                
                pc_file = Prompt.ask(
                    "请输入PC端录制文件路径",
                    default=recording_dir + "/"
                )
                if os.path.exists(pc_file):
                    self.recorder.replay_pc_actions(pc_file)
                    self.console.print("[green]PC端录制回放已启动")
                else:
                    self.console.print("[red]PC端录制文件不存在")
        else:
            # PC模式不需要设备
            # 如果有现有数据，询问是否清空
            clear_existing = True
            if len(self.recorder.get_actions()) > 0:
                clear_existing = Confirm.ask(
                    "检测到现有录制数据，是否清空后开始新录制？(选择No将继续在现有数据基础上录制)"
                )
                
            self.console.print("[green]开始PC端录制 (只录制船体操控)...")
            self.recorder.start_recording("", clear_existing)
            
        # 启动键盘监听
        self.keyboard_listener.start_listening(self.recording_mode)
        
        # 启动实时显示
        self.running = True
        layout = self.create_status_layout()
        
        with Live(layout, refresh_per_second=2, screen=True) as live:
            self.live_display = live
            self.start_live_display()
            
            try:
                # 等待用户按Ctrl+C停止录制
                mode_name = "PC端录制" if self.recording_mode == 'pc' else "ADB录制"
                self.console.print(f"\n[yellow]{mode_name}已开始，按 Ctrl+C 停止录制")
                while self.running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                self.stop_recording()
                
        return True
        
    def stop_recording(self):
        """停止录制"""
        self.running = False
        self.recorder.stop_recording()
        self.keyboard_listener.stop_listening()
        self.live_display = None
        
        self.console.print("[yellow]录制已停止")
        
        # 显示录制统计
        self.show_recording_stats()
        
    def show_recording_stats(self):
        """显示录制统计信息"""
        stats = self.recorder.get_statistics()
        
        if not stats:
            self.console.print("[yellow]暂无录制数据")
            return
            
        stats_table = Table(title="录制统计", box=box.ROUNDED)
        stats_table.add_column("统计项", style="cyan")
        stats_table.add_column("数值", style="white")
        
        stats_table.add_row("总动作数", str(stats['total_actions']))
        stats_table.add_row("总时长", f"{stats['total_duration']:.2f} 秒")
        
        self.console.print(stats_table)
        
        # 动作类型统计
        if stats['action_types']:
            type_table = Table(title="动作类型统计", box=box.ROUNDED)
            type_table.add_column("类型", style="green")
            type_table.add_column("次数", style="white")
            
            for action_type, count in stats['action_types'].items():
                type_table.add_row(action_type, str(count))
                
            self.console.print(type_table)
            
        # 按键使用统计
        if stats['key_usage']:
            key_table = Table(title="按键使用统计", box=box.ROUNDED)
            key_table.add_column("按键", style="magenta")
            key_table.add_column("次数", style="white")
            
            for key, count in stats['key_usage'].items():
                key_table.add_row(key, str(count))
                
            self.console.print(key_table)
            
    def save_recording(self):
        """保存录制"""
        if not self.recorder.get_actions():
            self.console.print("[yellow]没有录制数据可保存")
            return False
        
        # 确保recording目录存在
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
            
        # 生成默认文件名
        default_filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filename = Prompt.ask(
            "请输入保存文件名",
            default=os.path.join(recording_dir, default_filename)
        )
        
        if self.recorder.save_to_file(filename):
            self.console.print(f"[green]录制已保存到: {filename}")
            return True
        else:
            self.console.print("[red]保存失败")
            return False
            
    def load_recording(self):
        """加载录制"""
        # 设置默认目录
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        filename = Prompt.ask(
            "请输入要加载的文件路径", 
            default=recording_dir + "/"
        )
        
        if not os.path.exists(filename):
            self.console.print(f"[red]文件不存在: {filename}")
            return False
            
        if self.recorder.load_from_file(filename):
            self.console.print(f"[green]录制已加载: {filename}")
            self.show_recording_stats()
            return True
        else:
            self.console.print("[red]加载失败")
            return False
            
    def show_actions_list(self):
        """显示动作列表"""
        actions = self.recorder.get_actions()
        
        if not actions:
            self.console.print("[yellow]暂无录制动作")
            return
            
        actions_table = Table(title=f"动作列表 (共{len(actions)}个)", box=box.ROUNDED)
        actions_table.add_column("序号", style="cyan", width=6)
        actions_table.add_column("时间", style="yellow", width=8)
        actions_table.add_column("类型", style="green", width=12)
        actions_table.add_column("按键", style="magenta", width=6)
        actions_table.add_column("位置", style="white")
        actions_table.add_column("持续时间", style="blue", width=10)
        
        for i, action in enumerate(actions):
            time_str = f"{action['timestamp']:.2f}s"
            action_type = action['type']
            key = action.get('key', '')
            
            if 'position' in action:
                pos_text = f"{action['position']}"
            elif 'start_position' in action:
                pos_text = f"{action['start_position']} -> {action['end_position']}"
            else:
                pos_text = ""
                
            duration = f"{action.get('duration', 0)}ms"
            
            actions_table.add_row(
                str(i + 1), time_str, action_type, key, pos_text, duration
            )
            
        self.console.print(actions_table)
        
    def show_main_menu(self):
        """显示主菜单"""
        self.console.clear()
        self.console.print(Panel("[bold blue]现代战舰代肝脚本 - 终端界面[/bold blue]", 
                                style="bold cyan"))
        
        # 显示当前状态
        status_table = Table(show_header=False, box=None)
        status_table.add_column("", style="cyan")
        status_table.add_column("", style="white")
        
        status_table.add_row("当前设备:", self.current_device or "[red]未选择[/red]")
        status_table.add_row("录制模式:", "PC模式" if self.recording_mode == "pc" else "ADB模式")
        
        recording_status = "[green]录制中[/green]" if self.recorder.is_recording() else "[yellow]就绪[/yellow]"
        pc_replay_status = "[blue]PC回放中[/blue]" if self.pc_replayer.is_replaying() else ""
        mobile_replay_status = "[purple]手机端回放中[/purple]" if self.mobile_replayer.is_replaying() else ""
        
        # 组合状态显示
        all_status = [s for s in [recording_status, pc_replay_status, mobile_replay_status] if s]
        status_table.add_row("当前状态:", " | ".join(all_status) if all_status else "[yellow]就绪[/yellow]")
        
        self.console.print(status_table)
        self.console.print()
        
        # 显示菜单选项
        menu_table = Table(title="功能菜单", box=box.ROUNDED)
        menu_table.add_column("选项", style="cyan", width=4)
        menu_table.add_column("功能", style="white")
        menu_table.add_column("说明", style="dim")
        
        menu_table.add_row("1", "设备管理", "选择和管理ADB设备")
        menu_table.add_row("2", "录制控制", "开始/停止录制操作")
        menu_table.add_row("3", "文件操作", "保存/加载录制文件")
        menu_table.add_row("4", "PC端回放", "在PC上回放录制的操作")
        menu_table.add_row("5", "手机端回放", "在手机上回放录制的操作")
        menu_table.add_row("6", "统计信息", "查看录制统计和动作详情")
        menu_table.add_row("7", "设置选项", "配置录制参数")
        menu_table.add_row("0", "退出程序", "")
        
        self.console.print(menu_table)
        
        # 检查状态并显示提示
        if self.recorder.is_recording():
            self.console.print("\n[yellow]提示: 正在录制中，按 Ctrl+C 可停止录制[/yellow]")
        elif self.pc_replayer.is_replaying():
            self.console.print("\n[blue]提示: PC回放正在进行中[/blue]")
        elif self.mobile_replayer.is_replaying():
            self.console.print("\n[purple]提示: 手机端回放正在进行中[/purple]")
            
    def handle_menu_choice(self, choice):
        """处理菜单选择"""
        try:
            if choice == "1":
                self.device_management()
            elif choice == "2":
                self.recording_control()
            elif choice == "3":
                self.file_operations()
            elif choice == "4":
                self.pc_replay_menu()
            elif choice == "5":
                self.mobile_replay_menu()
            elif choice == "6":
                self.statistics_menu()
            elif choice == "7":
                self.settings_menu()
            elif choice == "0":
                return self.exit_program()
            else:
                self.console.print("[red]无效选择，请重新输入[/red]")
                
        except KeyboardInterrupt:
            if self.recorder.is_recording():
                self.recorder.stop_recording()
                self.console.print("\n[yellow]录制已停止[/yellow]")
            elif self.pc_replayer.is_replaying():
                self.pc_replayer.stop_replay()
                self.console.print("\n[yellow]PC回放已停止[/yellow]")
            elif self.mobile_replayer.is_replaying():
                self.mobile_replayer.stop_replay()
                self.console.print("\n[yellow]手机端回放已停止[/yellow]")
        except Exception as e:
            self.console.print(f"[red]操作出错: {str(e)}[/red]")
            
        input("\n按回车键继续...")
        return True
        
    def device_management(self):
        """设备管理"""
        self.console.print("\n[bold yellow]设备管理")
        self.refresh_devices()
        self.select_device()
        
    def recording_control(self):
        """录制控制"""
        self.console.print("\n[bold yellow]录制控制")
        if self.recorder.is_recording():
            self.stop_recording()
        else:
            self.start_recording()
            
    def file_operations(self):
        """文件操作"""
        self.console.print("\n[bold yellow]文件操作")
        self.save_recording()
        self.load_recording()
        
    def pc_replay_menu(self):
        """PC端回放菜单"""
        self.console.clear()
        self.console.print(Panel("[bold blue]PC端回放[/bold blue]", style="bold cyan"))
        
        if self.pc_replayer.is_replaying():
            self.console.print("[blue]PC端回放正在进行中...[/blue]")
            self.console.print("\n选项:")
            self.console.print("1. 停止回放")
            self.console.print("0. 返回主菜单")
            
            choice = Prompt.ask("请选择", choices=["1", "0"])
            
            if choice == "1":
                self.pc_replayer.stop_replay()
                self.console.print("[green]PC端回放已停止[/green]")
            return
            
        if not self.current_device:
            self.console.print("[red]错误: 未选择设备，请先在设备管理中选择设备[/red]")
            return
            
        # 设置录制文件目录
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        # 查找录制文件
        pattern = os.path.join(recording_dir, "*.json")
        json_files = glob.glob(pattern)
        
        if not json_files:
            self.console.print("[red]未找到录制文件！[/red]")
            self.console.print(f"请将录制文件(.json)放入: {recording_dir}")
            return
            
        # 按修改时间排序（最新的在前面）
        json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # 显示文件列表
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
        
        self.console.print(table)
        
        # 显示当前设置
        self.console.print(f"\n[cyan]目标设备:[/cyan] {self.current_device}")
        self.console.print(f"[cyan]长按补偿:[/cyan] +{self.pc_replayer.long_press_compensation}ms")
        
        self.console.print("\n选项:")
        self.console.print("• 输入数字 - 回放对应文件")
        self.console.print("• c + 数字 - 设置长按补偿 (如: c200)")
        self.console.print("• 0 - 返回主菜单")
        
        choice = input("\n请输入选择: ").strip().lower()
        
        if choice == "0":
            return
        elif choice.startswith('c') and len(choice) > 1:
            # 设置长按补偿
            try:
                compensation = int(choice[1:])
                if 0 <= compensation <= 1000:
                    self.pc_replayer.set_long_press_compensation(compensation)
                    self.console.print(f"[green]长按补偿已设置为: {compensation}ms[/green]")
                else:
                    self.console.print("[red]补偿时间应在0-1000ms之间[/red]")
            except ValueError:
                self.console.print("[red]无效的补偿时间格式[/red]")
        elif choice.isdigit():
            # 选择文件回放
            file_index = int(choice) - 1
            if 0 <= file_index < len(json_files):
                selected_file = json_files[file_index]
                filename = os.path.basename(selected_file)
                
                self.console.print(f"\n[green]选择文件:[/green] {filename}")
                self.console.print(f"[green]目标设备:[/green] {self.current_device}")
                self.console.print(f"[yellow]长按补偿:[/yellow] +{self.pc_replayer.long_press_compensation}ms")
                
                confirm = Confirm.ask("确认开始回放?")
                if confirm:
                    # 设置设备
                    self.pc_replayer.set_device(self.current_device)
                    
                    if self.pc_replayer.load_and_replay(selected_file):
                        self.console.print("[green]PC端回放已开始！[/green]")
                        self.console.print("[yellow]回放将在3秒后开始执行[/yellow]")
                        self.console.print("[yellow]按 Ctrl+C 可随时停止回放[/yellow]")
                    else:
                        self.console.print("[red]回放启动失败[/red]")
                else:
                    self.console.print("[yellow]回放已取消[/yellow]")
            else:
                self.console.print("[red]无效的文件序号[/red]")
        else:
            self.console.print("[red]无效的选择[/red]")

    def mobile_replay_menu(self):
        """手机端回放菜单"""
        self.console.clear()
        self.console.print(Panel("[bold purple]手机端回放[/bold purple]", style="bold cyan"))
        
        if self.mobile_replayer.is_replaying():
            self.console.print("[purple]手机端回放正在进行中...[/purple]")
            self.console.print("\n选项:")
            self.console.print("1. 停止回放")
            self.console.print("0. 返回主菜单")
            
            choice = Prompt.ask("请选择", choices=["1", "0"])
            
            if choice == "1":
                self.mobile_replayer.stop_replay()
                self.console.print("[green]手机端回放已停止[/green]")
            return
            
        if not self.current_device:
            self.console.print("[red]错误: 未选择设备，请先在设备管理中选择设备[/red]")
            return
            
        # 设置录制文件目录
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        # 查找录制文件
        pattern = os.path.join(recording_dir, "*.json")
        json_files = glob.glob(pattern)
        
        if not json_files:
            self.console.print("[red]未找到录制文件！[/red]")
            self.console.print(f"请将录制文件(.json)放入: {recording_dir}")
            return
            
        # 按修改时间排序（最新的在前面）
        json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # 显示文件列表
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
        
        self.console.print(table)
        
        # 显示当前设置
        self.console.print(f"\n[cyan]目标设备:[/cyan] {self.current_device}")
        self.console.print(f"[cyan]长按补偿:[/cyan] +{self.mobile_replayer.long_press_compensation}ms")
        
        self.console.print("\n选项:")
        self.console.print("• 输入数字 - 回放对应文件")
        self.console.print("• c + 数字 - 设置长按补偿 (如: c200)")
        self.console.print("• 0 - 返回主菜单")
        
        choice = input("\n请输入选择: ").strip().lower()
        
        if choice == "0":
            return
        elif choice.startswith('c') and len(choice) > 1:
            # 设置长按补偿
            try:
                compensation = int(choice[1:])
                if 0 <= compensation <= 1000:
                    self.mobile_replayer.set_long_press_compensation(compensation)
                    self.console.print(f"[green]长按补偿已设置为: {compensation}ms[/green]")
                else:
                    self.console.print("[red]补偿时间应在0-1000ms之间[/red]")
            except ValueError:
                self.console.print("[red]无效的补偿时间格式[/red]")
        elif choice.isdigit():
            # 选择文件回放
            file_index = int(choice) - 1
            if 0 <= file_index < len(json_files):
                selected_file = json_files[file_index]
                filename = os.path.basename(selected_file)
                
                self.console.print(f"\n[green]选择文件:[/green] {filename}")
                self.console.print(f"[green]目标设备:[/green] {self.current_device}")
                self.console.print(f"[yellow]长按补偿:[/yellow] +{self.mobile_replayer.long_press_compensation}ms")
                
                confirm = Confirm.ask("确认开始回放?")
                if confirm:
                    # 设置设备
                    self.mobile_replayer.set_device(self.current_device)
                    
                    if self.mobile_replayer.load_and_replay(selected_file):
                        self.console.print("[green]手机端回放已开始！[/green]")
                        self.console.print("[yellow]回放将在3秒后开始执行[/yellow]")
                        self.console.print("[yellow]按 Ctrl+C 可随时停止回放[/yellow]")
                    else:
                        self.console.print("[red]回放启动失败[/red]")
                else:
                    self.console.print("[yellow]回放已取消[/yellow]")
            else:
                self.console.print("[red]无效的文件序号[/red]")
        else:
            self.console.print("[red]无效的选择[/red]")

    def statistics_menu(self):
        """统计信息"""
        self.show_recording_stats()
        
    def settings_menu(self):
        """设置选项"""
        self.console.print("\n[bold yellow]设置选项")
        self.select_recording_mode()
        
    def exit_program(self):
        """退出程序"""
        # 停止所有正在进行的操作
        if self.recorder.is_recording():
            self.recorder.stop_recording()
            self.console.print("[yellow]录制已停止[/yellow]")
            
        if self.pc_replayer.is_replaying():
            self.pc_replayer.stop_replay()
            self.console.print("[yellow]PC回放已停止[/yellow]")
            
        if self.mobile_replayer.is_replaying():
            self.mobile_replayer.stop_replay()
            self.console.print("[yellow]手机端回放已停止[/yellow]")
            
        self.console.print("[green]程序已退出[/green]")
        return False

    def select_recording_mode(self):
        """选择录制模式"""
        self.console.print("\n[bold yellow]录制模式选择:")
        self.console.print("1. ADB模式 - 手机端录制 (需要连接设备)")
        self.console.print("2. PC模式 - 电脑端录制 (只录制船体操控)")
        
        while True:
            choice = Prompt.ask(
                "请选择录制模式",
                choices=["1", "2"],
                default="1"
            )
            
            if choice == "1":
                self.recording_mode = 'adb'
                self.console.print("[green]已选择ADB模式")
                return True
            elif choice == "2":
                self.recording_mode = 'pc'
                self.console.print("[green]已选择PC模式")
                return True
                
    def run(self):
        """运行终端界面"""
        self.show_banner()
        self.console.print("[green]欢迎使用现代战舰战斗录制器!")
        self.console.print("[yellow]请确保已连接安卓设备并启用USB调试")
        
        # 初始化时刷新设备
        self.refresh_devices()
        
        while True:
            try:
                self.console.print()
                self.show_main_menu()
                
                choice = Prompt.ask(
                    "请选择操作",
                    choices=["0", "1", "2", "3", "4", "5", "6", "7"],
                    default="3"
                )
                
                if choice == "0":
                    if self.recorder.is_recording():
                        if Confirm.ask("正在录制中，确定要退出吗？"):
                            self.stop_recording()
                        else:
                            continue
                    self.console.print("[green]感谢使用，再见!")
                    break
                    
                elif choice == "1":
                    self.select_recording_mode()
                    
                elif choice == "2":
                    self.refresh_devices()
                    
                elif choice == "3":
                    self.select_device()
                    
                elif choice == "4":
                    if self.recorder.is_recording():
                        self.console.print("[red]已在录制中")
                    else:
                        self.start_recording()
                        
                elif choice == "5":
                    self.handle_menu_choice(choice)
                    
                elif choice == "6":
                    self.handle_menu_choice(choice)
                    
                elif choice == "7":
                    self.handle_menu_choice(choice)
                    
            except KeyboardInterrupt:
                if self.recorder.is_recording():
                    self.stop_recording()
                self.console.print("\n[yellow]程序被中断，退出中...")
                break
            except Exception as e:
                self.console.print(f"[red]发生错误: {str(e)}")
                
def main():
    """主函数"""
    interface = TerminalInterface()
    interface.run()

if __name__ == "__main__":
    main() 