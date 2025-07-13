#!/usr/bin/env python3
"""
现代战舰模板配置工具
自动化配置游戏识别模板，解决不同分辨率设备的兼容性问题
"""

import sys
import os
import json
import cv2
import numpy as np
import re
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QLabel, QComboBox, QTextEdit, 
                            QGroupBox, QProgressBar, QMessageBox, QDialog,
                            QGridLayout, QFrame, QScrollArea, QSplitter,
                            QListWidget, QListWidgetItem, QCheckBox, QSpinBox,
                            QTabWidget, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPixmap, QImage, QPainter, QPen, QColor, QIcon
import ADBHelper

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(SCRIPT_DIR, "templates")
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")

class ImageSelector(QDialog):
    """图片选择器对话框"""
    
    def __init__(self, image_path, title="选择区域", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1200, 800)
        
        self.image_path = image_path
        self.selected_rect = None
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.scale_factor = 1.0
        
        self.init_ui()
        self.load_image()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 说明标签
        info_label = QLabel("请在图片上拖拽鼠标选择区域，选择完成后点击确认")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 14px; color: #666; padding: 10px;")
        layout.addWidget(info_label)
        
        # 图片显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(1200, 800)
        self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        self.image_label.mousePressEvent = self.mouse_press_event
        self.image_label.mouseMoveEvent = self.mouse_move_event
        self.image_label.mouseReleaseEvent = self.mouse_release_event
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.confirm_btn = QPushButton("确认选择")
        self.confirm_btn.clicked.connect(self.accept)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; } QPushButton:hover { background-color: #45a049; }")
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 8px 16px; border: none; border-radius: 4px; } QPushButton:hover { background-color: #da190b; }")
        
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_image(self):
        """加载图片"""
        if os.path.exists(self.image_path):
            self.cv_image = cv2.imread(self.image_path)
            if self.cv_image is not None:
                self.display_image()
            else:
                QMessageBox.warning(self, "错误", "无法加载图片文件")
    
    def display_image(self):
        """显示图片"""
        if hasattr(self, 'cv_image') and self.cv_image is not None:
            # 转换为Qt格式
            rgb_image = cv2.cvtColor(self.cv_image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 计算缩放比例
            label_size = self.image_label.size()
            image_size = qt_image.size()
            
            # 默认放大显示，不缩小
            if image_size.width() < label_size.width() and image_size.height() < label_size.height():
                # 图片比显示区域小时，放大到合适大小
                scale_x = label_size.width() / image_size.width()
                scale_y = label_size.height() / image_size.height()
                self.scale_factor = min(scale_x, scale_y) * 0.8  # 留一些边距
                
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    int(image_size.width() * self.scale_factor),
                    int(image_size.height() * self.scale_factor),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
                # 计算偏移（居中显示）
                scaled_size = scaled_pixmap.size()
                self.image_offset_x = (label_size.width() - scaled_size.width()) // 2
                self.image_offset_y = (label_size.height() - scaled_size.height()) // 2
            elif image_size.width() > label_size.width() or image_size.height() > label_size.height():
                # 图片比显示区域大时，适当缩小
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.scale_factor = min(label_size.width() / image_size.width(), label_size.height() / image_size.height())
                
                # 计算偏移
                scaled_size = scaled_pixmap.size()
                self.image_offset_x = (label_size.width() - scaled_size.width()) // 2
                self.image_offset_y = (label_size.height() - scaled_size.height()) // 2
            else:
                # 图片大小合适，不缩放
                scaled_pixmap = QPixmap.fromImage(qt_image)
                self.scale_factor = 1.0
                self.image_offset_x = 0
                self.image_offset_y = 0
            
            # 在缩放后的图片上绘制选择框
            if self.start_point and self.end_point:
                painter = QPainter(scaled_pixmap)
                painter.setPen(QPen(QColor(0, 255, 0), 2))
                
                # 转换坐标到缩放后的图片坐标系
                x1 = (self.start_point.x() - self.image_offset_x)
                y1 = (self.start_point.y() - self.image_offset_y)
                x2 = (self.end_point.x() - self.image_offset_x)
                y2 = (self.end_point.y() - self.image_offset_y)
                
                # 确保坐标在图片范围内
                scaled_size = scaled_pixmap.size()
                x1 = max(0, min(x1, scaled_size.width()))
                y1 = max(0, min(y1, scaled_size.height()))
                x2 = max(0, min(x2, scaled_size.width()))
                y2 = max(0, min(y2, scaled_size.height()))
                
                if x2 > x1 and y2 > y1:
                    painter.drawRect(int(x1), int(y1), int(x2-x1), int(y2-y1))
                painter.end()
            
            self.image_label.setPixmap(scaled_pixmap)
    
    def mouse_press_event(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
    
    def mouse_move_event(self, event):
        """鼠标移动事件"""
        if self.drawing:
            self.end_point = event.pos()
            self.display_image()
    
    def mouse_release_event(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            self.end_point = event.pos()
            
            # 计算实际图片坐标，考虑缩放和偏移
            if hasattr(self, 'image_offset_x') and hasattr(self, 'image_offset_y'):
                # 减去偏移量，转换为缩放图片坐标
                x1 = (self.start_point.x() - self.image_offset_x) / self.scale_factor
                y1 = (self.start_point.y() - self.image_offset_y) / self.scale_factor
                x2 = (self.end_point.x() - self.image_offset_x) / self.scale_factor
                y2 = (self.end_point.y() - self.image_offset_y) / self.scale_factor
            else:
                # 没有偏移的情况
                x1 = self.start_point.x() / self.scale_factor
                y1 = self.start_point.y() / self.scale_factor
                x2 = self.end_point.x() / self.scale_factor
                y2 = self.end_point.y() / self.scale_factor
            
            # 确保坐标顺序正确
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            
            # 转换为整数并确保在图片范围内
            if hasattr(self, 'cv_image') and self.cv_image is not None:
                h, w = self.cv_image.shape[:2]
                x1 = max(0, min(int(x1), w))
                y1 = max(0, min(int(y1), h))
                x2 = max(0, min(int(x2), w))
                y2 = max(0, min(int(y2), h))
                
                if x2 > x1 and y2 > y1:
                    self.selected_rect = (x1, y1, x2, y2)
                    self.confirm_btn.setEnabled(True)
            
            self.display_image()
    
    def get_selected_rect(self):
        """获取选择的区域"""
        return self.selected_rect


class RewardRegionCalibrator(QDialog):
    """奖励区域校准对话框"""
    
    def __init__(self, image_path, current_regions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("奖励区域校准")
        self.setModal(True)
        self.resize(1400, 900)
        
        self.image_path = image_path
        self.current_regions = current_regions
        self.new_regions = {}
        self.scale_factor = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        
        # 当前选中的区域
        self.selected_region = None
        self.dragging = False
        self.drag_start = None
        
        # 区域颜色
        self.region_colors = {
            'dollar_base': QColor(255, 0, 0),      # 红色
            'dollar_extra': QColor(255, 165, 0),   # 橙色
            'gold_base': QColor(255, 255, 0),      # 黄色
            'gold_extra': QColor(0, 255, 0)        # 绿色
        }
        
        self.region_names = {
            'dollar_base': '美元基础',
            'dollar_extra': '美元额外',
            'gold_base': '黄金基础',
            'gold_extra': '黄金额外'
        }
        
        self.init_ui()
        self.load_image()
        self.new_regions = dict(current_regions)  # 复制当前区域
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 说明标签
        info_label = QLabel("当前显示的彩色框为现有的奖励区域位置。您可以拖拽调整这些区域的位置和大小。")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 14px; color: #666; padding: 10px;")
        layout.addWidget(info_label)
        
        # 主要内容区域
        content_layout = QHBoxLayout()
        
        # 图片显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(1200, 800)
        self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        self.image_label.mousePressEvent = self.mouse_press_event
        self.image_label.mouseMoveEvent = self.mouse_move_event
        self.image_label.mouseReleaseEvent = self.mouse_release_event
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        content_layout.addWidget(scroll_area)
        
        # 控制面板
        control_panel = QGroupBox("区域控制")
        control_layout = QVBoxLayout()
        
        # 区域选择
        region_group = QGroupBox("选择区域")
        region_layout = QVBoxLayout()
        
        self.region_buttons = {}
        for region_key, region_name in self.region_names.items():
            btn = QPushButton(region_name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, key=region_key: self.select_region(key))
            color = self.region_colors[region_key]
            btn.setStyleSheet(f"QPushButton {{ background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 0.3); border: 2px solid rgb({color.red()}, {color.green()}, {color.blue()}); padding: 8px; }} QPushButton:checked {{ background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 0.6); }}")
            region_layout.addWidget(btn)
            self.region_buttons[region_key] = btn
        
        region_group.setLayout(region_layout)
        control_layout.addWidget(region_group)
        
        # 坐标显示
        coord_group = QGroupBox("当前坐标")
        coord_layout = QVBoxLayout()
        
        self.coord_labels = {}
        for region_key, region_name in self.region_names.items():
            label = QLabel(f"{region_name}: 未选择")
            label.setStyleSheet("font-family: monospace; font-size: 12px;")
            coord_layout.addWidget(label)
            self.coord_labels[region_key] = label
        
        coord_group.setLayout(coord_layout)
        control_layout.addWidget(coord_group)
        
        # 重置按钮
        reset_btn = QPushButton("重置所有区域")
        reset_btn.clicked.connect(self.reset_regions)
        reset_btn.setStyleSheet("QPushButton { background-color: #ff9800; color: white; padding: 8px; border: none; border-radius: 4px; }")
        control_layout.addWidget(reset_btn)
        
        control_layout.addStretch()
        control_panel.setLayout(control_layout)
        control_panel.setMaximumWidth(300)
        
        content_layout.addWidget(control_panel)
        layout.addLayout(content_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.confirm_btn = QPushButton("确认校准")
        self.confirm_btn.clicked.connect(self.accept)
        self.confirm_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; } QPushButton:hover { background-color: #45a049; }")
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 8px 16px; border: none; border-radius: 4px; } QPushButton:hover { background-color: #da190b; }")
        
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_image(self):
        """加载图片"""
        if os.path.exists(self.image_path):
            self.cv_image = cv2.imread(self.image_path)
            if self.cv_image is not None:
                self.display_image()
                self.update_coord_labels()
            else:
                QMessageBox.warning(self, "错误", "无法加载图片文件")
    
    def display_image(self):
        """显示图片"""
        if hasattr(self, 'cv_image') and self.cv_image is not None:
            # 转换为Qt格式
            rgb_image = cv2.cvtColor(self.cv_image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 计算缩放比例
            label_size = self.image_label.size()
            image_size = qt_image.size()
            
            # 默认放大显示，不缩小
            if image_size.width() < label_size.width() and image_size.height() < label_size.height():
                # 图片比显示区域小时，放大到合适大小
                scale_x = label_size.width() / image_size.width()
                scale_y = label_size.height() / image_size.height()
                self.scale_factor = min(scale_x, scale_y) * 0.8  # 留一些边距
                
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    int(image_size.width() * self.scale_factor),
                    int(image_size.height() * self.scale_factor),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
                # 计算偏移（居中显示）
                scaled_size = scaled_pixmap.size()
                self.image_offset_x = (label_size.width() - scaled_size.width()) // 2
                self.image_offset_y = (label_size.height() - scaled_size.height()) // 2
            elif image_size.width() > label_size.width() or image_size.height() > label_size.height():
                # 图片比显示区域大时，适当缩小
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.scale_factor = min(label_size.width() / image_size.width(), label_size.height() / image_size.height())
                
                # 计算偏移
                scaled_size = scaled_pixmap.size()
                self.image_offset_x = (label_size.width() - scaled_size.width()) // 2
                self.image_offset_y = (label_size.height() - scaled_size.height()) // 2
            else:
                # 图片大小合适，不缩放
                scaled_pixmap = QPixmap.fromImage(qt_image)
                self.scale_factor = 1.0
                self.image_offset_x = 0
                self.image_offset_y = 0
            
            # 绘制区域框
            painter = QPainter(scaled_pixmap)
            
            for region_key, region_coords in self.new_regions.items():
                if region_coords:
                    color = self.region_colors[region_key]
                    if region_key == self.selected_region:
                        painter.setPen(QPen(color, 3))  # 选中的区域线条更粗
                    else:
                        painter.setPen(QPen(color, 2))
                    
                    # 转换坐标
                    x1, y1, x2, y2 = region_coords
                    x1 = int(x1 * self.scale_factor)
                    y1 = int(y1 * self.scale_factor)
                    x2 = int(x2 * self.scale_factor)
                    y2 = int(y2 * self.scale_factor)
                    
                    painter.drawRect(x1, y1, x2-x1, y2-y1)
                    
                    # 绘制区域名称（在框的下方居中）
                    painter.setPen(QPen(color, 1))
                    font = painter.font()
                    font.setPointSize(10)
                    font.setBold(True)
                    painter.setFont(font)
                    
                    # 计算文字位置（框的下方居中）
                    text = self.region_names[region_key]
                    text_rect = painter.fontMetrics().boundingRect(text)
                    text_x = x1 + (x2 - x1 - text_rect.width()) // 2
                    text_y = y2 + text_rect.height() + 5  # 框下方5像素
                    
                    # 绘制白色背景以提高可读性
                    painter.fillRect(text_x - 2, text_y - text_rect.height(), 
                                   text_rect.width() + 4, text_rect.height() + 2, 
                                   QColor(255, 255, 255, 200))
                    
                    # 绘制文字
                    painter.setPen(QPen(color, 1))
                    painter.drawText(text_x, text_y, text)
            
            painter.end()
            self.image_label.setPixmap(scaled_pixmap)
    
    def select_region(self, region_key):
        """选择区域"""
        # 取消其他按钮的选中状态
        for key, btn in self.region_buttons.items():
            btn.setChecked(key == region_key)
        
        self.selected_region = region_key
        self.display_image()
    
    def mouse_press_event(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton and self.selected_region:
            # 检查点击位置是否在某个区域内
            click_x = event.pos().x()
            click_y = event.pos().y()
            
            # 转换为实际图片坐标
            real_x = (click_x - self.image_offset_x) / self.scale_factor
            real_y = (click_y - self.image_offset_y) / self.scale_factor
            
            # 检查是否点击在选中的区域内
            if self.selected_region in self.new_regions:
                x1, y1, x2, y2 = self.new_regions[self.selected_region]
                if x1 <= real_x <= x2 and y1 <= real_y <= y2:
                    self.dragging = True
                    self.drag_start = event.pos()
    
    def mouse_move_event(self, event):
        """鼠标移动事件"""
        if self.dragging and self.selected_region and self.drag_start:
            # 计算移动距离
            dx = event.pos().x() - self.drag_start.x()
            dy = event.pos().y() - self.drag_start.y()
            
            # 转换为实际图片坐标
            dx_real = dx / self.scale_factor
            dy_real = dy / self.scale_factor
            
            # 更新区域坐标
            if self.selected_region in self.new_regions:
                x1, y1, x2, y2 = self.new_regions[self.selected_region]
                new_x1 = x1 + dx_real
                new_y1 = y1 + dy_real
                new_x2 = x2 + dx_real
                new_y2 = y2 + dy_real
                
                # 确保区域在图片范围内
                if hasattr(self, 'cv_image') and self.cv_image is not None:
                    h, w = self.cv_image.shape[:2]
                    # 检查是否超出边界
                    if new_x1 >= 0 and new_y1 >= 0 and new_x2 <= w and new_y2 <= h:
                        self.new_regions[self.selected_region] = (
                            int(new_x1), int(new_y1),
                            int(new_x2), int(new_y2)
                        )
                        
                        self.drag_start = event.pos()
                        self.display_image()
                        self.update_coord_labels()
    
    def mouse_release_event(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.drag_start = None
    
    def update_coord_labels(self):
        """更新坐标标签"""
        for region_key, label in self.coord_labels.items():
            if region_key in self.new_regions and self.new_regions[region_key]:
                coords = self.new_regions[region_key]
                label.setText(f"{self.region_names[region_key]}: ({coords[0]}, {coords[1]}, {coords[2]}, {coords[3]})")
            else:
                label.setText(f"{self.region_names[region_key]}: 未设置")
    
    def reset_regions(self):
        """重置所有区域"""
        self.new_regions = dict(self.current_regions)
        self.display_image()
        self.update_coord_labels()
    
    def get_calibrated_regions(self):
        """获取校准后的区域"""
        return self.new_regions


class TemplateManager:
    """模板文件管理器"""
    
    def __init__(self, templates_dir):
        self.templates_dir = templates_dir
        self.ensure_templates_dir()
    
    def ensure_templates_dir(self):
        """确保模板目录存在"""
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir)
    
    def backup_templates(self):
        """备份现有模板"""
        backup_dir = os.path.join(self.templates_dir, "backup_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # 备份关键模板文件
        template_files = [
            "main_page.png",
            "into_battle.png", 
            "multi_team_battle.png",
            "shengli.png",
            "no_vip.png"
        ]
        
        backed_up = []
        for template_file in template_files:
            src_path = os.path.join(self.templates_dir, template_file)
            if os.path.exists(src_path):
                dst_path = os.path.join(backup_dir, template_file)
                try:
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    backed_up.append(template_file)
                except Exception as e:
                    print(f"备份文件失败 {template_file}: {e}")
        
        return backup_dir, backed_up
    
    def save_template(self, template_name, image_data):
        """保存模板图片"""
        template_path = os.path.join(self.templates_dir, template_name)
        try:
            cv2.imwrite(template_path, image_data)
            return os.path.exists(template_path)
        except Exception as e:
            print(f"保存模板失败 {template_name}: {e}")
            return False
    
    def crop_and_save_template(self, source_image_path, template_name, region):
        """裁剪并保存模板"""
        try:
            source_image = cv2.imread(source_image_path)
            if source_image is None:
                return False
            
            x1, y1, x2, y2 = region
            cropped = source_image[y1:y2, x1:x2]
            
            return self.save_template(template_name, cropped)
        except Exception as e:
            print(f"裁剪保存模板失败 {template_name}: {e}")
            return False
    
    def update_reward_regions(self, regions):
        """更新warship_auto_battle.py中的REWARD_REGIONS"""
        file_path = os.path.join(SCRIPT_DIR, "warship_auto_battle.py")
        
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 构建新的REWARD_REGIONS字典
            new_regions = f'''REWARD_REGIONS = {{
    "dollar_base": {regions['dollar_base']},      # 美元奖励
    "dollar_extra": {regions['dollar_extra']},    # 美元额外奖励
    "gold_base": {regions['gold_base']},       # 黄金奖励
    "gold_extra": {regions['gold_extra']},      # 黄金额外奖励
    "vip_check": (1482, 425, 1519, 465)        # VIP状态检查区域
}}'''
            
            # 使用正则表达式替换
            pattern = r'REWARD_REGIONS = \{[^}]+\}'
            content = re.sub(pattern, new_regions, content, flags=re.DOTALL)
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            print(f"更新REWARD_REGIONS失败: {e}")
            return False


class ConfigStep(QWidget):
    """配置步骤基类"""
    
    step_completed = pyqtSignal(dict)  # 步骤完成信号
    
    def __init__(self, step_name, description, parent=None):
        super().__init__(parent)
        self.step_name = step_name
        self.description = description
        self.config_data = {}
        self.device_id = None
        self.template_manager = TemplateManager(TEMPLATES_DIR)
        self.current_screenshot = None
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 步骤标题
        title_label = QLabel(self.step_name)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 描述
        desc_label = QLabel(self.description)
        desc_label.setStyleSheet("font-size: 14px; color: #666; margin-bottom: 20px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # 子类实现具体内容
        self.setup_content(layout)
        
        self.setLayout(layout)
    
    def setup_content(self, layout):
        """子类实现具体内容"""
        pass
    
    def set_device(self, device_id):
        """设置设备ID"""
        self.device_id = device_id
    
    def take_screenshot(self):
        """截取屏幕"""
        if not self.device_id:
            QMessageBox.warning(self, "错误", "请先选择设备")
            return None
        
        try:
            # 确保缓存目录存在
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(CACHE_DIR, f"temp_screenshot_{timestamp}.png")
            
            if ADBHelper.screenCapture(self.device_id, screenshot_path):
                self.current_screenshot = screenshot_path
                return screenshot_path
            else:
                QMessageBox.warning(self, "错误", "截图失败，请检查设备连接")
                return None
        except Exception as e:
            QMessageBox.critical(self, "错误", f"截图时发生错误: {str(e)}")
            return None
    
    def validate_step(self):
        """验证步骤是否完成"""
        return True
    
    def get_config_data(self):
        """获取配置数据"""
        return self.config_data


class MainPageConfigStep(ConfigStep):
    """主界面配置步骤"""
    
    def __init__(self, parent=None):
        super().__init__(
            "步骤1：主界面配置",
            "请确保游戏处于主界面状态，然后点击截取屏幕按钮进行配置。主界面区域会自动识别，您只需要手动配置进入战斗按钮。",
            parent
        )
        self.main_page_configured = False
        self.battle_button_configured = False
    
    def setup_content(self, layout):
        """设置内容"""
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.screenshot_btn = QPushButton("📸 截取当前屏幕")
        self.screenshot_btn.clicked.connect(self.on_screenshot)
        self.screenshot_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 4px; font-size: 14px; } QPushButton:hover { background-color: #1976D2; }")
        
        self.config_battle_btn = QPushButton("配置进入战斗按钮")
        self.config_battle_btn.clicked.connect(self.config_battle_button)
        self.config_battle_btn.setEnabled(False)
        
        button_layout.addWidget(self.screenshot_btn)
        button_layout.addWidget(self.config_battle_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 示例图展示区域
        example_group = QGroupBox("模板示例")
        example_layout = QHBoxLayout()
        
        # 主界面模板示例
        main_example_layout = QVBoxLayout()
        main_example_layout.addWidget(QLabel("主界面识别区域 (自动)"))
        self.main_example_label = QLabel("暂无图片")
        self.main_example_label.setFixedSize(150, 80)
        self.main_example_label.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.main_example_label.setAlignment(Qt.AlignCenter)
        main_example_layout.addWidget(self.main_example_label)
        example_layout.addLayout(main_example_layout)
        
        # 进入战斗按钮示例
        battle_example_layout = QVBoxLayout()
        battle_example_layout.addWidget(QLabel("进入战斗按钮"))
        self.battle_example_label = QLabel("暂无图片")
        self.battle_example_label.setFixedSize(150, 80)
        self.battle_example_label.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.battle_example_label.setAlignment(Qt.AlignCenter)
        battle_example_layout.addWidget(self.battle_example_label)
        example_layout.addLayout(battle_example_layout)
        
        example_layout.addStretch()
        example_group.setLayout(example_layout)
        layout.addWidget(example_group)
        
        # 状态显示
        self.status_label = QLabel("请先截取屏幕")
        self.status_label.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.status_label)
        
        # 配置状态
        status_group = QGroupBox("配置状态")
        status_layout = QVBoxLayout()
        
        self.main_status_label = QLabel("⏳ 主界面区域：未配置")
        self.battle_status_label = QLabel("⏳ 进入战斗按钮：未配置")
        
        status_layout.addWidget(self.main_status_label)
        status_layout.addWidget(self.battle_status_label)
        status_group.setLayout(status_layout)
        
        layout.addWidget(status_group)
        
        # 加载现有模板示例
        self.load_existing_templates()
    
    def load_existing_templates(self):
        """加载现有模板作为示例"""
        # 加载主界面模板
        main_template_path = os.path.join(TEMPLATES_DIR, "main_page.png")
        if os.path.exists(main_template_path):
            self.show_template_example(main_template_path, self.main_example_label)
        
        # 加载进入战斗按钮模板
        battle_template_path = os.path.join(TEMPLATES_DIR, "into_battle.png")
        if os.path.exists(battle_template_path):
            self.show_template_example(battle_template_path, self.battle_example_label)
    
    def show_template_example(self, template_path, label):
        """显示模板示例图"""
        try:
            pixmap = QPixmap(template_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"加载模板示例失败: {e}")
    
    def show_template_comparison(self, old_path, new_path, label, template_name):
        """显示模板替换前后对比"""
        try:
            # 创建对比图
            comparison_dialog = QDialog(self)
            comparison_dialog.setWindowTitle(f"{template_name} - 模板对比")
            comparison_dialog.setModal(True)
            comparison_dialog.resize(600, 300)
            
            layout = QVBoxLayout()
            
            # 标题
            title_label = QLabel(f"模板已更新：{template_name}")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
            layout.addWidget(title_label)
            
            # 对比图片
            images_layout = QHBoxLayout()
            
            # 旧模板
            old_layout = QVBoxLayout()
            old_layout.addWidget(QLabel("替换前"))
            old_label = QLabel()
            old_label.setFixedSize(250, 150)
            old_label.setStyleSheet("border: 1px solid #ccc;")
            old_label.setAlignment(Qt.AlignCenter)
            if os.path.exists(old_path):
                old_pixmap = QPixmap(old_path)
                if not old_pixmap.isNull():
                    old_label.setPixmap(old_pixmap.scaled(old_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            old_layout.addWidget(old_label)
            images_layout.addLayout(old_layout)
            
            # 箭头
            arrow_label = QLabel("→")
            arrow_label.setAlignment(Qt.AlignCenter)
            arrow_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
            images_layout.addWidget(arrow_label)
            
            # 新模板
            new_layout = QVBoxLayout()
            new_layout.addWidget(QLabel("替换后"))
            new_label = QLabel()
            new_label.setFixedSize(250, 150)
            new_label.setStyleSheet("border: 1px solid #ccc;")
            new_label.setAlignment(Qt.AlignCenter)
            if os.path.exists(new_path):
                new_pixmap = QPixmap(new_path)
                if not new_pixmap.isNull():
                    new_label.setPixmap(new_pixmap.scaled(new_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            new_layout.addWidget(new_label)
            images_layout.addLayout(new_layout)
            
            layout.addLayout(images_layout)
            
            # 确认按钮
            ok_btn = QPushButton("确定")
            ok_btn.clicked.connect(comparison_dialog.accept)
            ok_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; }")
            
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(ok_btn)
            layout.addLayout(btn_layout)
            
            comparison_dialog.setLayout(layout)
            comparison_dialog.exec_()
            
            # 更新示例图
            self.show_template_example(new_path, label)
            
        except Exception as e:
            print(f"显示模板对比失败: {e}")
    
    def on_screenshot(self):
        """截图按钮点击事件"""
        screenshot_path = self.take_screenshot()
        if screenshot_path:
            self.status_label.setText(f"截图成功：{os.path.basename(screenshot_path)}")
            self.config_battle_btn.setEnabled(True)
            
            # 自动配置主界面区域
            self.auto_config_main_page()
    
    def auto_config_main_page(self):
        """自动配置主界面区域"""
        if not self.current_screenshot:
            return
        
        # 自动截取 (2109, 40, 2254, 92) 区域
        region = (2109, 40, 2254, 92)
        
        # 检查是否有旧模板
        old_template_path = os.path.join(TEMPLATES_DIR, "main_page.png")
        has_old_template = os.path.exists(old_template_path)
        
        # 创建临时文件保存旧模板
        old_temp_path = None
        if has_old_template:
            old_temp_path = os.path.join(CACHE_DIR, "temp_old_main_page.png")
            try:
                # 确保缓存目录存在
                if not os.path.exists(CACHE_DIR):
                    os.makedirs(CACHE_DIR)
                import shutil
                shutil.copy2(old_template_path, old_temp_path)
            except:
                old_temp_path = None
        
        if self.template_manager.crop_and_save_template(self.current_screenshot, "main_page.png", region):
            self.main_page_configured = True
            self.main_status_label.setText("✅ 主界面区域：已配置")
            self.config_data['main_page_region'] = region
            
            # 显示对比图（如果有旧模板）
            if has_old_template and old_temp_path:
                self.show_template_comparison(old_temp_path, old_template_path, self.main_example_label, "主界面识别区域")
            else:
                self.show_template_example(old_template_path, self.main_example_label)
            
            self.check_completion()
        else:
            QMessageBox.warning(self, "错误", "自动配置主界面区域失败")
    
    def config_battle_button(self):
        """配置进入战斗按钮"""
        if not self.current_screenshot:
            QMessageBox.warning(self, "错误", "请先截取屏幕")
            return
        
        selector = ImageSelector(self.current_screenshot, "选择进入战斗按钮", self)
        if selector.exec_() == QDialog.Accepted:
            region = selector.get_selected_rect()
            if region:
                # 检查是否有旧模板
                old_template_path = os.path.join(TEMPLATES_DIR, "into_battle.png")
                has_old_template = os.path.exists(old_template_path)
                
                # 创建临时文件保存旧模板
                old_temp_path = None
                if has_old_template:
                    old_temp_path = os.path.join(CACHE_DIR, "temp_old_into_battle.png")
                    try:
                        # 确保缓存目录存在
                        if not os.path.exists(CACHE_DIR):
                            os.makedirs(CACHE_DIR)
                        import shutil
                        shutil.copy2(old_template_path, old_temp_path)
                    except:
                        old_temp_path = None
                
                if self.template_manager.crop_and_save_template(self.current_screenshot, "into_battle.png", region):
                    self.battle_button_configured = True
                    self.battle_status_label.setText("✅ 进入战斗按钮：已配置")
                    self.config_data['battle_button_region'] = region
                    
                    # 显示对比图（如果有旧模板）
                    if has_old_template and old_temp_path:
                        self.show_template_comparison(old_temp_path, old_template_path, self.battle_example_label, "进入战斗按钮")
                    else:
                        self.show_template_example(old_template_path, self.battle_example_label)
                    
                    self.check_completion()
                else:
                    QMessageBox.warning(self, "错误", "保存进入战斗按钮模板失败")
    
    def check_completion(self):
        """检查步骤是否完成"""
        if self.main_page_configured and self.battle_button_configured:
            self.step_completed.emit(self.config_data)
    
    def validate_step(self):
        """验证步骤是否完成"""
        return self.main_page_configured and self.battle_button_configured


class MultiTeamConfigStep(ConfigStep):
    """混斗模式配置步骤"""
    
    def __init__(self, parent=None):
        super().__init__(
            "步骤2：混斗模式配置",
            "请进入混斗模式地图，当游戏开始时点击截取屏幕按钮进行配置。混斗模式区域会自动识别。",
            parent
        )
        self.multi_team_configured = False
    
    def setup_content(self, layout):
        """设置内容"""
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.screenshot_btn = QPushButton("📸 截取当前屏幕")
        self.screenshot_btn.clicked.connect(self.on_screenshot)
        self.screenshot_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 4px; font-size: 14px; } QPushButton:hover { background-color: #1976D2; }")
        
        button_layout.addWidget(self.screenshot_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 示例图展示区域
        example_group = QGroupBox("模板示例")
        example_layout = QHBoxLayout()
        
        # 混斗模式模板示例
        multi_example_layout = QVBoxLayout()
        multi_example_layout.addWidget(QLabel("混斗模式识别区域 (自动)"))
        self.multi_example_label = QLabel("暂无图片")
        self.multi_example_label.setFixedSize(150, 80)
        self.multi_example_label.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.multi_example_label.setAlignment(Qt.AlignCenter)
        multi_example_layout.addWidget(self.multi_example_label)
        example_layout.addLayout(multi_example_layout)
        
        example_layout.addStretch()
        example_group.setLayout(example_layout)
        layout.addWidget(example_group)
        
        # 状态显示
        self.status_label = QLabel("请先截取屏幕")
        self.status_label.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.status_label)
        
        # 配置状态
        status_group = QGroupBox("配置状态")
        status_layout = QVBoxLayout()
        
        self.multi_team_status_label = QLabel("⏳ 混斗模式识别：未配置")
        status_layout.addWidget(self.multi_team_status_label)
        status_group.setLayout(status_layout)
        
        layout.addWidget(status_group)
        
        # 加载现有模板示例
        self.load_existing_templates()
    
    def load_existing_templates(self):
        """加载现有模板作为示例"""
        # 加载混斗模式模板
        multi_template_path = os.path.join(TEMPLATES_DIR, "multi_team_battle.png")
        if os.path.exists(multi_template_path):
            self.show_template_example(multi_template_path, self.multi_example_label)
    
    def show_template_example(self, template_path, label):
        """显示模板示例图"""
        try:
            pixmap = QPixmap(template_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"加载模板示例失败: {e}")
    
    def show_template_comparison(self, old_path, new_path, label, template_name):
        """显示模板替换前后对比"""
        try:
            # 创建对比图
            comparison_dialog = QDialog(self)
            comparison_dialog.setWindowTitle(f"{template_name} - 模板对比")
            comparison_dialog.setModal(True)
            comparison_dialog.resize(600, 300)
            
            layout = QVBoxLayout()
            
            # 标题
            title_label = QLabel(f"模板已更新：{template_name}")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
            layout.addWidget(title_label)
            
            # 对比图片
            images_layout = QHBoxLayout()
            
            # 旧模板
            old_layout = QVBoxLayout()
            old_layout.addWidget(QLabel("替换前"))
            old_label = QLabel()
            old_label.setFixedSize(250, 150)
            old_label.setStyleSheet("border: 1px solid #ccc;")
            old_label.setAlignment(Qt.AlignCenter)
            if os.path.exists(old_path):
                old_pixmap = QPixmap(old_path)
                if not old_pixmap.isNull():
                    old_label.setPixmap(old_pixmap.scaled(old_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            old_layout.addWidget(old_label)
            images_layout.addLayout(old_layout)
            
            # 箭头
            arrow_label = QLabel("→")
            arrow_label.setAlignment(Qt.AlignCenter)
            arrow_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
            images_layout.addWidget(arrow_label)
            
            # 新模板
            new_layout = QVBoxLayout()
            new_layout.addWidget(QLabel("替换后"))
            new_label = QLabel()
            new_label.setFixedSize(250, 150)
            new_label.setStyleSheet("border: 1px solid #ccc;")
            new_label.setAlignment(Qt.AlignCenter)
            if os.path.exists(new_path):
                new_pixmap = QPixmap(new_path)
                if not new_pixmap.isNull():
                    new_label.setPixmap(new_pixmap.scaled(new_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            new_layout.addWidget(new_label)
            images_layout.addLayout(new_layout)
            
            layout.addLayout(images_layout)
            
            # 确认按钮
            ok_btn = QPushButton("确定")
            ok_btn.clicked.connect(comparison_dialog.accept)
            ok_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; }")
            
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(ok_btn)
            layout.addLayout(btn_layout)
            
            comparison_dialog.setLayout(layout)
            comparison_dialog.exec_()
            
            # 更新示例图
            self.show_template_example(new_path, label)
            
        except Exception as e:
            print(f"显示模板对比失败: {e}")
    
    def on_screenshot(self):
        """截图按钮点击事件"""
        screenshot_path = self.take_screenshot()
        if screenshot_path:
            self.status_label.setText(f"截图成功：{os.path.basename(screenshot_path)}")
            
            # 自动配置混斗模式区域
            self.auto_config_multi_team()
    
    def auto_config_multi_team(self):
        """自动配置混斗模式区域"""
        if not self.current_screenshot:
            return
        
        # 自动截取 (952, 88, 998, 153) 区域
        region = (952, 88, 998, 153)
        
        # 检查是否有旧模板
        old_template_path = os.path.join(TEMPLATES_DIR, "multi_team_battle.png")
        has_old_template = os.path.exists(old_template_path)
        
        # 创建临时文件保存旧模板
        old_temp_path = None
        if has_old_template:
            old_temp_path = os.path.join(CACHE_DIR, "temp_old_multi_team_battle.png")
            try:
                # 确保缓存目录存在
                if not os.path.exists(CACHE_DIR):
                    os.makedirs(CACHE_DIR)
                import shutil
                shutil.copy2(old_template_path, old_temp_path)
            except:
                old_temp_path = None
        
        if self.template_manager.crop_and_save_template(self.current_screenshot, "multi_team_battle.png", region):
            self.multi_team_configured = True
            self.multi_team_status_label.setText("✅ 混斗模式识别：已配置")
            self.config_data['multi_team_region'] = region
            
            # 显示对比图（如果有旧模板）
            if has_old_template and old_temp_path:
                self.show_template_comparison(old_temp_path, old_template_path, self.multi_example_label, "混斗模式识别区域")
            else:
                self.show_template_example(old_template_path, self.multi_example_label)
            
            self.step_completed.emit(self.config_data)
        else:
            QMessageBox.warning(self, "错误", "自动配置混斗模式区域失败")
    
    def validate_step(self):
        """验证步骤是否完成"""
        return self.multi_team_configured


class ResultConfigStep(ConfigStep):
    """结算界面配置步骤"""
    
    def __init__(self, parent=None):
        # 先初始化必要的属性
        self.victory_configured = False
        self.no_vip_configured = False
        self.reward_regions_configured = False
        self.reward_regions = {}
        # 在调用父类初始化之前先设置这个属性
        self.current_reward_regions = self._get_default_reward_regions()
        
        super().__init__(
            "步骤3：结算界面配置",
            "请进入战斗结算界面，胜利图标和VIP状态检测将自动配置，您只需校准奖励区域。",
            parent
        )
        
        # 父类初始化完成后，尝试从代码中读取实际的奖励区域
        try:
            self.current_reward_regions = self.get_current_reward_regions()
        except:
            pass  # 如果读取失败，使用默认值
    
    def _get_default_reward_regions(self):
        """获取默认的奖励区域坐标"""
        return {
            "dollar_base": (1361, 425, 1398, 465),
            "dollar_extra": (1482, 425, 1519, 465),
            "gold_base": (1361, 498, 1398, 538),
            "gold_extra": (1482, 498, 1519, 538)
        }
    
    def setup_content(self, layout):
        """设置内容"""
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.screenshot_btn = QPushButton("📸 截取当前屏幕")
        self.screenshot_btn.clicked.connect(self.on_screenshot)
        self.screenshot_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 4px; font-size: 14px; } QPushButton:hover { background-color: #1976D2; }")
        
        self.calibrate_rewards_btn = QPushButton("校准奖励区域")
        self.calibrate_rewards_btn.clicked.connect(self.calibrate_reward_regions)
        self.calibrate_rewards_btn.setEnabled(False)
        
        button_layout.addWidget(self.screenshot_btn)
        button_layout.addWidget(self.calibrate_rewards_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 示例图展示区域
        example_group = QGroupBox("模板示例")
        example_layout = QHBoxLayout()
        
        # VIP状态检测示例
        vip_example_layout = QVBoxLayout()
        vip_example_layout.addWidget(QLabel("VIP状态检测 (自动)"))
        self.vip_example_label = QLabel("暂无图片")
        self.vip_example_label.setFixedSize(120, 80)
        self.vip_example_label.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.vip_example_label.setAlignment(Qt.AlignCenter)
        vip_example_layout.addWidget(self.vip_example_label)
        example_layout.addLayout(vip_example_layout)
        
        # 胜利图标示例
        victory_example_layout = QVBoxLayout()
        victory_example_layout.addWidget(QLabel("胜利图标"))
        self.victory_example_label = QLabel("暂无图片")
        self.victory_example_label.setFixedSize(120, 80)
        self.victory_example_label.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")
        self.victory_example_label.setAlignment(Qt.AlignCenter)
        victory_example_layout.addWidget(self.victory_example_label)
        example_layout.addLayout(victory_example_layout)
        
        example_layout.addStretch()
        example_group.setLayout(example_layout)
        layout.addWidget(example_group)
        
        # 奖励区域信息
        reward_info_group = QGroupBox("当前奖励区域坐标")
        reward_info_layout = QVBoxLayout()
        
        self.reward_info_labels = {}
        region_names = {
            'dollar_base': '美元基础',
            'dollar_extra': '美元额外',
            'gold_base': '黄金基础',
            'gold_extra': '黄金额外'
        }
        
        for region_key, region_name in region_names.items():
            coords = self.current_reward_regions.get(region_key, (0, 0, 0, 0))
            label = QLabel(f"{region_name}: ({coords[0]}, {coords[1]}, {coords[2]}, {coords[3]})")
            label.setStyleSheet("font-family: monospace; font-size: 12px; padding: 2px;")
            reward_info_layout.addWidget(label)
            self.reward_info_labels[region_key] = label
        
        reward_info_group.setLayout(reward_info_layout)
        layout.addWidget(reward_info_group)
        
        # 状态显示
        self.status_label = QLabel("请先截取屏幕")
        self.status_label.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.status_label)
        
        # 配置状态
        status_group = QGroupBox("配置状态")
        status_layout = QVBoxLayout()
        
        self.no_vip_status_label = QLabel("⏳ VIP状态检测：未配置")
        self.victory_status_label = QLabel("⏳ 胜利图标：未配置")
        self.rewards_status_label = QLabel("⏳ 奖励区域：未校准")
        
        status_layout.addWidget(self.no_vip_status_label)
        status_layout.addWidget(self.victory_status_label)
        status_layout.addWidget(self.rewards_status_label)
        status_group.setLayout(status_layout)
        
        layout.addWidget(status_group)
        
        # 加载现有模板示例
        self.load_existing_templates()
    
    def load_existing_templates(self):
        """加载现有模板作为示例"""
        # 加载VIP状态检测模板
        vip_template_path = os.path.join(TEMPLATES_DIR, "no_vip.png")
        if os.path.exists(vip_template_path):
            self.show_template_example(vip_template_path, self.vip_example_label)
        
        # 加载胜利图标模板
        victory_template_path = os.path.join(TEMPLATES_DIR, "shengli.png")
        if os.path.exists(victory_template_path):
            self.show_template_example(victory_template_path, self.victory_example_label)
    
    def show_template_example(self, template_path, label):
        """显示模板示例图"""
        try:
            pixmap = QPixmap(template_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"加载模板示例失败: {e}")
    
    def show_template_comparison(self, old_path, new_path, label, template_name):
        """显示模板替换前后对比"""
        try:
            # 创建对比图
            comparison_dialog = QDialog(self)
            comparison_dialog.setWindowTitle(f"{template_name} - 模板对比")
            comparison_dialog.setModal(True)
            comparison_dialog.resize(600, 300)
            
            layout = QVBoxLayout()
            
            # 标题
            title_label = QLabel(f"模板已更新：{template_name}")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
            layout.addWidget(title_label)
            
            # 对比图片
            images_layout = QHBoxLayout()
            
            # 旧模板
            old_layout = QVBoxLayout()
            old_layout.addWidget(QLabel("替换前"))
            old_label = QLabel()
            old_label.setFixedSize(250, 150)
            old_label.setStyleSheet("border: 1px solid #ccc;")
            old_label.setAlignment(Qt.AlignCenter)
            if os.path.exists(old_path):
                old_pixmap = QPixmap(old_path)
                if not old_pixmap.isNull():
                    old_label.setPixmap(old_pixmap.scaled(old_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            old_layout.addWidget(old_label)
            images_layout.addLayout(old_layout)
            
            # 箭头
            arrow_label = QLabel("→")
            arrow_label.setAlignment(Qt.AlignCenter)
            arrow_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
            images_layout.addWidget(arrow_label)
            
            # 新模板
            new_layout = QVBoxLayout()
            new_layout.addWidget(QLabel("替换后"))
            new_label = QLabel()
            new_label.setFixedSize(250, 150)
            new_label.setStyleSheet("border: 1px solid #ccc;")
            new_label.setAlignment(Qt.AlignCenter)
            if os.path.exists(new_path):
                new_pixmap = QPixmap(new_path)
                if not new_pixmap.isNull():
                    new_label.setPixmap(new_pixmap.scaled(new_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            new_layout.addWidget(new_label)
            images_layout.addLayout(new_layout)
            
            layout.addLayout(images_layout)
            
            # 确认按钮
            ok_btn = QPushButton("确定")
            ok_btn.clicked.connect(comparison_dialog.accept)
            ok_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; }")
            
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(ok_btn)
            layout.addLayout(btn_layout)
            
            comparison_dialog.setLayout(layout)
            comparison_dialog.exec_()
            
            # 更新示例图
            self.show_template_example(new_path, label)
            
        except Exception as e:
            print(f"显示模板对比失败: {e}")
    
    def on_screenshot(self):
        """截图按钮点击事件"""
        screenshot_path = self.take_screenshot()
        if screenshot_path:
            self.status_label.setText(f"截图成功：{os.path.basename(screenshot_path)}")
            self.calibrate_rewards_btn.setEnabled(True)
            
            # 询问当前是否有VIP
            self.check_vip_status()
            # 自动配置胜利图标
            self.auto_config_victory_icon()
    
    def check_vip_status(self):
        """检查VIP状态并决定是否配置VIP检测"""
        reply = QMessageBox.question(
            self,
            "VIP状态确认",
            "请确认当前游戏状态（★谨慎选择，瞎点代肝脚本报错★）：\n\n★您当前是否拥有VIP？★\n\n• 选择\"是\"：跳过VIP状态检测配置\n• 选择\"否\"：配置VIP状态检测模板",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 有VIP，跳过配置
            self.no_vip_configured = True
            self.no_vip_status_label.setText("✅ VIP状态检测：已跳过（当前有VIP）")
            self.config_data['no_vip_region'] = (1482, 425, 1519, 465)  # 使用默认区域
            self.check_completion()
        else:
            # 没有VIP，进行配置
            self.auto_config_no_vip()
    
    def auto_config_no_vip(self):
        """自动配置VIP状态检测区域"""
        if not self.current_screenshot:
            return
        
        # 自动截取 (1482, 425, 1519, 465) 区域
        region = (1482, 425, 1519, 465)
        
        # 检查是否有旧模板
        old_template_path = os.path.join(TEMPLATES_DIR, "no_vip.png")
        has_old_template = os.path.exists(old_template_path)
        
        # 创建临时文件保存旧模板
        old_temp_path = None
        if has_old_template:
            old_temp_path = os.path.join(CACHE_DIR, "temp_old_no_vip.png")
            try:
                # 确保缓存目录存在
                if not os.path.exists(CACHE_DIR):
                    os.makedirs(CACHE_DIR)
                import shutil
                shutil.copy2(old_template_path, old_temp_path)
            except:
                old_temp_path = None
        
        if self.template_manager.crop_and_save_template(self.current_screenshot, "no_vip.png", region):
            self.no_vip_configured = True
            self.no_vip_status_label.setText("✅ VIP状态检测：已配置")
            self.config_data['no_vip_region'] = region
            
            # 显示对比图（如果有旧模板）
            if has_old_template and old_temp_path:
                self.show_template_comparison(old_temp_path, old_template_path, self.vip_example_label, "VIP状态检测")
            else:
                self.show_template_example(old_template_path, self.vip_example_label)
            
            self.check_completion()
        else:
            QMessageBox.warning(self, "错误", "自动配置VIP状态检测区域失败")
    
    def auto_config_victory_icon(self):
        """自动配置胜利图标"""
        if not self.current_screenshot:
            return
        
        # 自动截取 (278, 32, 513, 123) 区域
        region = (278, 32, 513, 123)
        
        # 检查是否有旧模板
        old_template_path = os.path.join(TEMPLATES_DIR, "shengli.png")
        has_old_template = os.path.exists(old_template_path)
        
        # 创建临时文件保存旧模板
        old_temp_path = None
        if has_old_template:
            old_temp_path = os.path.join(CACHE_DIR, "temp_old_shengli.png")
            try:
                # 确保缓存目录存在
                if not os.path.exists(CACHE_DIR):
                    os.makedirs(CACHE_DIR)
                import shutil
                shutil.copy2(old_template_path, old_temp_path)
            except:
                old_temp_path = None
        
        if self.template_manager.crop_and_save_template(self.current_screenshot, "shengli.png", region):
            self.victory_configured = True
            self.victory_status_label.setText("✅ 胜利图标：已配置")
            self.config_data['victory_region'] = region
            
            # 显示对比图（如果有旧模板）
            if has_old_template and old_temp_path:
                self.show_template_comparison(old_temp_path, old_template_path, self.victory_example_label, "胜利图标")
            else:
                self.show_template_example(old_template_path, self.victory_example_label)
            
            self.check_completion()
        else:
            QMessageBox.warning(self, "错误", "保存胜利图标模板失败")
    
    def calibrate_reward_regions(self):
        """校准奖励区域"""
        if not self.current_screenshot:
            QMessageBox.warning(self, "错误", "请先截取屏幕")
            return
        
        calibrator = RewardRegionCalibrator(self.current_screenshot, self.current_reward_regions, self)
        if calibrator.exec_() == QDialog.Accepted:
            new_regions = calibrator.get_calibrated_regions()
            if new_regions:
                # 更新奖励区域
                if self.template_manager.update_reward_regions(new_regions):
                    self.reward_regions_configured = True
                    self.rewards_status_label.setText("✅ 奖励区域：已校准")
                    self.config_data['reward_regions'] = new_regions
                    self.reward_regions = new_regions
                    
                    # 更新显示的坐标信息
                    self.update_reward_info_labels(new_regions)
                    
                    self.check_completion()
                else:
                    QMessageBox.warning(self, "错误", "更新奖励区域代码失败")
    
    def update_reward_info_labels(self, regions):
        """更新奖励区域信息标签"""
        region_names = {
            'dollar_base': '美元基础',
            'dollar_extra': '美元额外',
            'gold_base': '黄金基础',
            'gold_extra': '黄金额外'
        }
        
        for region_key, region_name in region_names.items():
            if region_key in regions:
                coords = regions[region_key]
                self.reward_info_labels[region_key].setText(f"{region_name}: ({coords[0]}, {coords[1]}, {coords[2]}, {coords[3]})")
    
    def check_completion(self):
        """检查步骤是否完成"""
        if self.no_vip_configured and self.victory_configured and self.reward_regions_configured:
            self.step_completed.emit(self.config_data)
    
    def validate_step(self):
        """验证步骤是否完成"""
        return self.no_vip_configured and self.victory_configured and self.reward_regions_configured

    def get_current_reward_regions(self):
        """从代码中读取当前的奖励区域坐标"""
        default_regions = {
            "dollar_base": (1361, 425, 1398, 465),
            "dollar_extra": (1482, 425, 1519, 465),
            "gold_base": (1361, 498, 1398, 538),
            "gold_extra": (1482, 498, 1519, 538)
        }
        
        try:
            file_path = os.path.join(SCRIPT_DIR, "warship_auto_battle.py")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 使用正则表达式提取REWARD_REGIONS
                pattern = r'REWARD_REGIONS = \{([^}]+)\}'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    regions_text = match.group(1)
                    
                    # 解析各个区域
                    for region_key in ["dollar_base", "dollar_extra", "gold_base", "gold_extra"]:
                        region_pattern = rf'"{region_key}":\s*\(([^)]+)\)'
                        region_match = re.search(region_pattern, regions_text)
                        if region_match:
                            coords = region_match.group(1).split(',')
                            if len(coords) == 4:
                                try:
                                    default_regions[region_key] = tuple(int(x.strip()) for x in coords)
                                except ValueError:
                                    pass
        except Exception as e:
            print(f"读取奖励区域失败: {e}")
        
        return default_regions


class TemplateConfigTool(QMainWindow):
    """模板配置工具主窗口"""
    
    def __init__(self):
        super().__init__()
        self.device_id = None
        self.current_step = 0
        self.config_data = {}
        self.steps = []
        
        self.init_ui()
        self.init_steps()
        self.refresh_devices()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("现代战舰模板配置工具")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置应用图标
        self.setWindowIcon(QIcon())
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 标题
        title_label = QLabel("现代战舰模板配置工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #333; margin: 20px 0;")
        main_layout.addWidget(title_label)
        
        # 设备选择区域
        device_group = QGroupBox("设备选择")
        device_layout = QHBoxLayout()
        
        device_layout.addWidget(QLabel("选择设备："))
        
        self.device_combo = QComboBox()
        self.device_combo.currentTextChanged.connect(self.on_device_changed)
        device_layout.addWidget(self.device_combo)
        
        refresh_btn = QPushButton("刷新设备")
        refresh_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(refresh_btn)
        
        device_layout.addStretch()
        device_group.setLayout(device_layout)
        main_layout.addWidget(device_group)
        
        # 步骤导航
        nav_group = QGroupBox("配置步骤")
        nav_layout = QHBoxLayout()
        
        self.step_labels = []
        for i, step_name in enumerate(["主界面配置", "混斗模式配置", "结算界面配置"]):
            label = QLabel(f"{i+1}. {step_name}")
            label.setStyleSheet("padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f5f5f5;")
            nav_layout.addWidget(label)
            self.step_labels.append(label)
        
        nav_layout.addStretch()
        nav_group.setLayout(nav_layout)
        main_layout.addWidget(nav_group)
        
        # 步骤内容区域
        self.step_widget = QTabWidget()
        self.step_widget.setTabPosition(QTabWidget.North)
        main_layout.addWidget(self.step_widget)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("上一步")
        self.prev_btn.clicked.connect(self.prev_step)
        self.prev_btn.setEnabled(False)
        
        self.next_btn = QPushButton("下一步")
        self.next_btn.clicked.connect(self.next_step)
        self.next_btn.setEnabled(False)
        
        self.finish_btn = QPushButton("完成配置")
        self.finish_btn.clicked.connect(self.finish_config)
        self.finish_btn.setEnabled(False)
        
        control_layout.addStretch()
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.next_btn)
        control_layout.addWidget(self.finish_btn)
        
        main_layout.addLayout(control_layout)
        
        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("请选择设备开始配置")
    
    def init_steps(self):
        """初始化配置步骤"""
        # 创建步骤
        step1 = MainPageConfigStep(self)
        step2 = MultiTeamConfigStep(self)
        step3 = ResultConfigStep(self)
        
        self.steps = [step1, step2, step3]
        
        # 添加到标签页
        self.step_widget.addTab(step1, "步骤1：主界面配置")
        self.step_widget.addTab(step2, "步骤2：混斗模式配置")
        self.step_widget.addTab(step3, "步骤3：结算界面配置")
        
        # 连接信号
        for i, step in enumerate(self.steps):
            step.step_completed.connect(lambda data, idx=i: self.on_step_completed(idx, data))
        
        # 初始状态
        self.step_widget.setCurrentIndex(0)
        self.update_step_navigation()
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.device_combo.clear()
        try:
            devices = ADBHelper.getDevicesList()  # 修改方法名
            if devices:
                for device in devices:
                    self.device_combo.addItem(device)
                self.status_bar.showMessage(f"找到 {len(devices)} 个设备")
            else:
                self.device_combo.addItem("未找到设备")
                self.status_bar.showMessage("未找到设备，请检查ADB连接")
        except Exception as e:
            self.device_combo.addItem("获取设备失败")
            self.status_bar.showMessage(f"获取设备失败: {str(e)}")
    
    def on_device_changed(self, device_text):
        """设备选择改变"""
        if device_text and device_text != "未找到设备" and device_text != "获取设备失败":
            self.device_id = device_text
            # 设置所有步骤的设备ID
            for step in self.steps:
                step.set_device(device_text)
            self.next_btn.setEnabled(True)
            self.status_bar.showMessage(f"已选择设备: {device_text}")
        else:
            self.device_id = None
            self.next_btn.setEnabled(False)
            self.status_bar.showMessage("请选择有效设备")
    
    def update_step_navigation(self):
        """更新步骤导航显示"""
        for i, label in enumerate(self.step_labels):
            if i == self.current_step:
                label.setStyleSheet("padding: 10px; border: 2px solid #2196F3; border-radius: 4px; background-color: #E3F2FD; color: #1976D2; font-weight: bold;")
            elif i < self.current_step:
                label.setStyleSheet("padding: 10px; border: 1px solid #4CAF50; border-radius: 4px; background-color: #E8F5E8; color: #2E7D32;")
            else:
                label.setStyleSheet("padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f5f5f5;")
    
    def prev_step(self):
        """上一步"""
        if self.current_step > 0:
            self.current_step -= 1
            self.step_widget.setCurrentIndex(self.current_step)
            self.update_step_navigation()
            self.update_control_buttons()
    
    def next_step(self):
        """下一步"""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self.step_widget.setCurrentIndex(self.current_step)
            self.update_step_navigation()
            self.update_control_buttons()
    
    def update_control_buttons(self):
        """更新控制按钮状态"""
        self.prev_btn.setEnabled(self.current_step > 0)
        self.next_btn.setEnabled(self.current_step < len(self.steps) - 1 and self.device_id is not None)
        
        # 检查是否所有步骤都完成
        all_completed = all(step.validate_step() for step in self.steps)
        self.finish_btn.setEnabled(all_completed)
    
    def on_step_completed(self, step_index, data):
        """步骤完成处理"""
        self.config_data[f"step_{step_index}"] = data
        self.update_control_buttons()
        self.status_bar.showMessage(f"步骤 {step_index + 1} 配置完成")
        
        # 如果不是最后一步，自动进入下一步
        if step_index < len(self.steps) - 1:
            QTimer.singleShot(1000, self.next_step)  # 1秒后自动进入下一步
    
    def finish_config(self):
        """完成配置"""
        try:
            # 备份现有模板
            template_manager = TemplateManager(TEMPLATES_DIR)
            backup_dir, backed_up = template_manager.backup_templates()
            
            # 显示完成信息
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("配置完成")
            msg.setText("模板配置已完成！")
            
            detail_text = "配置详情：\n"
            detail_text += f"• 设备ID: {self.device_id}\n"
            detail_text += f"• 备份目录: {backup_dir}\n"
            detail_text += f"• 备份文件: {', '.join(backed_up)}\n"
            detail_text += f"• 配置步骤: {len([s for s in self.steps if s.validate_step()])} / {len(self.steps)}\n"
            
            msg.setDetailedText(detail_text)
            msg.exec_()
            
            # 清理临时文件
            self.cleanup_temp_files()
            
            self.status_bar.showMessage("配置完成，可以关闭工具")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"完成配置时发生错误: {str(e)}")
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            if os.path.exists(CACHE_DIR):
                import glob
                # 清理所有临时截图
                temp_screenshots = glob.glob(os.path.join(CACHE_DIR, "temp_screenshot_*.png"))
                # 清理所有临时旧模板
                temp_old_files = glob.glob(os.path.join(CACHE_DIR, "temp_old_*.png"))
                
                all_temp_files = temp_screenshots + temp_old_files
                for temp_file in all_temp_files:
                    try:
                        os.remove(temp_file)
                    except:
                        pass
        except:
            pass
    
    def closeEvent(self, event):
        """关闭事件"""
        self.cleanup_temp_files()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = TemplateConfigTool()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()