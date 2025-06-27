#!/usr/bin/env python3
"""
自动化市场交易GUI界面
"""

import sys
import os
import json
import pandas as pd
from datetime import datetime
import glob
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QCheckBox, QComboBox, QMessageBox, QHeaderView,
                             QSpinBox, QDoubleSpinBox, QProgressBar, QTextEdit,
                             QScrollArea, QFrame, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont

# BidTracker模块将会导入此模块，避免循环导入
BIDTRACKER_AVAILABLE = False

# 尝试导入BidTracker模块
try:
    import BidTracker
    BIDTRACKER_AVAILABLE = True
    print("AutoTradeGUI: BidTracker模块导入成功")
except ImportError as e:
    print(f"AutoTradeGUI: BidTracker模块导入失败: {str(e)}")
    BIDTRACKER_AVAILABLE = False

class TrackingSignals(QObject):
    """追踪信号类，用于跨线程安全地更新GUI"""
    status_updated = pyqtSignal(str)
    log_added = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)  # value, maximum
    progress_visible = pyqtSignal(bool)
    tracking_started = pyqtSignal()
    tracking_stopped = pyqtSignal()
    data_refresh_requested = pyqtSignal()

class AutoTradeMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("现代战舰市场自动交易工具")
        self.setGeometry(100, 100, 1360, 800)  # 宽度从1280增加到1360，为两个新列各增加40像素
        
        # 配置文件路径
        self.filter_config_file = "./market_data/筛选预设.json"
        self.shopping_list_file = "./market_data/清单.json"
        
        # 确保市场数据目录存在
        if not os.path.exists("./market_data"):
            os.makedirs("./market_data")
        
        # 存储当前标的数据
        self.current_targets_df = None
        
        # 追踪状态变量
        self.is_tracking = False
        self.tracking_thread = None
        
        # 创建跨线程信号
        self.tracking_signals = TrackingSignals()
        self.tracking_signals.status_updated.connect(self.update_status_safe)
        self.tracking_signals.log_added.connect(self.add_log_safe)
        self.tracking_signals.progress_updated.connect(self.update_progress_safe)
        self.tracking_signals.progress_visible.connect(self.set_progress_visible_safe)
        self.tracking_signals.tracking_started.connect(self.on_tracking_started_safe)
        self.tracking_signals.tracking_stopped.connect(self.on_tracking_stopped_safe)
        self.tracking_signals.data_refresh_requested.connect(self.refresh_bid_tracker)
        
        # 初始化界面
        self.init_ui()
        
        # 加载配置
        self.load_filter_config()

    def init_ui(self):
        """初始化用户界面"""
        # 创建中央窗口和标签页
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 创建三个标签页
        self.create_target_selection_tab()
        self.create_auto_buy_tab()
        self.create_auto_sell_tab()

    def create_target_selection_tab(self):
        """创建入选标的标签页"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "入选标的")
        
        layout = QVBoxLayout(tab)
        
        # 筛选预设区域
        filter_group = self.create_filter_group()
        layout.addWidget(filter_group)
        
        # 操作按钮区域
        button_layout = QHBoxLayout()
        
        self.get_targets_btn = QPushButton("刷新获取全部标的")
        self.get_targets_btn.clicked.connect(self.get_all_targets)
        button_layout.addWidget(self.get_targets_btn)
        
        self.save_filter_btn = QPushButton("保存筛选预设")
        self.save_filter_btn.clicked.connect(self.save_filter_config)
        button_layout.addWidget(self.save_filter_btn)
        
        self.load_filter_btn = QPushButton("加载预设")
        self.load_filter_btn.clicked.connect(self.load_filter_config_manual)
        button_layout.addWidget(self.load_filter_btn)
        
        button_layout.addStretch()
        
        # 排序选择
        sort_label = QLabel("排序方式:")
        button_layout.addWidget(sort_label)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["利润率降序", "低买低卖溢价降序"])
        self.sort_combo.currentTextChanged.connect(self.on_sort_changed)
        button_layout.addWidget(self.sort_combo)
        
        layout.addLayout(button_layout)
        
        # 标的列表表格
        self.targets_table = QTableWidget()
        self.targets_table.setColumnCount(9)
        self.targets_table.setHorizontalHeaderLabels([
            "选择", "物品名称", "物品分类", "最高购入价", "低买低卖溢价", "利润率", "出价数量", "上架数量", "时间戳"
        ])
        
        # 设置表格属性
        header = self.targets_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 物品名称列自适应
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 物品分类列自适应内容
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # 时间戳列自适应内容
        
        layout.addWidget(self.targets_table)
        
        # 底部操作按钮
        bottom_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all_targets)
        bottom_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("全不选")
        self.deselect_all_btn.clicked.connect(self.deselect_all_targets)
        bottom_layout.addWidget(self.deselect_all_btn)
        
        bottom_layout.addStretch()
        
        self.add_to_tracker_btn = QPushButton("添加进购买追踪")
        self.add_to_tracker_btn.clicked.connect(self.add_selected_to_tracker)
        bottom_layout.addWidget(self.add_to_tracker_btn)
        
        layout.addLayout(bottom_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # 购买追踪清单区域
        tracking_group = self.create_tracking_list_group()
        layout.addWidget(tracking_group)
        
        # 页面初始化时自动获取标的
        QTimer.singleShot(500, self.auto_get_targets)  # 延迟500ms自动获取

    def create_filter_group(self):
        """创建筛选预设组"""
        from PyQt5.QtWidgets import QGroupBox
        
        group = QGroupBox("筛选预设项")
        layout = QGridLayout(group)
        
        # 最高购入价
        layout.addWidget(QLabel("最高购入价 ≤"), 0, 0)
        self.max_buy_price_spin = QSpinBox()
        self.max_buy_price_spin.setRange(1, 999999)
        self.max_buy_price_spin.setValue(2000)
        self.max_buy_price_spin.setSuffix(" AC")
        layout.addWidget(self.max_buy_price_spin, 0, 1)
        
        # 低买低卖溢价
        layout.addWidget(QLabel("低买低卖溢价 ≥"), 0, 2)
        self.min_spread_spin = QSpinBox()
        self.min_spread_spin.setRange(-99999, 99999)
        self.min_spread_spin.setValue(45)
        self.min_spread_spin.setSuffix(" AC")
        layout.addWidget(self.min_spread_spin, 0, 3)
        
        # 利润率
        layout.addWidget(QLabel("利润率 ≥"), 1, 0)
        self.min_profit_rate_spin = QDoubleSpinBox()
        self.min_profit_rate_spin.setRange(-100.0, 1000.0)
        self.min_profit_rate_spin.setValue(9.0)
        self.min_profit_rate_spin.setSuffix(" %")
        self.min_profit_rate_spin.setDecimals(2)
        layout.addWidget(self.min_profit_rate_spin, 1, 1)
        
        # 出价数量
        layout.addWidget(QLabel("出价数量 ≥"), 1, 2)
        self.min_bid_count_spin = QSpinBox()
        self.min_bid_count_spin.setRange(0, 100)
        self.min_bid_count_spin.setValue(3)
        self.min_bid_count_spin.setSuffix(" 个")
        layout.addWidget(self.min_bid_count_spin, 1, 3)
        
        return group

    def create_auto_buy_tab(self):
        """创建自动化购入竞价标签页"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "自动化购入竞价")
        
        layout = QVBoxLayout(tab)
        
        # 顶部控制区域
        control_layout = QHBoxLayout()
        
        self.start_tracking_btn = QPushButton("开始报价追踪")
        self.start_tracking_btn.clicked.connect(self.start_tracking)
        control_layout.addWidget(self.start_tracking_btn)
        
        self.stop_tracking_btn = QPushButton("停止追踪")
        self.stop_tracking_btn.clicked.connect(self.stop_tracking)
        self.stop_tracking_btn.setEnabled(False)  # 初始禁用
        control_layout.addWidget(self.stop_tracking_btn)
        
        self.refresh_tracker_btn = QPushButton("刷新显示")
        self.refresh_tracker_btn.clicked.connect(self.refresh_bid_tracker)
        control_layout.addWidget(self.refresh_tracker_btn)
        
        control_layout.addStretch()
        
        # 显示状态标签
        self.tracker_status_label = QLabel("状态: 未开始追踪")
        control_layout.addWidget(self.tracker_status_label)
        
        layout.addLayout(control_layout)
        
        # 进度条
        self.tracker_progress = QProgressBar()
        self.tracker_progress.setVisible(False)
        layout.addWidget(self.tracker_progress)
        
        # 主要数据区域 - 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 卡片容器
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setAlignment(Qt.AlignTop)
        
        scroll_area.setWidget(self.cards_widget)
        layout.addWidget(scroll_area)
        
        # 底部日志区域
        log_label = QLabel("追踪日志:")
        layout.addWidget(log_label)
        
        self.tracker_log = QTextEdit()
        self.tracker_log.setMaximumHeight(120)
        self.tracker_log.setReadOnly(True)
        layout.addWidget(self.tracker_log)
        
        # 存储卡片状态和数据
        self.item_cards = {}  # {item_name: card_widget}
        self.card_states = {}  # {item_name: {'expanded': True, 'last_record_count': 0}}
        
        # 自动刷新数据（当标签被激活时）
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def create_auto_sell_tab(self):
        """创建自动化售出竞价标签页"""
        tab = QWidget()
        self.tab_widget.addTab(tab, "自动化售出竞价")
        
        layout = QVBoxLayout(tab)
        
        # 占位标签
        placeholder = QLabel("自动化售出竞价功能正在开发中...")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-size: 16px;")
        layout.addWidget(placeholder)

    def load_filter_config(self):
        """加载筛选预设配置"""
        try:
            if os.path.exists(self.filter_config_file):
                with open(self.filter_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.max_buy_price_spin.setValue(config.get('max_buy_price', 2000))
                self.min_spread_spin.setValue(config.get('min_spread', 45))
                self.min_profit_rate_spin.setValue(config.get('min_profit_rate', 9.0))
                self.min_bid_count_spin.setValue(config.get('min_bid_count', 3))
                
                print("已加载筛选预设配置")
        except Exception as e:
            print(f"加载筛选预设配置失败: {str(e)}")

    def save_filter_config(self):
        """保存筛选预设配置"""
        try:
            config = {
                'max_buy_price': self.max_buy_price_spin.value(),
                'min_spread': self.min_spread_spin.value(),
                'min_profit_rate': self.min_profit_rate_spin.value(),
                'min_bid_count': self.min_bid_count_spin.value(),
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(self.filter_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "保存成功", "筛选预设配置已保存")
            print("筛选预设配置已保存")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存筛选预设配置失败: {str(e)}")

    def load_filter_config_manual(self):
        """手动加载筛选预设配置"""
        try:
            if not os.path.exists(self.filter_config_file):
                QMessageBox.warning(self, "文件不存在", "筛选预设配置文件不存在，请先保存预设")
                return
            
            with open(self.filter_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新界面控件
            self.max_buy_price_spin.setValue(config.get('max_buy_price', 2000))
            self.min_spread_spin.setValue(config.get('min_spread', 45))
            self.min_profit_rate_spin.setValue(config.get('min_profit_rate', 9.0))
            self.min_bid_count_spin.setValue(config.get('min_bid_count', 3))
            
            # 显示最后更新时间
            last_updated = config.get('last_updated', '未知')
            QMessageBox.information(self, "加载成功", 
                f"筛选预设配置已加载\n最后更新时间: {last_updated}")
            print("手动加载筛选预设配置成功")
            
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载筛选预设配置失败: {str(e)}")

    def find_latest_price_data(self):
        """查找最新的价格数据文件"""
        price_files = glob.glob("market_data/price_data_*.csv")
        if not price_files:
            return None
        return max(price_files)

    def get_all_targets(self):
        """获取全部标的"""
        try:
            # 查找最新价格数据文件
            latest_file = self.find_latest_price_data()
            if not latest_file:
                QMessageBox.warning(self, "警告", "未找到价格数据文件")
                return
            
            print(f"使用价格数据文件: {latest_file}")
            
            # 读取价格数据
            df = pd.read_csv(latest_file)
            
            # 获取筛选条件
            max_buy_price = self.max_buy_price_spin.value()
            min_spread = self.min_spread_spin.value()
            min_profit_rate = self.min_profit_rate_spin.value()
            min_bid_count = self.min_bid_count_spin.value()
            
            # 筛选数据
            filtered_df = self.filter_targets(df, max_buy_price, min_spread, min_profit_rate, min_bid_count)
            
            # 排序
            sort_method = self.sort_combo.currentText()
            if sort_method == "利润率降序":
                # 先计算利润率并排序
                filtered_df = self.calculate_and_sort_by_profit_rate(filtered_df)
            else:  # 低买低卖溢价降序
                # 确保低买低卖溢价列是数字类型
                filtered_df['低买低卖溢价_数值'] = pd.to_numeric(filtered_df['低买低卖溢价'], errors='coerce')
                filtered_df = filtered_df.sort_values('低买低卖溢价_数值', ascending=False)
            
            # 显示结果
            self.display_targets(filtered_df)
            
            # 保存到标的清单
            self.save_to_target_list(filtered_df)
            
            QMessageBox.information(self, "完成", f"已找到 {len(filtered_df)} 个符合条件的标的")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取标的时出错: {str(e)}")
            print(f"获取标的时出错: {str(e)}")

    def filter_targets(self, df, max_buy_price, min_spread, min_profit_rate, min_bid_count):
        """筛选标的"""
        filtered_df = df.copy()
        
        # 解析购买价格，获取最高价格
        def get_max_buy_price(price_str):
            if pd.isna(price_str) or price_str == '':
                return 0
            try:
                prices = []
                for price in str(price_str).split(';'):
                    clean_price = price.strip().replace(',', '').replace(' ', '')
                    if clean_price:
                        prices.append(float(clean_price))
                return max(prices) if prices else 0
            except:
                return 0
        
        # 解析利润率
        def get_profit_rate(profit_str):
            if pd.isna(profit_str) or profit_str == '':
                return 0.0
            try:
                return float(str(profit_str).replace('%', '').strip())
            except:
                return 0.0
        
        # 添加最高购买价格列
        filtered_df['最高购买价格'] = filtered_df['购买价格'].apply(get_max_buy_price)
        
        # 如果没有利润率列，则计算利润率
        if '利润率' not in filtered_df.columns:
            def calculate_profit_rate(row):
                try:
                    max_buy = row['最高购买价格']
                    spread = float(row['低买低卖溢价'])
                    if max_buy > 0:
                        return (spread / (max_buy + 1)) * 100
                    return 0.0
                except:
                    return 0.0
            
            filtered_df['利润率'] = filtered_df.apply(calculate_profit_rate, axis=1)
        else:
            filtered_df['利润率_数值'] = filtered_df['利润率'].apply(get_profit_rate)
        
        # 应用筛选条件
        # 1. 最高购入价筛选
        filtered_df = filtered_df[filtered_df['最高购买价格'] <= max_buy_price]
        
        # 2. 低买低卖溢价筛选
        filtered_df = filtered_df[pd.to_numeric(filtered_df['低买低卖溢价'], errors='coerce') >= min_spread]
        
        # 3. 利润率筛选
        if '利润率_数值' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['利润率_数值'] >= min_profit_rate]
        else:
            filtered_df = filtered_df[filtered_df['利润率'] >= min_profit_rate]
        
        # 4. 出价数量筛选
        filtered_df = filtered_df[pd.to_numeric(filtered_df['出价数量'], errors='coerce') >= min_bid_count]
        
        return filtered_df

    def calculate_and_sort_by_profit_rate(self, df):
        """计算并按利润率排序"""
        def get_profit_rate_value(profit_str):
            if pd.isna(profit_str):
                return 0.0
            try:
                if isinstance(profit_str, str) and '%' in profit_str:
                    return float(profit_str.replace('%', '').strip())
                return float(profit_str)
            except:
                return 0.0
        
        df['利润率_排序'] = df['利润率'].apply(get_profit_rate_value)
        return df.sort_values('利润率_排序', ascending=False)

    def display_targets(self, df):
        """显示标的列表"""
        self.targets_table.setRowCount(len(df))
        
        for row, (_, item) in enumerate(df.iterrows()):
            # 选择复选框
            checkbox = QCheckBox()
            self.targets_table.setCellWidget(row, 0, checkbox)
            
            # 物品名称
            self.targets_table.setItem(row, 1, QTableWidgetItem(str(item['物品名称'])))
            
            # 物品分类
            self.targets_table.setItem(row, 2, QTableWidgetItem(str(item['物品分类'])))
            
            # 最高购入价
            max_buy_price = item.get('最高购买价格', 0)
            self.targets_table.setItem(row, 3, QTableWidgetItem(f"{max_buy_price:,.0f}"))
            
            # 低买低卖溢价
            spread = item['低买低卖溢价']
            self.targets_table.setItem(row, 4, QTableWidgetItem(str(spread)))
            
            # 利润率
            profit_rate = item['利润率']
            if isinstance(profit_rate, (int, float)):
                profit_display = f"{profit_rate:.2f}%"
            else:
                profit_display = str(profit_rate)
            self.targets_table.setItem(row, 5, QTableWidgetItem(profit_display))
            
            # 出价数量
            bid_count = item['出价数量']
            self.targets_table.setItem(row, 6, QTableWidgetItem(str(bid_count)))
            
            # 上架数量
            self.targets_table.setItem(row, 7, QTableWidgetItem(str(item.get('上架数量', '未知'))))
            
            # 时间戳
            self.targets_table.setItem(row, 8, QTableWidgetItem(str(item.get('时间戳', '未知'))))
        
        # 保存数据框供后续使用
        self.current_targets_df = df

    def save_to_target_list(self, df):
        """保存到标的清单"""
        try:
            # 加载现有的购物清单
            shopping_list = self.load_shopping_list()
            
            # 清空标的清单并添加新数据
            target_list = []
            for _, item in df.iterrows():
                target_item = {
                    "物品名称": item['物品名称'],
                    "物品分类": item['物品分类'],
                    "筛选时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                target_list.append(target_item)
            
            shopping_list["标的清单"] = target_list
            
            # 保存购物清单
            with open(self.shopping_list_file, 'w', encoding='utf-8') as f:
                json.dump(shopping_list, f, ensure_ascii=False, indent=2)
            
            print(f"已保存 {len(target_list)} 个标的到清单.json")
            
        except Exception as e:
            print(f"保存标的清单时出错: {str(e)}")

    def load_shopping_list(self):
        """加载购物清单"""
        if os.path.exists(self.shopping_list_file):
            try:
                with open(self.shopping_list_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        # 返回默认结构
        return {
            "标的清单": [],
            "正在购买": [],
            "正在售出": []
        }

    def select_all_targets(self):
        """全选标的"""
        for row in range(self.targets_table.rowCount()):
            checkbox = self.targets_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)

    def deselect_all_targets(self):
        """全不选标的"""
        for row in range(self.targets_table.rowCount()):
            checkbox = self.targets_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)

    def add_selected_to_tracker(self):
        """添加选中的标的到购买追踪"""
        try:
            # 检查BidTracker是否可用
            if not BIDTRACKER_AVAILABLE:
                QMessageBox.critical(self, "模块不可用", 
                    "BidTracker模块导入失败，可能是由于CNOCR库的问题。\n"
                    "请检查Python环境或重新安装相关依赖。")
                return
            
            selected_items = []
            
            # 获取选中的项目
            for row in range(self.targets_table.rowCount()):
                checkbox = self.targets_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    item_name = self.targets_table.item(row, 1).text()
                    item_category = self.targets_table.item(row, 2).text()
                    
                    # 从当前数据框中找到完整的物品信息
                    if hasattr(self, 'current_targets_df'):
                        item_row = self.current_targets_df[
                            (self.current_targets_df['物品名称'] == item_name) & 
                            (self.current_targets_df['物品分类'] == item_category)
                        ]
                        
                        if not item_row.empty:
                            selected_items.append(item_row.iloc[0])
            
            if not selected_items:
                QMessageBox.warning(self, "警告", "请至少选择一个标的")
                return
            
            # 获取BidTracker模块
            import sys
            BidTracker = sys.modules.get('BidTracker')
            if not BidTracker:
                QMessageBox.critical(self, "模块错误", "BidTracker模块未正确加载")
                return
            
            # 使用BidTracker的add_item_to_tracker功能
            added_count = 0
            for item in selected_items:
                try:
                    BidTracker.add_item_to_tracker(item)
                    added_count += 1
                except Exception as e:
                    print(f"添加物品 '{item['物品名称']}' 时出错: {str(e)}")
            
            QMessageBox.information(self, "完成", f"已成功添加 {added_count} 个物品到购买追踪")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加到购买追踪时出错: {str(e)}")

    def on_sort_changed(self):
        """当排序方式改变时重新排序表格"""
        if self.current_targets_df is not None and not self.current_targets_df.empty:
            self.resort_and_display_targets()

    def resort_and_display_targets(self):
        """重新排序并显示标的"""
        if self.current_targets_df is None or self.current_targets_df.empty:
            return
        
        try:
            # 获取当前选择的排序方式
            sort_method = self.sort_combo.currentText()
            
            # 创建数据副本进行排序
            sorted_df = self.current_targets_df.copy()
            
            if sort_method == "利润率降序":
                # 按利润率排序
                sorted_df = self.calculate_and_sort_by_profit_rate(sorted_df)
            else:  # 低买低卖溢价降序
                # 确保低买低卖溢价列是数字类型
                sorted_df['低买低卖溢价_数值'] = pd.to_numeric(sorted_df['低买低卖溢价'], errors='coerce')
                sorted_df = sorted_df.sort_values('低买低卖溢价_数值', ascending=False)
            
            # 更新表格显示
            self.display_targets(sorted_df)
            
            print(f"已按'{sort_method}'重新排序表格")
            
        except Exception as e:
            print(f"重新排序时出错: {str(e)}")

    def on_tab_changed(self, index):
        """当标签页切换时的处理"""
        if index == 1:  # 自动化购入竞价标签页的索引是1
            self.refresh_bid_tracker()

    def refresh_bid_tracker(self):
        """刷新报价追踪数据"""
        try:
            print(f"[DEBUG] 开始刷新报价追踪数据...")
            self.tracker_status_label.setText("状态: 正在加载数据...")
            self.tracker_progress.setVisible(True)
            self.tracker_progress.setRange(0, 0)  # 无限进度条
            
            # 检查报价追踪文件是否存在
            tracker_file = "./market_data/报价追踪.csv"
            if not os.path.exists(tracker_file):
                print(f"[DEBUG] 报价追踪文件不存在: {tracker_file}")
                self.tracker_status_label.setText("状态: 未找到报价追踪文件")
                self.tracker_progress.setVisible(False)
                return
            
            print(f"[DEBUG] 读取报价追踪文件: {tracker_file}")
            # 读取报价追踪数据
            df = pd.read_csv(tracker_file)
            print(f"[DEBUG] 读取到数据形状: {df.shape}")
            
            if df.empty:
                print(f"[DEBUG] 报价追踪文件为空")
                self.tracker_status_label.setText("状态: 报价追踪文件为空")
                self.tracker_progress.setVisible(False)
                # 清空现有卡片
                self.clear_all_cards()
                return
            
            # 按物品名称分组，获取每个物品的历史数据
            print(f"[DEBUG] 开始处理数据分组...")
            grouped_data = self.process_tracker_data_for_cards(df)
            print(f"[DEBUG] 分组完成，共 {len(grouped_data)} 个物品")
            
            if not grouped_data:
                print(f"[DEBUG] 警告: 分组数据为空")
                self.tracker_status_label.setText("状态: 没有有效的追踪数据")
                self.tracker_progress.setVisible(False)
                # 清空现有卡片
                self.clear_all_cards()
                return
            
            # 更新或创建卡片
            print(f"[DEBUG] 开始更新卡片...")
            self.update_tracking_cards_safe(grouped_data)
            print(f"[DEBUG] 卡片更新完成")
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            success_msg = f"[{timestamp}] 数据刷新完成，共 {len(grouped_data)} 个物品"
            print(f"[DEBUG] {success_msg}")
            self.tracking_signals.log_added.emit(success_msg)
            
        except Exception as e:
            error_msg = f"刷新报价追踪数据时出错: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tracking_signals.log_added.emit(f"[{timestamp}] 刷新失败: {str(e)}")
            
            # 确保界面状态正确
            self.tracker_status_label.setText(f"状态: 刷新失败 - {str(e)}")
            self.tracker_progress.setVisible(False)
        
        finally:
            # 确保进度条总是被隐藏
            self.tracker_progress.setVisible(False)

    def clear_all_cards(self):
        """清空所有卡片"""
        try:
            print(f"[DEBUG] 开始清空所有卡片...")
            
            if hasattr(self, 'item_cards'):
                for item_name, card in list(self.item_cards.items()):
                    try:
                        if card and card.parent():
                            card.setParent(None)
                            card.deleteLater()
                        del self.item_cards[item_name]
                    except Exception as e:
                        print(f"[ERROR] 删除卡片 {item_name} 时出错: {str(e)}")
                
                self.item_cards.clear()
            
            if hasattr(self, 'card_states'):
                self.card_states.clear()
            
            # 强制刷新布局
            if hasattr(self, 'cards_widget') and self.cards_widget:
                self.cards_widget.update()
                self.cards_widget.repaint()
            
            print(f"[DEBUG] 所有卡片已清空")
            
        except Exception as e:
            print(f"[ERROR] 清空卡片时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def process_tracker_data_for_cards(self, df):
        """处理报价追踪数据用于卡片显示"""
        grouped_data = []
        
        # 按物品名称分组
        for item_name, item_group in df.groupby('物品名称'):
            # 按时间戳排序
            item_group = item_group.sort_values('时间戳')
            
            if len(item_group) < 1:
                continue
            
            # 获取所有历史记录用于计算被竞价次数
            item_records = []
            for _, row in item_group.iterrows():
                record = self.parse_price_record(row)
                item_records.append(record)
            
            # 获取最新数据
            latest_record = item_records[-1] if item_records else None
            
            # 计算被竞价次数和其他统计信息
            competition_stats = self.calculate_competition_stats(item_records)
            
            grouped_data.append({
                'item_name': item_name,
                'category': item_records[0]['category'] if item_records else '',
                'latest_record': latest_record,
                'all_records': item_records,
                'competition_stats': competition_stats,
                'record_count': len(item_records)
            })
        
        return grouped_data

    def parse_price_record(self, row):
        """解析价格记录"""
        record = {
            'category': row['物品分类'],
            'timestamp': row['时间戳'],
            'spread': row.get('低买低卖溢价', 'N/A'),
            'profit_rate': row.get('利润率', 'N/A'),
            'bid_count': row.get('出价数量', 0),
            'listing_count': row.get('上架数量', 0),
            'buying_prices': [],
            'selling_prices': [],
            'own_buying_price': row.get('本人购买价格', ''),
            'own_selling_price': row.get('本人售出价格', '')
        }
        
        # 解析购买价格 - 添加空值检查
        buying_price_data = row.get('购买价格', '')
        if pd.notna(buying_price_data) and buying_price_data and str(buying_price_data).strip():
            for price in str(buying_price_data).split(';'):
                clean_price = price.strip().replace(',', '')
                if clean_price:
                    try:
                        record['buying_prices'].append(int(clean_price))
                    except ValueError:
                        print(f"无法解析购买价格: {price}")
        
        # 解析出售价格 - 添加空值检查
        selling_price_data = row.get('出售价格', '')
        if pd.notna(selling_price_data) and selling_price_data and str(selling_price_data).strip():
            for price in str(selling_price_data).split(';'):
                clean_price = price.strip().replace(',', '')
                if clean_price:
                    try:
                        record['selling_prices'].append(int(clean_price))
                    except ValueError:
                        print(f"无法解析出售价格: {price}")
        
        # 排序价格
        record['buying_prices'].sort()
        record['selling_prices'].sort()
        
        return record

    def calculate_row_competition(self, record, previous_record=None):
        """计算单行的被竞价次数：相比上一行新增的竞价数量"""
        try:
            # 获取本行的本人购买价格
            own_buying_price_str = record.get('own_buying_price', '')
            if not own_buying_price_str or own_buying_price_str == '':
                # 如果没有本人购买价格，返回0
                return 0
            
            # 解析本行的本人购买价格
            try:
                own_buying_price = float(str(own_buying_price_str).replace(',', '').strip())
            except:
                return 0
            
            # 获取本行中大于本人购买价格的购买价格集合
            current_competing_prices = set()
            buying_prices = record.get('buying_prices', [])
            
            for price in buying_prices:
                if price > own_buying_price:
                    current_competing_prices.add(price)
            
            # 如果没有上一行，直接返回当前行的竞价数量
            if not previous_record:
                return len(current_competing_prices)
            
            # 获取上一行的本人购买价格
            prev_own_buying_price_str = previous_record.get('own_buying_price', '')
            if not prev_own_buying_price_str or prev_own_buying_price_str == '':
                # 如果上一行没有本人购买价格，返回当前行的竞价数量
                return len(current_competing_prices)
            
            # 解析上一行的本人购买价格
            try:
                prev_own_buying_price = float(str(prev_own_buying_price_str).replace(',', '').strip())
            except:
                # 如果上一行本人购买价格解析失败，返回当前行的竞价数量
                return len(current_competing_prices)
            
            # 获取上一行中大于上一行本人购买价格的购买价格集合
            previous_competing_prices = set()
            prev_buying_prices = previous_record.get('buying_prices', [])
            
            for price in prev_buying_prices:
                if price > prev_own_buying_price:
                    previous_competing_prices.add(price)
            
            # 计算新增的竞价：当前行的竞价价格集合 - 上一行的竞价价格集合
            new_competing_prices = current_competing_prices - previous_competing_prices
            
            print(f"[DEBUG] 竞价计算 - 当前竞价价格: {current_competing_prices}, 上一行竞价价格: {previous_competing_prices}, 新增: {new_competing_prices}")
            
            return len(new_competing_prices)
            
        except Exception as e:
            print(f"[ERROR] 计算行被竞价时出错: {str(e)}")
            return 0

    def calculate_competition_stats(self, item_records):
        """计算竞争统计信息"""
        try:
            if not item_records:
                return {
                    'latest_competitions': 0,
                    'spread_trend': 'stable',
                    'profit_trend': 'stable',
                    'total_competitions': 0
                }
            
            # 计算每行的被竞价并加总
            total_competitions = 0
            for i, record in enumerate(item_records):
                # 传递上一行记录用于计算新增竞价
                previous_record = item_records[i-1] if i > 0 else None
                row_competition = self.calculate_row_competition(record, previous_record)
                total_competitions += row_competition
            
            # 获取最新记录的竞争次数
            if len(item_records) >= 2:
                latest_competitions = self.calculate_row_competition(item_records[-1], item_records[-2])
            elif len(item_records) == 1:
                latest_competitions = self.calculate_row_competition(item_records[-1], None)
            else:
                latest_competitions = 0
            
            # 计算趋势
            spread_trend = 'stable'
            profit_trend = 'stable'
            
            if len(item_records) >= 2:
                current_spread = self.parse_numeric_value(item_records[-1]['spread'])
                previous_spread = self.parse_numeric_value(item_records[-2]['spread'])
                
                if current_spread is not None and previous_spread is not None:
                    if current_spread > previous_spread:
                        spread_trend = 'up'
                    elif current_spread < previous_spread:
                        spread_trend = 'down'
                
                current_profit = self.parse_numeric_value(item_records[-1]['profit_rate'])
                previous_profit = self.parse_numeric_value(item_records[-2]['profit_rate'])
                
                if current_profit is not None and previous_profit is not None:
                    if current_profit > previous_profit:
                        profit_trend = 'up'
                    elif current_profit < previous_profit:
                        profit_trend = 'down'
            
            return {
                'latest_competitions': latest_competitions,
                'spread_trend': spread_trend,
                'profit_trend': profit_trend,
                'total_competitions': total_competitions  # 使用计算出的总竞价数
            }
        except Exception as e:
            print(f"[ERROR] 计算竞争统计信息时出错: {str(e)}")
            return {
                'latest_competitions': 0,
                'spread_trend': 'stable',
                'profit_trend': 'stable',
                'total_competitions': 0
            }

    def parse_numeric_value(self, value):
        """解析数值"""
        try:
            # 处理百分比
            if isinstance(value, str) and '%' in value:
                return float(value.replace('%', ''))
            # 处理逗号分隔的数字
            if isinstance(value, str):
                value = value.replace(',', '').replace(' ', '')
            return float(value)
        except:
            return None

    def update_tracking_cards_safe(self, grouped_data):
        """安全地更新追踪卡片，加强异常处理"""
        try:
            print(f"[DEBUG] 进入update_tracking_cards_safe，数据量: {len(grouped_data)}")
            
            if not hasattr(self, 'item_cards'):
                self.item_cards = {}
            if not hasattr(self, 'card_states'):
                self.card_states = {}
            
            # 获取现有的物品列表
            existing_items = set(self.item_cards.keys())
            current_items = set([item['item_name'] for item in grouped_data])
            
            print(f"[DEBUG] 现有物品: {existing_items}")
            print(f"[DEBUG] 当前物品: {current_items}")
            
            # 删除不再存在的物品卡片
            items_to_remove = existing_items - current_items
            for item_name in items_to_remove:
                try:
                    print(f"[DEBUG] 删除卡片: {item_name}")
                    if item_name in self.item_cards:
                        card = self.item_cards[item_name]
                        if card and card.parent():
                            card.setParent(None)
                            card.deleteLater()
                        del self.item_cards[item_name]
                    if item_name in self.card_states:
                        del self.card_states[item_name]
                except Exception as e:
                    print(f"[ERROR] 删除卡片 {item_name} 时出错: {str(e)}")
            
            # 更新或创建卡片
            for item_data in grouped_data:
                try:
                    item_name = item_data['item_name']
                    print(f"[DEBUG] 处理物品: {item_name}")
                    
                    if item_name in self.item_cards:
                        # 更新现有卡片
                        print(f"[DEBUG] 更新现有卡片: {item_name}")
                        self.update_existing_card_safe(item_name, item_data)
                    else:
                        # 创建新卡片
                        print(f"[DEBUG] 创建新卡片: {item_name}")
                        card = self.create_item_card_safe(item_data)
                        if card:
                            self.item_cards[item_name] = card
                            self.card_states[item_name] = {
                                'expanded': True, 
                                'last_record_count': len(item_data['all_records'])
                            }
                            self.cards_layout.addWidget(card)
                            print(f"[DEBUG] 新卡片已添加到布局: {item_name}")
                        else:
                            print(f"[ERROR] 创建卡片失败: {item_name}")
                            
                except Exception as e:
                    print(f"[ERROR] 处理物品 {item_data.get('item_name', 'Unknown')} 时出错: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            # 更新状态
            final_count = len(self.item_cards)
            status_text = f"状态: 已加载 {final_count} 个追踪物品"
            print(f"[DEBUG] {status_text}")
            self.tracker_status_label.setText(status_text)
            self.tracker_progress.setVisible(False)
            
            # 强制刷新布局
            if hasattr(self, 'cards_widget') and self.cards_widget:
                self.cards_widget.update()
                self.cards_widget.repaint()
            
        except Exception as e:
            print(f"[ERROR] update_tracking_cards_safe 出错: {str(e)}")
            import traceback
            traceback.print_exc()
            self.tracker_status_label.setText(f"状态: 更新卡片失败 - {str(e)}")
            self.tracker_progress.setVisible(False)

    def update_existing_card_safe(self, item_name, item_data):
        """安全地更新现有卡片"""
        try:
            if item_name not in self.item_cards:
                print(f"[DEBUG] 卡片不存在，跳过更新: {item_name}")
                return
            
            card = self.item_cards[item_name]
            if not card:
                print(f"[DEBUG] 卡片对象为空，跳过更新: {item_name}")
                return
                
            state = self.card_states.get(item_name, {'expanded': True, 'last_record_count': 0})
            
            # 检查是否有新记录
            new_record_count = len(item_data['all_records'])
            last_record_count = state['last_record_count']
            
            print(f"[DEBUG] 更新卡片 {item_name}: 新记录数={new_record_count}, 上次记录数={last_record_count}")
            
            if new_record_count > last_record_count:
                # 有新记录，重建卡片
                print(f"[DEBUG] 有新记录，重建卡片内容: {item_name}")
                self.rebuild_card_content_safe(card, item_data)
                state['last_record_count'] = new_record_count
                
                # 显示新数据提示
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] {item_name} 新增 {new_record_count - last_record_count} 条记录")
            else:
                # 只更新头部信息
                print(f"[DEBUG] 只更新头部信息: {item_name}")
                self.update_card_header_safe(card, item_data)
                
        except Exception as e:
            print(f"[ERROR] 更新现有卡片 {item_name} 时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def rebuild_card_content_safe(self, card, item_data):
        """安全地重建卡片内容"""
        try:
            print(f"[DEBUG] 重建卡片内容: {item_data['item_name']}")
            
            # 获取现有布局
            layout = card.layout()
            if layout:
                print(f"[DEBUG] 清理现有布局...")
                
                # 递归删除所有子widget和子布局
                def clear_layout_recursive(layout_to_clear):
                    if not layout_to_clear:
                        return
                    while layout_to_clear.count():
                        child = layout_to_clear.takeAt(0)
                        if child.widget():
                            widget = child.widget()
                            widget.setParent(None)
                            widget.deleteLater()
                        elif child.layout():
                            clear_layout_recursive(child.layout())
                
                # 清理布局内容
                clear_layout_recursive(layout)
                
                # 不要删除布局本身，只是清空内容
                print(f"[DEBUG] 布局内容已清空，准备重新构建...")
            else:
                # 如果没有布局，创建一个新的
                print(f"[DEBUG] 创建新布局...")
                layout = QVBoxLayout(card)
            
            # 重新构建卡片内容
            self.build_card_content_with_layout(layout, item_data)
            print(f"[DEBUG] 卡片内容重建完成: {item_data['item_name']}")
                
        except Exception as e:
            print(f"[ERROR] 重建卡片内容时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 如果重建失败，尝试创建一个全新的卡片
            try:
                print(f"[DEBUG] 重建失败，尝试创建全新卡片...")
                # 移除所有现有内容
                if card.layout():
                    layout = card.layout()
                    while layout.count():
                        child = layout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                
                # 创建简单的错误显示
                error_layout = QVBoxLayout(card)
                error_label = QLabel(f"重建失败: {item_data['item_name']}")
                error_label.setStyleSheet("color: red;")
                error_layout.addWidget(error_label)
                
            except Exception as fatal_error:
                print(f"[FATAL] 创建错误卡片也失败: {str(fatal_error)}")

    def build_card_content_with_layout(self, layout, item_data):
        """使用指定布局构建卡片内容"""
        try:
            print(f"[DEBUG] 开始构建卡片内容: {item_data['item_name']}")
            
            # 卡片头部
            header_widget = QWidget()
            header_layout = QHBoxLayout(header_widget)
            header_layout.setContentsMargins(0, 0, 0, 0)
            
            self.build_card_header(header_layout, item_data)
            
            layout.addWidget(header_widget)
            
            # 详细信息区域（始终显示）
            detail_widget = QWidget()
            detail_layout = QVBoxLayout(detail_widget)
            detail_layout.setContentsMargins(0, 10, 0, 0)
            
            # 创建详细信息内容
            self.build_detail_content(detail_layout, item_data)
            
            layout.addWidget(detail_widget)
            
            print(f"[DEBUG] 卡片内容构建完成: {item_data['item_name']}")
            
        except Exception as e:
            print(f"[ERROR] 构建卡片内容时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 如果构建失败，添加错误信息
            try:
                error_label = QLabel(f"构建失败: {str(e)}")
                error_label.setStyleSheet("color: red;")
                layout.addWidget(error_label)
            except:
                pass

    def update_card_header_safe(self, card, item_data):
        """安全地更新卡片头部信息"""
        try:
            print(f"[DEBUG] 更新卡片头部: {item_data['item_name']}")
            
            # 找到头部布局并更新
            layout = card.layout()
            if layout and layout.count() > 0:
                header_widget = layout.itemAt(0).widget()
                if header_widget:
                    # 重建头部
                    header_layout = header_widget.layout()
                    if header_layout:
                        # 安全地清空头部
                        while header_layout.count():
                            child = header_layout.takeAt(0)
                            if child.widget():
                                widget = child.widget()
                                widget.setParent(None)
                                widget.deleteLater()
                        
                        # 重建头部内容
                        self.build_card_header(header_layout, item_data)
                        print(f"[DEBUG] 卡片头部更新完成: {item_data['item_name']}")
                    else:
                        print(f"[ERROR] 头部布局为空: {item_data['item_name']}")
                else:
                    print(f"[ERROR] 头部widget为空: {item_data['item_name']}")
            else:
                print(f"[ERROR] 卡片布局为空或无内容: {item_data['item_name']}")
                
        except Exception as e:
            print(f"[ERROR] 更新卡片头部时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def create_item_card_safe(self, item_data):
        """安全地创建物品卡片"""
        try:
            print(f"[DEBUG] 创建物品卡片: {item_data['item_name']}")
            
            # 主卡片容器
            card = QGroupBox()
            card.setStyleSheet("""
                QGroupBox {
                    border: 2px solid #ddd;
                    border-radius: 8px;
                    margin: 5px;
                    padding: 15px;
                    background-color: #ffffff;
                }
                QGroupBox:hover {
                    border-color: #007acc;
                    background-color: #f8f9fa;
                }
            """)
            
            # 创建布局 - 注意：不要在build_card_content中再次创建布局
            layout = QVBoxLayout(card)
            print(f"[DEBUG] 为新卡片创建了布局")
            
            # 构建卡片内容，传入已经创建的布局
            self.build_card_content_with_layout(layout, item_data)
            
            print(f"[DEBUG] 物品卡片创建完成: {item_data['item_name']}")
            return card
            
        except Exception as e:
            print(f"[ERROR] 创建物品卡片时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def start_tracking(self):
        """开始追踪"""
        if self.is_tracking:
            return
            
        try:
            # 检查BidTracker模块是否可用
            if not BIDTRACKER_AVAILABLE:
                QMessageBox.warning(self, "错误", "BidTracker模块不可用")
                return
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tracking_signals.log_added.emit(f"[{timestamp}] 开始启动报价追踪...")
            
            self.is_tracking = True
            
            # 启动追踪线程
            self.tracking_thread = BidTracker.start_gui_tracking(self.on_tracking_callback)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tracking_signals.log_added.emit(f"[{timestamp}] 报价追踪已启动，开始循环监控")
            
            # 更新按钮状态
            self.start_tracking_btn.setEnabled(False)
            self.stop_tracking_btn.setEnabled(True)
            
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tracking_signals.log_added.emit(f"[{timestamp}] 启动失败: {str(e)}")
            QMessageBox.critical(self, "启动失败", str(e))
            self.is_tracking = False
            self.start_tracking_btn.setEnabled(True)
            self.stop_tracking_btn.setEnabled(False)

    def stop_tracking(self):
        """停止追踪"""
        if not self.is_tracking:
            return
            
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tracking_signals.log_added.emit(f"[{timestamp}] 正在停止报价追踪...")
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tracking_signals.log_added.emit(f"[{timestamp}] 停止追踪时出错: {str(e)}")
        
        # 调用BidTracker的停止函数
        if BIDTRACKER_AVAILABLE:
            BidTracker.stop_gui_tracking()
        
        self.is_tracking = False
        self.start_tracking_btn.setEnabled(True)
        self.stop_tracking_btn.setEnabled(False)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.tracking_signals.log_added.emit(f"[{timestamp}] 报价追踪已停止")

    def on_tracking_callback(self, event_type, data):
        """处理BidTracker的回调事件"""
        try:
            if event_type == 'tracking_started':
                self.tracking_signals.tracking_started.emit()
                self.tracking_signals.status_updated.emit(f"追踪中 ({data['total_items']} 个物品)")
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] 开始追踪 {data['total_items']} 个物品")
                
            elif event_type == 'cycle_started':
                self.tracking_signals.status_updated.emit(f"第 {data['cycle']} 轮追踪")
                self.tracking_signals.progress_updated.emit(0, data['total_items'])
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] 开始第 {data['cycle']} 轮追踪")
                
            elif event_type == 'processing_item':
                status = f"第 {data['cycle']} 轮 - 处理 {data['item_name']} ({data['item_index']}/{data['total_items']})"
                self.tracking_signals.status_updated.emit(status)
                self.tracking_signals.progress_updated.emit(data['item_index'], data['total_items'])
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] [{data['cycle']}-{data['item_index']}] 处理 {data['item_name']}")
                
            elif event_type == 'data_updated':
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] ✓ {data['item_name']} 数据已更新 ({data['timestamp']})")
                # 刷新表格显示
                self.tracking_signals.data_refresh_requested.emit()
                
            elif event_type == 'data_unchanged':
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] - {data['item_name']} 数据无变化")
                
            elif event_type == 'item_not_found':
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] ✗ 未找到物品: {data['item_name']}")
                
            elif event_type == 'cycle_completed':
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] 第 {data['cycle']} 轮追踪完成")
                
            elif event_type == 'tracking_stopped':
                self.tracking_signals.tracking_stopped.emit()
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] 追踪已停止 (共完成 {data['total_cycles']} 轮)")
                # 重置界面状态
                self.is_tracking = False
                
            elif event_type == 'error':
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.tracking_signals.log_added.emit(f"[{timestamp}] 错误: {data['message']}")
                # 错误消息框需要在主线程中显示
                QMessageBox.critical(self, "追踪错误", data['message'])
                
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.tracking_signals.log_added.emit(f"[{timestamp}] 处理回调事件时出错: {str(e)}")

    def update_status_safe(self, status):
        """安全更新状态标签"""
        self.tracker_status_label.setText(f"状态: {status}")

    def add_log_safe(self, log):
        """安全添加日志"""
        self.tracker_log.append(log)

    def update_progress_safe(self, value, maximum):
        """安全更新进度条"""
        self.tracker_progress.setRange(0, maximum)
        self.tracker_progress.setValue(value)

    def set_progress_visible_safe(self, visible):
        """安全设置进度条可见性"""
        self.tracker_progress.setVisible(visible)

    def on_tracking_started_safe(self):
        """安全处理追踪开始"""
        self.start_tracking_btn.setEnabled(False)
        self.stop_tracking_btn.setEnabled(True)
        self.tracker_status_label.setText("状态: 正在启动追踪...")
        self.tracker_progress.setVisible(True)
        self.tracker_progress.setRange(0, 0)  # 无限进度条

    def on_tracking_stopped_safe(self):
        """安全处理追踪停止"""
        self.start_tracking_btn.setEnabled(True)
        self.stop_tracking_btn.setEnabled(False)
        self.tracker_status_label.setText("状态: 已停止追踪")
        self.tracker_progress.setVisible(False)

    def create_tracking_list_group(self):
        """创建购买追踪清单组"""
        group = QGroupBox("购买追踪清单")
        layout = QVBoxLayout(group)
        
        # 控制按钮区域
        control_layout = QHBoxLayout()
        
        self.refresh_tracking_btn = QPushButton("刷新追踪清单")
        self.refresh_tracking_btn.clicked.connect(self.refresh_tracking_list)
        control_layout.addWidget(self.refresh_tracking_btn)
        
        control_layout.addStretch()
        
        tracking_status_label = QLabel("状态:")
        control_layout.addWidget(tracking_status_label)
        
        self.tracking_list_status = QLabel("未加载")
        control_layout.addWidget(self.tracking_list_status)
        
        layout.addLayout(control_layout)
        
        # 追踪清单表格
        self.tracking_list_table = QTableWidget()
        self.tracking_list_table.setColumnCount(4)
        self.tracking_list_table.setHorizontalHeaderLabels([
            "物品名称", "物品分类", "添加时间", "操作"
        ])
        
        # 设置表格属性
        header = self.tracking_list_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 物品名称列自适应
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 物品分类列自适应内容
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 添加时间列自适应内容
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 操作列自适应内容
        
        # 设置较小的高度
        self.tracking_list_table.setMaximumHeight(200)
        
        layout.addWidget(self.tracking_list_table)
        
        return group

    def auto_get_targets(self):
        """自动获取标的（页面初始化时调用）"""
        try:
            # 静默获取，不显示消息框
            latest_file = self.find_latest_price_data()
            if not latest_file:
                self.tracking_list_status.setText("未找到价格数据文件")
                return
            
            print(f"自动加载价格数据文件: {latest_file}")
            
            # 读取价格数据
            df = pd.read_csv(latest_file)
            
            # 获取筛选条件
            max_buy_price = self.max_buy_price_spin.value()
            min_spread = self.min_spread_spin.value()
            min_profit_rate = self.min_profit_rate_spin.value()
            min_bid_count = self.min_bid_count_spin.value()
            
            # 筛选数据
            filtered_df = self.filter_targets(df, max_buy_price, min_spread, min_profit_rate, min_bid_count)
            
            # 排序
            sort_method = self.sort_combo.currentText()
            if sort_method == "利润率降序":
                filtered_df = self.calculate_and_sort_by_profit_rate(filtered_df)
            else:
                filtered_df['低买低卖溢价_数值'] = pd.to_numeric(filtered_df['低买低卖溢价'], errors='coerce')
                filtered_df = filtered_df.sort_values('低买低卖溢价_数值', ascending=False)
            
            # 显示结果
            self.display_targets(filtered_df)
            
            # 保存到标的清单
            self.save_to_target_list(filtered_df)
            
            print(f"自动获取完成，找到 {len(filtered_df)} 个符合条件的标的")
            
            # 同时刷新追踪清单
            self.refresh_tracking_list()
            
        except Exception as e:
            print(f"自动获取标的时出错: {str(e)}")
            self.tracking_list_status.setText(f"加载失败: {str(e)}")

    def refresh_tracking_list(self):
        """刷新购买追踪清单"""
        try:
            self.tracking_list_status.setText("正在加载...")
            
            # 读取购物清单
            shopping_list = self.load_shopping_list()
            buying_items = shopping_list.get("正在购买", [])
            
            # 更新表格
            self.tracking_list_table.setRowCount(len(buying_items))
            
            for row, item in enumerate(buying_items):
                # 物品名称
                self.tracking_list_table.setItem(row, 0, QTableWidgetItem(item.get("物品名称", "")))
                
                # 物品分类
                self.tracking_list_table.setItem(row, 1, QTableWidgetItem(item.get("物品分类", "")))
                
                # 添加时间
                add_time = item.get("添加时间", "")
                self.tracking_list_table.setItem(row, 2, QTableWidgetItem(add_time))
                
                # 操作按钮
                delete_btn = QPushButton("删除")
                delete_btn.setStyleSheet("QPushButton { background-color: #ff6b6b; color: white; }")
                delete_btn.clicked.connect(lambda checked, r=row: self.delete_tracking_item(r))
                self.tracking_list_table.setCellWidget(row, 3, delete_btn)
            
            self.tracking_list_status.setText(f"已加载 {len(buying_items)} 个追踪物品")
            
        except Exception as e:
            print(f"刷新追踪清单时出错: {str(e)}")
            self.tracking_list_status.setText(f"刷新失败: {str(e)}")

    def delete_tracking_item(self, row):
        """删除追踪物品"""
        try:
            # 获取要删除的物品信息
            item_name = self.tracking_list_table.item(row, 0).text()
            item_category = self.tracking_list_table.item(row, 1).text()
            
            # 确认删除
            reply = QMessageBox.question(self, "确认删除", 
                f"确定要删除追踪物品 '{item_name}' 吗？\n\n"
                "这将同时从购物清单和报价追踪记录中删除该物品的所有数据。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            
            if reply != QMessageBox.Yes:
                return
            
            # 从JSON购物清单中删除
            success1 = self.remove_from_shopping_list(item_name, item_category)
            
            # 从报价追踪CSV中删除
            success2 = self.remove_from_bid_tracker_csv(item_name, item_category)
            
            if success1 and success2:
                QMessageBox.information(self, "删除成功", 
                    f"已成功删除 '{item_name}' 的所有追踪数据")
                # 刷新列表
                self.refresh_tracking_list()
            else:
                QMessageBox.warning(self, "删除部分成功", 
                    f"删除 '{item_name}' 时部分操作失败，请检查日志")
                
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"删除追踪物品时出错: {str(e)}")
            print(f"删除追踪物品时出错: {str(e)}")

    def remove_from_shopping_list(self, item_name, item_category):
        """从购物清单JSON中删除物品"""
        try:
            shopping_list = self.load_shopping_list()
            
            # 从正在购买列表中删除
            buying_items = shopping_list.get("正在购买", [])
            original_count = len(buying_items)
            
            shopping_list["正在购买"] = [
                item for item in buying_items 
                if not (item.get("物品名称") == item_name and item.get("物品分类") == item_category)
            ]
            
            removed_count = original_count - len(shopping_list["正在购买"])
            
            if removed_count > 0:
                # 保存更新后的购物清单
                with open(self.shopping_list_file, 'w', encoding='utf-8') as f:
                    json.dump(shopping_list, f, ensure_ascii=False, indent=2)
                
                print(f"已从购物清单中删除 {removed_count} 个 '{item_name}' 条目")
                return True
            else:
                print(f"购物清单中未找到物品 '{item_name}'")
                return True  # 没找到也算成功
                
        except Exception as e:
            print(f"从购物清单删除物品时出错: {str(e)}")
            return False

    def remove_from_bid_tracker_csv(self, item_name, item_category):
        """从报价追踪CSV中删除物品的所有记录"""
        try:
            tracker_file = "./market_data/报价追踪.csv"
            
            if not os.path.exists(tracker_file):
                print("报价追踪文件不存在")
                return True  # 文件不存在也算成功
            
            # 读取CSV文件
            df = pd.read_csv(tracker_file)
            original_count = len(df)
            
            # 删除匹配的记录
            df_filtered = df[~((df['物品名称'] == item_name) & (df['物品分类'] == item_category))]
            removed_count = original_count - len(df_filtered)
            
            if removed_count > 0:
                # 保存更新后的CSV
                df_filtered.to_csv(tracker_file, index=False, encoding='utf-8')
                print(f"已从报价追踪文件中删除 {removed_count} 条 '{item_name}' 记录")
            else:
                print(f"报价追踪文件中未找到物品 '{item_name}' 的记录")
            
            return True
            
        except Exception as e:
            print(f"从报价追踪文件删除记录时出错: {str(e)}")
            return False

    def get_trend_color(self, trend):
        """获取趋势颜色"""
        if trend == 'up':
            return "#28a745"  # 绿色
        elif trend == 'down':
            return "#dc3545"  # 红色
        else:
            return "#666666"  # 灰色

    def update_tracking_cards(self, grouped_data):
        """更新追踪卡片（向后兼容方法）"""
        return self.update_tracking_cards_safe(grouped_data)

    def update_existing_card(self, item_name, item_data):
        """更新现有卡片（向后兼容方法）"""
        return self.update_existing_card_safe(item_name, item_data)

    def rebuild_card_content(self, card, item_data):
        """重建卡片内容（向后兼容方法）"""
        return self.rebuild_card_content_safe(card, item_data)

    def update_card_header(self, card, item_data):
        """更新卡片头部（向后兼容方法）"""
        return self.update_card_header_safe(card, item_data)

    def create_item_card(self, item_data):
        """创建物品卡片（向后兼容方法）"""
        return self.create_item_card_safe(item_data)

    def build_card_content(self, card, item_data):
        """构建卡片内容"""
        try:
            print(f"[DEBUG] build_card_content被调用: {item_data['item_name']}")
            
            # 检查卡片是否已有布局
            layout = card.layout()
            if not layout:
                print(f"[DEBUG] 卡片没有布局，创建新布局")
                layout = QVBoxLayout(card)
            else:
                print(f"[DEBUG] 卡片已有布局，直接使用现有布局")
            
            # 使用专用方法构建内容
            self.build_card_content_with_layout(layout, item_data)
            
        except Exception as e:
            print(f"[ERROR] build_card_content出错: {str(e)}")
            import traceback
            traceback.print_exc()

    def build_card_header(self, header_layout, item_data):
        """构建卡片头部"""
        # 物品名称（大标题）
        title_label = QLabel(item_data['item_name'])
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 右侧信息
        latest_record = item_data['latest_record']
        competition_stats = item_data.get('competition_stats', {})
        
        if latest_record:
            # 溢价信息
            spread_color = self.get_trend_color(competition_stats.get('spread_trend', 'stable'))
            spread_label = QLabel(f"{latest_record['spread']}")
            spread_label.setStyleSheet(f"color: {spread_color}; font-weight: bold; font-size: 14px;")
            header_layout.addWidget(QLabel("溢价:"))
            header_layout.addWidget(spread_label)
            
            # 利润率信息
            profit_color = self.get_trend_color(competition_stats.get('profit_trend', 'stable'))
            profit_label = QLabel(f"{latest_record['profit_rate']}")
            profit_label.setStyleSheet(f"color: {profit_color}; font-weight: bold; font-size: 14px;")
            header_layout.addWidget(QLabel("利润率:"))
            header_layout.addWidget(profit_label)
            
            # 被竞价次数（使用总竞价数）
            total_competition = competition_stats.get('total_competitions', 0)
            competition_label = QLabel(f"{total_competition}")
            competition_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
            header_layout.addWidget(QLabel("被竞价:"))
            header_layout.addWidget(competition_label)

    def build_detail_content(self, detail_layout, item_data):
        """构建详细信息内容"""
        records = item_data['all_records']
        
        if not records:
            detail_layout.addWidget(QLabel("暂无数据"))
            return
        
        # 创建表头
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        headers = ["时间戳", "购买价格", "出售价格", "溢价", "利润率", "被竞价", "买家", "卖家"]
        # 恢复原本的列宽度：溢价、利润率、被竞价恢复原宽度，新增两列各40宽度
        widths = [150, 420, 200, 80, 80, 60, 40, 40]  # 恢复溢价、利润率、被竞价的原宽度
        
        for i, (header, width) in enumerate(zip(headers, widths)):
            label = QLabel(header)
            label.setStyleSheet("font-weight: bold; color: #555; border-bottom: 2px solid #ddd; padding: 5px;")
            label.setMinimumWidth(width)
            label.setMaximumWidth(width)
            # 表头文字居中对齐
            label.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(label)
        
        detail_layout.addWidget(header_widget)
        
        # 创建数据行
        for row_idx, record in enumerate(records):
            row_widget = self.create_data_row(record, records[row_idx-1] if row_idx > 0 else None, widths)
            detail_layout.addWidget(row_widget)

    def create_data_row(self, record, previous_record, widths):
        """创建数据行"""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(10, 3, 10, 3)
        
        # 背景色交替
        if hash(record['timestamp']) % 2 == 0:
            row_widget.setStyleSheet("background-color: #f8f9fa;")
        
        # 时间戳
        time_label = QLabel(str(record['timestamp']))
        time_label.setMinimumWidth(widths[0])
        time_label.setAlignment(Qt.AlignCenter)  # 与表头保持一致，居中对齐
        row_layout.addWidget(time_label)
        
        # 购买价格（横向排列，包含本人购买价格）
        buying_display = self.format_prices_horizontally(
            record['buying_prices'], 
            record.get('own_buying_price', ''),  # 传递本人购买价格
            previous_record['buying_prices'] if previous_record else None
        )
        buying_label = QLabel(buying_display)
        buying_label.setMinimumWidth(widths[1])
        buying_label.setMaximumWidth(widths[1])  # 设置最大宽度防止过宽
        buying_label.setTextFormat(Qt.RichText)
        buying_label.setWordWrap(True)
        buying_label.setAlignment(Qt.AlignCenter)  # 与表头保持一致，居中对齐
        row_layout.addWidget(buying_label)
        
        # 出售价格（横向排列，包含本人售出价格）
        selling_display = self.format_prices_horizontally(
            record['selling_prices'], 
            record.get('own_selling_price', ''),  # 传递本人售出价格
            previous_record['selling_prices'] if previous_record else None
        )
        selling_label = QLabel(selling_display)
        selling_label.setMinimumWidth(widths[2])
        selling_label.setMaximumWidth(widths[2])  # 设置最大宽度防止过宽
        selling_label.setTextFormat(Qt.RichText)
        selling_label.setWordWrap(True)
        selling_label.setAlignment(Qt.AlignCenter)  # 与表头保持一致，居中对齐
        row_layout.addWidget(selling_label)
        
        # 溢价
        spread_label = QLabel(str(record['spread']))
        spread_label.setMinimumWidth(widths[3])
        spread_label.setMaximumWidth(widths[3])
        spread_label.setAlignment(Qt.AlignCenter)
        if previous_record:
            spread_label.setStyleSheet(self.get_comparison_style(record['spread'], previous_record['spread']))
        row_layout.addWidget(spread_label)
        
        # 利润率
        profit_label = QLabel(str(record['profit_rate']))
        profit_label.setMinimumWidth(widths[4])
        profit_label.setMaximumWidth(widths[4])
        profit_label.setAlignment(Qt.AlignCenter)
        if previous_record:
            profit_label.setStyleSheet(self.get_comparison_style(record['profit_rate'], previous_record['profit_rate']))
        row_layout.addWidget(profit_label)
        
        # 被竞价次数（传递上一行记录用于计算新增竞价）
        competition_count = self.calculate_row_competition(record, previous_record)
        competition_label = QLabel(str(competition_count))
        competition_label.setMinimumWidth(widths[5])
        competition_label.setMaximumWidth(widths[5])
        competition_label.setAlignment(Qt.AlignCenter)
        if competition_count > 0:
            competition_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        row_layout.addWidget(competition_label)
        
        # 出价数量
        bid_count = record.get('bid_count', 0)
        bid_label = QLabel(str(bid_count))
        bid_label.setMinimumWidth(widths[6])
        bid_label.setMaximumWidth(widths[6])
        bid_label.setAlignment(Qt.AlignCenter)
        if previous_record:
            prev_bid_count = previous_record.get('bid_count', 0)
            if bid_count > prev_bid_count:
                bid_label.setStyleSheet("color: #28a745; font-weight: bold;")  # 绿色表示增加
            elif bid_count < prev_bid_count:
                bid_label.setStyleSheet("color: #dc3545; font-weight: bold;")  # 红色表示减少
        row_layout.addWidget(bid_label)
        
        # 上架数量
        listing_count = record.get('listing_count', 0)
        listing_label = QLabel(str(listing_count))
        listing_label.setMinimumWidth(widths[7])
        listing_label.setMaximumWidth(widths[7])
        listing_label.setAlignment(Qt.AlignCenter)
        if previous_record:
            prev_listing_count = previous_record.get('listing_count', 0)
            if listing_count > prev_listing_count:
                listing_label.setStyleSheet("color: #28a745; font-weight: bold;")  # 绿色表示增加
            elif listing_count < prev_listing_count:
                listing_label.setStyleSheet("color: #dc3545; font-weight: bold;")  # 红色表示减少
        row_layout.addWidget(listing_label)
        
        return row_widget

    def format_prices_horizontally(self, current_prices, own_price, previous_prices):
        """格式化价格用于横向显示"""
        # 收集所有当前价格（包括本人价格）
        all_current_prices = []
        
        # 添加普通价格
        for price in current_prices if current_prices else []:
            all_current_prices.append({
                'price': price,
                'type': 'normal',
                'is_own': False
            })
        
        # 添加本人价格
        if own_price and str(own_price).strip():
            try:
                own_price_clean = str(own_price).replace(',', '').strip()
                if own_price_clean and own_price_clean != 'nan':
                    # 修复：先转换为float再转换为int，处理numpy.float64类型
                    own_price_num = int(float(own_price_clean))
                    all_current_prices.append({
                        'price': own_price_num,
                        'type': 'normal',
                        'is_own': True
                    })
                    print(f"[DEBUG] 成功添加本人价格: {own_price_num}")
            except Exception as e:
                print(f"[DEBUG] 无法解析本人价格: {own_price}, 错误: {str(e)}")
        
        # 添加删除的价格（前一行有但当前行没有的）
        if previous_prices:
            # 获取当前所有价格的集合（用于比较）
            current_price_set = set()
            for price_info in all_current_prices:
                current_price_set.add(price_info['price'])
            
            # 添加被删除的价格
            for prev_price in previous_prices:
                if prev_price not in current_price_set:
                    all_current_prices.append({
                        'price': prev_price,
                        'type': 'deleted',
                        'is_own': False
                    })
        
        # 如果没有任何价格，返回无价格提示
        if not all_current_prices:
            return "<span style='color: #999;'>无价格</span>"
        
        # 按价格从小到大排序
        all_current_prices.sort(key=lambda x: x['price'])
        
        # 格式化显示
        formatted_prices = []
        for price_info in all_current_prices:
            price = price_info['price']
            price_type = price_info['type']
            is_own = price_info['is_own']
            
            if price_type == 'deleted':
                # 删除的价格：恢复红色显示
                price_str = f"<span style='color: #dc3545; text-decoration: line-through;'>{price:,}</span>"
            else:
                # 当前价格
                if is_own:
                    # 本人价格：特殊背景框
                    price_str = f"<span style='border: 2px solid #007acc; padding: 2px 5px; background-color: #e3f2fd; border-radius: 4px; font-weight: bold; color: #0d47a1;'>{price:,}</span>"
                else:
                    # 普通价格
                    # 检查是否是新增价格
                    if previous_prices and price not in previous_prices:
                        price_str = f"<span style='color: #28a745; font-weight: bold;'>{price:,}</span>"
                    else:
                        price_str = f"{price:,}"
            
            formatted_prices.append(price_str)
        
        return " • ".join(formatted_prices) if formatted_prices else "<span style='color: #999;'>无价格</span>"

    def get_comparison_style(self, current_value, previous_value):
        """获取比较样式"""
        try:
            current_num = self.parse_numeric_value(current_value)
            previous_num = self.parse_numeric_value(previous_value)
            
            if current_num is not None and previous_num is not None:
                if current_num > previous_num:
                    return "background-color: #d4edda; color: #155724; font-weight: bold;"  # 绿色背景
                elif current_num < previous_num:
                    return "background-color: #f8d7da; color: #721c24; font-weight: bold;"  # 红色背景
            
            return ""
        except:
            return ""

    def toggle_card_detail(self, item_name, detail_widget, toggle_btn):
        """切换卡片详细信息显示状态"""
        if item_name in self.card_states:
            current_state = self.card_states[item_name]['expanded']
            new_state = not current_state
            self.card_states[item_name]['expanded'] = new_state
            
            if new_state:
                detail_widget.show()
                toggle_btn.setText("收起详情")
            else:
                detail_widget.hide()
                toggle_btn.setText("展开详情")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("自动化市场交易")
    app.setApplicationVersion("1.0")
    
    # 设置字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    # 创建并显示主窗口
    window = AutoTradeMainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 