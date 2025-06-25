import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QLabel, QTextEdit, QComboBox, 
                             QFileDialog, QMessageBox, QGroupBox, QGridLayout,
                             QProgressBar, QStatusBar, QTabWidget, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox, QCheckBox,
                             QRadioButton)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QPixmap, QIcon
import json
from datetime import datetime
from action_recorder import ActionRecorder
from keyboard_listener import KeyboardListener
import ADBHelper
from pc_replayer import PCReplayer
from mobile_replayer import MobileReplayer
import glob

class RecorderThread(QThread):
    """录制线程"""
    status_update = pyqtSignal(str)
    action_recorded = pyqtSignal(dict)
    
    def __init__(self, recorder, keyboard_listener):
        super().__init__()
        self.recorder = recorder
        self.keyboard_listener = keyboard_listener
        self.running = False
        
    def run(self):
        self.running = True
        self.keyboard_listener.start_listening()
        
        while self.running:
            self.msleep(100)  # 100ms检查一次
            
        self.keyboard_listener.stop_listening()
        
    def stop(self):
        self.running = False

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.action_recorder = ActionRecorder()
        self.keyboard_listener = KeyboardListener(self.action_recorder)
        self.pc_replayer = PCReplayer()
        self.mobile_replayer = MobileReplayer()  # 添加手机端回放器
        self.recorder_thread = None
        self.devices = []
        self.current_device = ""
        self.current_mode = "adb"  # 默认ADB模式
        
        self.init_ui()
        self.setup_timer()
        self.refresh_devices()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("现代战舰战斗录制器 v1.0")
        self.setGeometry(100, 100, 1000, 700)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # 录制控制选项卡
        self.create_recording_tab(tab_widget)
        
        # 动作列表选项卡
        self.create_actions_tab(tab_widget)
        
        # 统计信息选项卡
        self.create_statistics_tab(tab_widget)
        
        # 设置选项卡
        self.create_settings_tab(tab_widget)
        
        # 创建状态栏
        self.create_status_bar()
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLabel {
                color: #333333;
            }
        """)
        
    def create_recording_tab(self, tab_widget):
        """创建录制控制选项卡"""
        recording_widget = QWidget()
        tab_widget.addTab(recording_widget, "录制控制")
        
        layout = QVBoxLayout(recording_widget)
        
        # 设备选择组
        device_group = QGroupBox("设备选择")
        device_layout = QHBoxLayout(device_group)
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        device_layout.addWidget(QLabel("选择设备:"))
        device_layout.addWidget(self.device_combo)
        
        self.refresh_device_btn = QPushButton("刷新设备")
        self.refresh_device_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(self.refresh_device_btn)
        
        device_layout.addStretch()
        layout.addWidget(device_group)
        
        # 录制控制组
        control_group = QGroupBox("录制控制")
        control_layout = QGridLayout(control_group)
        
        # 录制模式选择
        mode_label = QLabel("录制模式:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["ADB模式 (手机端)", "PC模式 (电脑端)"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        
        control_layout.addWidget(mode_label, 0, 0)
        control_layout.addWidget(self.mode_combo, 0, 1)
        
        self.start_btn = QPushButton("开始录制")
        self.start_btn.clicked.connect(self.start_recording)
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; }")
        
        self.stop_btn = QPushButton("停止录制")
        self.stop_btn.clicked.connect(self.stop_recording)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; }")
        
        self.pause_btn = QPushButton("暂停录制")
        self.pause_btn.clicked.connect(self.pause_recording)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("QPushButton { background-color: #ff9800; }")
        
        control_layout.addWidget(self.start_btn, 1, 0)
        control_layout.addWidget(self.stop_btn, 1, 1)
        control_layout.addWidget(self.pause_btn, 1, 2)
        
        # 将录制控制组添加到主布局
        layout.addWidget(control_group)
        
        # 录制状态组
        status_group = QGroupBox("录制状态")
        status_layout = QGridLayout(status_group)
        
        self.status_label = QLabel("未开始录制")
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        self.time_label = QLabel("录制时间: 00:00:00")
        self.action_count_label = QLabel("动作数量: 0")
        self.view_mode_label = QLabel("视角模式: 快速")
        
        status_layout.addWidget(self.status_label, 0, 0, 1, 2)
        status_layout.addWidget(self.time_label, 1, 0)
        status_layout.addWidget(self.action_count_label, 1, 1)
        status_layout.addWidget(self.view_mode_label, 2, 0)
        
        layout.addWidget(status_group)
        
        # 按键映射说明组
        help_group = QGroupBox("按键映射说明")
        help_layout = QVBoxLayout(help_group)
        
        help_text = """
        移动控制:
        • W/S: 前进/后退 (点按)
        • A/D: 左转/右转 (长按)
        
        武器控制:
        • 1/2/3/4: 发射对应武器 (点按)
        
        特殊功能:
        • Q: 回血 (点按)
        • E: 热诱弹 (点按)
        
        视角控制:
        • Z: 切换到慢速视角模式
        • X: 切换到快速视角模式
        • 方向键: 控制视角方向
        """
        
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("QLabel { color: #555555; }")
        help_layout.addWidget(help_label)
        
        layout.addWidget(help_group)
        
        # 文件操作组
        file_group = QGroupBox("文件操作")
        file_layout = QGridLayout(file_group)
        
        self.save_btn = QPushButton("保存录制")
        self.save_btn.clicked.connect(self.save_recording)
        
        self.load_btn = QPushButton("加载录制")
        self.load_btn.clicked.connect(self.load_recording)
        
        self.clear_btn = QPushButton("清空录制")
        self.clear_btn.clicked.connect(self.clear_recording)
        
        file_layout.addWidget(self.save_btn, 0, 0)
        file_layout.addWidget(self.load_btn, 0, 1)
        file_layout.addWidget(self.clear_btn, 0, 2)
        
        # 回放控制区域
        replay_group = QGroupBox("回放控制")
        replay_layout = QGridLayout(replay_group)
        
        self.pc_replay_btn = QPushButton("PC端回放")
        self.mobile_replay_btn = QPushButton("手机端回放")  # 新增手机端回放按钮
        self.stop_replay_btn = QPushButton("停止回放")
        
        self.pc_replay_btn.clicked.connect(self.start_pc_replay)
        self.mobile_replay_btn.clicked.connect(self.start_mobile_replay)  # 连接手机端回放函数
        self.stop_replay_btn.clicked.connect(self.stop_replay)
        
        # 长按补偿设置
        self.compensation_label = QLabel("长按补偿(ms):")
        self.compensation_spinbox = QSpinBox()
        self.compensation_spinbox.setRange(0, 1000)
        self.compensation_spinbox.setValue(150)
        self.compensation_spinbox.valueChanged.connect(self.update_compensation)
        
        replay_layout.addWidget(self.pc_replay_btn, 0, 0)
        replay_layout.addWidget(self.mobile_replay_btn, 0, 1)
        replay_layout.addWidget(self.stop_replay_btn, 0, 2)
        replay_layout.addWidget(self.compensation_label, 1, 0)
        replay_layout.addWidget(self.compensation_spinbox, 1, 1)
        
        layout.addWidget(file_group)
        layout.addWidget(replay_group)
        
        layout.addStretch()
        
    def create_actions_tab(self, tab_widget):
        """创建动作列表选项卡"""
        actions_widget = QWidget()
        tab_widget.addTab(actions_widget, "动作列表")
        
        layout = QVBoxLayout(actions_widget)
        
        # 动作列表表格
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(6)
        self.actions_table.setHorizontalHeaderLabels([
            "序号", "时间", "类型", "按键", "位置", "持续时间"
        ])
        
        # 设置表格列宽
        header = self.actions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.actions_table)
        
        # 动作操作按钮
        action_buttons_layout = QHBoxLayout()
        
        self.refresh_actions_btn = QPushButton("刷新列表")
        self.refresh_actions_btn.clicked.connect(self.refresh_actions_table)
        
        self.export_actions_btn = QPushButton("导出动作")
        self.export_actions_btn.clicked.connect(self.export_actions)
        
        action_buttons_layout.addWidget(self.refresh_actions_btn)
        action_buttons_layout.addWidget(self.export_actions_btn)
        action_buttons_layout.addStretch()
        
        layout.addLayout(action_buttons_layout)
        
    def create_statistics_tab(self, tab_widget):
        """创建统计信息选项卡"""
        stats_widget = QWidget()
        tab_widget.addTab(stats_widget, "统计信息")
        
        layout = QVBoxLayout(stats_widget)
        
        # 统计信息显示
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFont(QFont("Consolas", 10))
        
        layout.addWidget(self.stats_text)
        
        # 刷新统计按钮
        refresh_stats_btn = QPushButton("刷新统计")
        refresh_stats_btn.clicked.connect(self.refresh_statistics)
        
        layout.addWidget(refresh_stats_btn)
        
    def create_settings_tab(self, tab_widget):
        """创建设置选项卡"""
        settings_widget = QWidget()
        tab_widget.addTab(settings_widget, "设置")
        
        layout = QVBoxLayout(settings_widget)
        
        # 录制设置组
        recording_settings_group = QGroupBox("录制设置")
        recording_settings_layout = QGridLayout(recording_settings_group)
        
        # 自动保存设置
        self.auto_save_checkbox = QCheckBox("自动保存录制")
        self.auto_save_checkbox.setChecked(True)
        
        # 保存间隔设置
        self.save_interval_spinbox = QSpinBox()
        self.save_interval_spinbox.setRange(1, 60)
        self.save_interval_spinbox.setValue(5)
        self.save_interval_spinbox.setSuffix(" 分钟")
        
        recording_settings_layout.addWidget(self.auto_save_checkbox, 0, 0)
        recording_settings_layout.addWidget(QLabel("保存间隔:"), 1, 0)
        recording_settings_layout.addWidget(self.save_interval_spinbox, 1, 1)
        
        layout.addWidget(recording_settings_group)
        
        # 关于信息
        about_group = QGroupBox("关于")
        about_layout = QVBoxLayout(about_group)
        
        about_text = """
        现代战舰战斗录制器 v1.0
        
        功能特点:
        • 实时录制游戏操作
        • 支持多种操作类型
        • 可视化操作界面
        • 详细的统计信息
        
        使用说明:
        1. 连接安卓设备并启用USB调试
        2. 选择设备并开始录制
        3. 使用键盘进行游戏操作
        4. 停止录制并保存结果
        """
        
        about_label = QLabel(about_text)
        about_label.setWordWrap(True)
        about_layout.addWidget(about_label)
        
        layout.addWidget(about_group)
        layout.addStretch()
        
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
    def setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # 每秒更新一次
        
    def refresh_devices(self):
        """刷新设备列表"""
        self.devices = ADBHelper.getDevicesList()
        self.device_combo.clear()
        
        if self.devices:
            self.device_combo.addItems(self.devices)
            self.current_device = self.devices[0]
            self.status_bar.showMessage(f"找到 {len(self.devices)} 个设备")
        else:
            self.device_combo.addItem("未找到设备")
            self.status_bar.showMessage("未找到连接的设备")
            
    def on_mode_changed(self, mode_text):
        """录制模式切换处理"""
        if "PC模式" in mode_text:
            self.device_combo.setEnabled(False)
            self.refresh_device_btn.setEnabled(False)
            # PC模式下不需要设备
            self.status_label.setText("PC模式 - 只录制船体操控")
        else:
            self.device_combo.setEnabled(True)
            self.refresh_device_btn.setEnabled(True)
            self.status_label.setText("ADB模式 - 需要连接设备")
            
    def start_recording(self):
        """开始录制"""
        try:
            # 检查录制模式
            mode_text = self.mode_combo.currentText()
            recording_mode = 'pc' if "PC模式" in mode_text else 'adb'
            
            if recording_mode == 'adb':
                # ADB模式需要检查设备
                if not self.device_combo.currentText():
                    QMessageBox.warning(self, "警告", "请先选择设备！")
                    return
                    
                device_id = self.device_combo.currentText().split()[0]
                self.current_device = device_id
                
                # 如果有现有数据，询问是否清空
                clear_existing = True
                if len(self.action_recorder.get_actions()) > 0:
                    reply = QMessageBox.question(
                        self, "清空现有录制", 
                        "检测到现有录制数据，是否清空后开始新录制？\n选择'否'将继续在现有数据基础上录制",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    clear_existing = (reply == QMessageBox.Yes)
                
                self.action_recorder.start_recording(device_id, clear_existing)
                
                # 检查是否需要回放PC录制
                reply = QMessageBox.question(
                    self, "回放PC录制", 
                    "是否需要在录制时回放PC端录制的船体操控？\n(需要先选择PC录制文件)",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # 设置默认目录为recording文件夹
                    recording_dir = os.path.join(os.path.dirname(__file__), "recording")
                    os.makedirs(recording_dir, exist_ok=True)
                    
                    pc_file, _ = QFileDialog.getOpenFileName(
                        self, "选择PC端录制文件", recording_dir, "JSON files (*.json)"
                    )
                    if pc_file:
                        self.action_recorder.replay_pc_actions(pc_file)
                        
            else:
                # PC模式
                # 如果有现有数据，询问是否清空
                clear_existing = True
                if len(self.action_recorder.get_actions()) > 0:
                    reply = QMessageBox.question(
                        self, "清空现有录制", 
                        "检测到现有录制数据，是否清空后开始新录制？\n选择'否'将继续在现有数据基础上录制",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    clear_existing = (reply == QMessageBox.Yes)
                
                self.action_recorder.start_recording("", clear_existing)
                
            # 启动键盘监听
            self.recorder_thread = RecorderThread(self.action_recorder, self.keyboard_listener)
            self.recorder_thread.start()
            
            # 根据录制模式设置键盘监听
            self.keyboard_listener.start_listening(recording_mode)
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.pause_btn.setEnabled(True)
            self.mode_combo.setEnabled(False)
            
            mode_name = "PC端录制" if recording_mode == 'pc' else "ADB录制"
            self.status_label.setText(f"正在{mode_name}...")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"开始录制失败: {str(e)}")
        
    def stop_recording(self):
        """停止录制"""
        try:
            # 停止录制
            self.action_recorder.stop_recording()
            
            # 停止录制线程
            if self.recorder_thread:
                self.recorder_thread.stop()
                self.recorder_thread.wait()
                self.recorder_thread = None
            
            # 停止键盘监听
            self.keyboard_listener.stop_listening()
            
            # 更新UI状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.mode_combo.setEnabled(True)  # 重新启用模式选择
            
            self.status_label.setText("录制已停止")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
            self.status_bar.showMessage("录制已停止")
            
            # 刷新界面显示（不清空数据）
            self.refresh_actions_table()
            self.refresh_statistics()
            
            # 强制更新状态显示
            self.update_status()
            
            # 如果有录制数据，提示保存
            if len(self.action_recorder.get_actions()) > 0:
                reply = QMessageBox.question(
                    self, "保存录制", 
                    "是否要保存录制结果？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.save_recording()
                    
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止录制失败: {str(e)}")
        
    def pause_recording(self):
        """暂停录制"""
        # 这里可以实现暂停逻辑
        pass
        
    def save_recording(self):
        """保存录制"""
        if not self.action_recorder.get_actions():
            QMessageBox.information(self, "提示", "没有录制数据可保存")
            return
        
        # 确保recording目录存在
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        # 设置默认文件名和目录
        default_filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        default_path = os.path.join(recording_dir, default_filename)
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存录制文件", 
            default_path,
            "JSON文件 (*.json)"
        )
        
        if filename:
            if self.action_recorder.save_to_file(filename):
                QMessageBox.information(self, "成功", f"录制已保存到: {filename}")
                self.status_bar.showMessage(f"录制已保存: {filename}")
            else:
                QMessageBox.critical(self, "错误", "保存失败")
                
    def load_recording(self):
        """加载录制"""
        # 设置默认目录为recording文件夹
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        filename, _ = QFileDialog.getOpenFileName(
            self, "加载录制文件", recording_dir,
            "JSON文件 (*.json)"
        )
        
        if filename:
            if self.action_recorder.load_from_file(filename):
                QMessageBox.information(self, "成功", f"录制已加载: {filename}")
                self.status_bar.showMessage(f"录制已加载: {filename}")
                self.refresh_actions_table()
                self.refresh_statistics()
            else:
                QMessageBox.critical(self, "错误", "加载失败")
                
    def clear_recording(self):
        """清空录制"""
        reply = QMessageBox.question(
            self, "确认", "确定要清空当前录制吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 如果正在录制，先停止
            if self.action_recorder.is_recording():
                self.stop_recording()
            
            # 清空录制数据
            self.action_recorder.clear_actions()
            
            # 清空键盘监听器状态
            self.keyboard_listener.clear_states()
            
            # 刷新界面
            self.refresh_actions_table()
            self.refresh_statistics()
            
            # 强制更新状态显示
            self.update_status()
            
            self.status_bar.showMessage("录制已清空")
        else:
            self.status_bar.showMessage("操作已取消")
            
    def refresh_actions_table(self):
        """刷新动作列表表格"""
        actions = self.action_recorder.get_actions()
        self.actions_table.setRowCount(len(actions))
        
        for i, action in enumerate(actions):
            self.actions_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.actions_table.setItem(i, 1, QTableWidgetItem(f"{action['timestamp']:.2f}s"))
            self.actions_table.setItem(i, 2, QTableWidgetItem(action['type']))
            self.actions_table.setItem(i, 3, QTableWidgetItem(action.get('key', '')))
            
            # 位置信息
            if 'position' in action:
                pos_text = f"{action['position']}"
            elif 'start_position' in action:
                pos_text = f"{action['start_position']} -> {action['end_position']}"
            else:
                pos_text = ""
            self.actions_table.setItem(i, 4, QTableWidgetItem(pos_text))
            
            # 持续时间
            duration = action.get('duration', 0)
            self.actions_table.setItem(i, 5, QTableWidgetItem(f"{duration}ms"))
            
    def refresh_statistics(self):
        """刷新统计信息"""
        stats = self.action_recorder.get_statistics()
        
        if not stats:
            self.stats_text.setText("暂无统计数据")
            return
            
        stats_text = f"""录制统计信息
{'='*50}

总体信息:
• 总动作数: {stats['total_actions']}
• 总时长: {stats['total_duration']:.2f} 秒

动作类型统计:
"""
        
        for action_type, count in stats['action_types'].items():
            stats_text += f"• {action_type}: {count} 次\n"
            
        stats_text += "\n按键使用统计:\n"
        for key, count in stats['key_usage'].items():
            stats_text += f"• {key}: {count} 次\n"
            
        self.stats_text.setText(stats_text)
        
    def export_actions(self):
        """导出动作列表"""
        if not self.action_recorder.get_actions():
            QMessageBox.information(self, "提示", "没有动作数据可导出")
            return
        
        # 确保recording目录存在
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        os.makedirs(recording_dir, exist_ok=True)
        
        # 设置默认文件名和目录
        default_filename = f"actions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        default_path = os.path.join(recording_dir, default_filename)
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出动作列表", 
            default_path,
            "CSV文件 (*.csv)"
        )
        
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["序号", "时间", "类型", "按键", "位置", "持续时间"])
                    
                    for i, action in enumerate(self.action_recorder.get_actions()):
                        pos_text = ""
                        if 'position' in action:
                            pos_text = f"{action['position']}"
                        elif 'start_position' in action:
                            pos_text = f"{action['start_position']} -> {action['end_position']}"
                            
                        writer.writerow([
                            i + 1,
                            f"{action['timestamp']:.2f}s",
                            action['type'],
                            action.get('key', ''),
                            pos_text,
                            f"{action.get('duration', 0)}ms"
                        ])
                        
                QMessageBox.information(self, "成功", f"动作列表已导出到: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
                
    def update_status(self):
        """更新状态信息"""
        if self.action_recorder.is_recording():
            # 更新录制时间
            current_time = self.action_recorder.get_current_time()
            hours = int(current_time // 3600)
            minutes = int((current_time % 3600) // 60)
            seconds = int(current_time % 60)
            self.time_label.setText(f"录制时间: {hours:02d}:{minutes:02d}:{seconds:02d}")
            
            # 更新动作数量
            action_count = len(self.action_recorder.get_actions())
            self.action_count_label.setText(f"动作数量: {action_count}")
            
            # 更新视角模式
            view_mode = self.keyboard_listener.get_view_mode()
            mode_text = "慢速" if view_mode == "slow" else "快速"
            self.view_mode_label.setText(f"视角模式: {mode_text}")
        else:
            # 不在录制状态时，显示当前数据状态
            action_count = len(self.action_recorder.get_actions())
            self.action_count_label.setText(f"动作数量: {action_count}")
            
            # 如果没有录制数据，重置时间显示
            if action_count == 0:
                self.time_label.setText("录制时间: 00:00:00")
            else:
                # 显示总录制时长
                total_duration = self.action_recorder.get_statistics().get('total_duration', 0)
                hours = int(total_duration // 3600)
                minutes = int((total_duration % 3600) // 60)
                seconds = int(total_duration % 60)
                self.time_label.setText(f"总时长: {hours:02d}:{minutes:02d}:{seconds:02d}")
            
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.action_recorder.is_recording():
            reply = QMessageBox.question(
                self, "确认", "正在录制中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
                
            self.stop_recording()
            
        event.accept()

    def start_pc_replay(self):
        """开始PC端回放"""
        try:
            if self.pc_replayer.is_replaying():
                QMessageBox.information(self, "提示", "PC端回放正在进行中，请先停止")
                return
                
            # 选择录制文件
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择录制文件", "./recording", "JSON files (*.json)"
            )
            
            if not file_path:
                return
                
            if not self.current_device:
                QMessageBox.warning(self, "警告", "请先选择设备")
                return
                
            # 设置设备和补偿时间
            self.pc_replayer.set_device(self.current_device)
            compensation = self.compensation_spinbox.value()
            self.pc_replayer.set_long_press_compensation(compensation)
            
            # 确认对话框
            reply = QMessageBox.question(
                self, '确认回放', 
                f'即将在设备 {self.current_device} 上回放录制文件:\n{os.path.basename(file_path)}\n\n长按补偿: +{compensation}ms\n\n确认开始回放吗？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                if self.pc_replayer.load_and_replay(file_path):
                    self.status_bar.showMessage(f"PC端回放已开始: {os.path.basename(file_path)}")
                    self.update_ui_state()
                else:
                    QMessageBox.warning(self, "错误", "PC端回放启动失败")
                    
        except Exception as e:
            QMessageBox.critical(self, "错误", f"PC端回放出错: {str(e)}")
            
    def start_mobile_replay(self):
        """开始手机端回放"""
        try:
            if self.mobile_replayer.is_replaying():
                QMessageBox.information(self, "提示", "手机端回放正在进行中，请先停止")
                return
                
            # 选择录制文件
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择录制文件", "./recording", "JSON文件 (*.json)"
            )
            
            if not file_path:
                return
                
            if not self.current_device:
                QMessageBox.warning(self, "警告", "请先选择设备")
                return
                
            # 设置设备和补偿时间
            self.mobile_replayer.set_device(self.current_device)
            compensation = self.compensation_spinbox.value()
            self.mobile_replayer.set_long_press_compensation(compensation)
            
            # 确认对话框
            reply = QMessageBox.question(
                self, '确认回放', 
                f'即将在设备 {self.current_device} 上回放录制文件:\n{os.path.basename(file_path)}\n\n长按补偿: +{compensation}ms\n\n确认开始回放吗？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                if self.mobile_replayer.load_and_replay(file_path):
                    self.status_bar.showMessage(f"手机端回放已开始: {os.path.basename(file_path)}")
                    self.update_ui_state()
                else:
                    QMessageBox.warning(self, "错误", "手机端回放启动失败")
                    
        except Exception as e:
            QMessageBox.critical(self, "错误", f"手机端回放出错: {str(e)}")
            
    def stop_replay(self):
        """停止所有回放"""
        try:
            pc_stopped = False
            mobile_stopped = False
            
            if self.pc_replayer.is_replaying():
                self.pc_replayer.stop_replay()
                pc_stopped = True
                
            if self.mobile_replayer.is_replaying():
                self.mobile_replayer.stop_replay()
                mobile_stopped = True
                
            if pc_stopped or mobile_stopped:
                self.status_bar.showMessage("回放已停止")
                self.update_ui_state()
            else:
                QMessageBox.information(self, "提示", "当前没有正在进行的回放")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止回放出错: {str(e)}")
            
    def update_compensation(self):
        """更新长按补偿时间"""
        compensation = self.compensation_spinbox.value()
        self.mobile_replayer.set_long_press_compensation(compensation)
        self.status_bar.showMessage(f"长按补偿已设置为: {compensation}ms")

    def update_ui_state(self):
        """更新界面状态"""
        recording = self.action_recorder.is_recording()
        pc_replaying = self.pc_replayer.is_replaying()
        mobile_replaying = self.mobile_replayer.is_replaying()  # 检查手机端回放状态
        
        # 更新按钮状态
        self.start_btn.setEnabled(not recording and not pc_replaying and not mobile_replaying)
        self.stop_btn.setEnabled(recording)
        self.pause_btn.setEnabled(recording)
        self.mode_combo.setEnabled(not recording and not pc_replaying and not mobile_replaying)
        self.pc_replay_btn.setEnabled(not recording and not pc_replaying and not mobile_replaying)
        self.mobile_replay_btn.setEnabled(not recording and not pc_replaying and not mobile_replaying)  # 手机端回放按钮状态
        self.stop_replay_btn.setEnabled(pc_replaying or mobile_replaying)  # 包含手机端回放状态

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("现代战舰战斗录制器")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 