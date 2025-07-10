#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分辨率自适应模块
用于处理不同分辨率下的坐标转换和区域缩放
"""

import os
from game_config import ADBHelper

class ResolutionAdapter:
    """分辨率适配器"""
    
    # 基准分辨率（游戏设计时的标准分辨率）
    BASE_WIDTH = 2560
    BASE_HEIGHT = 1440
    
    def __init__(self, device_id=None):
        self.device_id = device_id
        self.current_width = self.BASE_WIDTH
        self.current_height = self.BASE_HEIGHT
        self.scale_x = 1.0
        self.scale_y = 1.0
        
        # 自动检测设备分辨率
        if device_id:
            self.detect_resolution()
    
    def detect_resolution(self):
        """检测设备实际分辨率"""
        try:
            # 使用ADB获取设备分辨率
            result = ADBHelper.execute_command(
                self.device_id, 
                ["shell", "wm", "size"]
            )
            
            if result and "Physical size:" in result:
                # 解析输出格式: "Physical size: 1920x1080"
                size_str = result.split("Physical size:")[-1].strip()
                width, height = map(int, size_str.split('x'))
                
                self.current_width = width
                self.current_height = height
                self.scale_x = width / self.BASE_WIDTH
                self.scale_y = height / self.BASE_HEIGHT
                
                print(f"检测到设备分辨率: {width}x{height}")
                print(f"缩放比例: X={self.scale_x:.2f}, Y={self.scale_y:.2f}")
                
                return True
            else:
                print("无法获取设备分辨率，使用默认值")
                return False
                
        except Exception as e:
            print(f"检测分辨率失败: {e}")
            return False
    
    def adapt_point(self, x, y):
        """
        将基准分辨率的坐标转换为当前分辨率的坐标
        
        Args:
            x: 基准分辨率下的X坐标
            y: 基准分辨率下的Y坐标
            
        Returns:
            tuple: (scaled_x, scaled_y) 适配后的坐标
        """
        scaled_x = int(x * self.scale_x)
        scaled_y = int(y * self.scale_y)
        return (scaled_x, scaled_y)
    
    def adapt_region(self, x1, y1, x2, y2):
        """
        将基准分辨率的区域转换为当前分辨率的区域
        
        Args:
            x1, y1: 区域左上角坐标
            x2, y2: 区域右下角坐标
            
        Returns:
            tuple: (scaled_x1, scaled_y1, scaled_x2, scaled_y2) 适配后的区域
        """
        scaled_x1 = int(x1 * self.scale_x)
        scaled_y1 = int(y1 * self.scale_y)
        scaled_x2 = int(x2 * self.scale_x)
        scaled_y2 = int(y2 * self.scale_y)
        return (scaled_x1, scaled_y1, scaled_x2, scaled_y2)
    
    def adapt_distance(self, distance, direction='both'):
        """
        适配距离值（用于滑动等操作）
        
        Args:
            distance: 基准分辨率下的距离
            direction: 'x', 'y', 或 'both'
            
        Returns:
            int or tuple: 适配后的距离
        """
        if direction == 'x':
            return int(distance * self.scale_x)
        elif direction == 'y':
            return int(distance * self.scale_y)
        else:  # both
            return (int(distance * self.scale_x), int(distance * self.scale_y))
    
    def get_screen_center(self):
        """获取当前分辨率的屏幕中心点"""
        return (self.current_width // 2, self.current_height // 2)
    
    def adapt_controls(self, controls_dict):
        """
        批量适配控制坐标字典
        
        Args:
            controls_dict: 包含坐标的字典
            
        Returns:
            dict: 适配后的坐标字典
        """
        adapted = {}
        for key, value in controls_dict.items():
            if isinstance(value, tuple) and len(value) == 2:
                adapted[key] = self.adapt_point(value[0], value[1])
            else:
                adapted[key] = value
        return adapted
    
    def get_resolution_info(self):
        """获取分辨率信息"""
        return {
            'base': f"{self.BASE_WIDTH}x{self.BASE_HEIGHT}",
            'current': f"{self.current_width}x{self.current_height}",
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'is_adapted': self.scale_x != 1.0 or self.scale_y != 1.0
        }


# 全局适配器实例
_adapter = None

def get_adapter(device_id=None):
    """获取全局适配器实例"""
    global _adapter
    if _adapter is None or (device_id and device_id != _adapter.device_id):
        _adapter = ResolutionAdapter(device_id)
    return _adapter

def adapt_point(x, y, device_id=None):
    """便捷函数：适配单个坐标点"""
    adapter = get_adapter(device_id)
    return adapter.adapt_point(x, y)

def adapt_region(x1, y1, x2, y2, device_id=None):
    """便捷函数：适配区域"""
    adapter = get_adapter(device_id)
    return adapter.adapt_region(x1, y1, x2, y2)

def adapt_all_game_controls(device_id=None):
    """适配所有游戏控制坐标"""
    from game_config import (
        MOVEMENT_CONTROLS, WEAPON_CONTROLS, 
        SPECIAL_CONTROLS, SCREEN_CENTER
    )
    
    adapter = get_adapter(device_id)
    
    # 适配后的控制坐标
    adapted_controls = {
        'movement': adapter.adapt_controls(MOVEMENT_CONTROLS),
        'weapons': adapter.adapt_controls(WEAPON_CONTROLS),
        'special': adapter.adapt_controls(SPECIAL_CONTROLS),
        'screen_center': adapter.get_screen_center()
    }
    
    return adapted_controls


if __name__ == "__main__":
    # 测试代码
    print("分辨率适配器测试")
    print("-" * 50)
    
    # 获取设备列表
    devices = ADBHelper.get_devices()
    if devices:
        device_id = devices[0]
        print(f"使用设备: {device_id}")
        
        # 创建适配器
        adapter = ResolutionAdapter(device_id)
        
        # 显示分辨率信息
        info = adapter.get_resolution_info()
        print(f"\n分辨率信息:")
        print(f"基准分辨率: {info['base']}")
        print(f"当前分辨率: {info['current']}")
        print(f"缩放比例: X={info['scale_x']:.2f}, Y={info['scale_y']:.2f}")
        
        # 测试坐标转换
        print(f"\n坐标转换测试:")
        test_points = [
            (1280, 720),  # 屏幕中心
            (2049, 717),  # 1号武器
            (442, 702),   # 上移动
        ]
        
        for x, y in test_points:
            adapted_x, adapted_y = adapter.adapt_point(x, y)
            print(f"({x}, {y}) -> ({adapted_x}, {adapted_y})")
        
        # 测试区域转换
        print(f"\n区域转换测试:")
        test_region = (2109, 40, 2254, 92)  # 检测区域
        adapted_region = adapter.adapt_region(*test_region)
        print(f"{test_region} -> {adapted_region}")
        
    else:
        print("没有检测到设备") 