#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量更新recording文件中的按钮坐标
根据game_config.py中的配置自动修改所有recording文件中的对应按钮坐标
"""

import json
import os
import sys
from pathlib import Path

# 导入游戏配置
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from game_config import MOVEMENT_CONTROLS, WEAPON_CONTROLS, SPECIAL_CONTROLS, KEY_MAPPING

def get_coordinate_for_key(key):
    """根据按键获取对应的坐标"""
    # 先通过KEY_MAPPING获取对应的控制类型
    if key in KEY_MAPPING:
        control_type = KEY_MAPPING[key]
        
        # 在移动控制中查找
        if control_type in MOVEMENT_CONTROLS:
            return MOVEMENT_CONTROLS[control_type]
        
        # 在特殊功能中查找
        if control_type in SPECIAL_CONTROLS:
            return SPECIAL_CONTROLS[control_type]
    
    # 直接在武器控制中查找
    if key in WEAPON_CONTROLS:
        return WEAPON_CONTROLS[key]
    
    return None

def update_recording_file(file_path):
    """更新单个recording文件的坐标"""
    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        updated_count = 0
        
        # 遍历所有actions
        if 'actions' in data:
            for action in data['actions']:
                if 'key' in action and 'position' in action:
                    key = action['key']
                    new_coordinate = get_coordinate_for_key(key)
                    
                    if new_coordinate:
                        old_position = action['position']
                        action['position'] = list(new_coordinate)
                        updated_count += 1
                        print(f"  更新按键 '{key}': {old_position} -> {list(new_coordinate)}")
        
        if updated_count > 0:
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  ✓ 成功更新 {updated_count} 个坐标")
        else:
            print(f"  - 没有需要更新的坐标")
            
        return updated_count
        
    except Exception as e:
        print(f"  ✗ 处理文件时出错: {e}")
        return 0

def main():
    """主函数"""
    print("=== 批量更新recording文件坐标 ===\n")
    
    # 获取recording文件夹路径
    recording_dir = Path(__file__).parent / "recording"
    
    if not recording_dir.exists():
        print(f"错误: recording文件夹不存在: {recording_dir}")
        return
    
    # 显示当前配置
    print("当前配置的坐标:")
    print("移动控制:")
    for key, coord in MOVEMENT_CONTROLS.items():
        print(f"  {key}: {coord}")
    
    print("\n武器控制:")
    for key, coord in WEAPON_CONTROLS.items():
        print(f"  {key}: {coord}")
    
    print("\n特殊功能:")
    for key, coord in SPECIAL_CONTROLS.items():
        print(f"  {key}: {coord}")
    
    print("\n" + "="*50)
    
    # 获取所有JSON文件
    json_files = list(recording_dir.glob("*.json"))
    
    if not json_files:
        print("没有找到任何JSON文件")
        return
    
    print(f"找到 {len(json_files)} 个recording文件\n")
    
    # 确认是否继续
    response = input("是否继续更新所有文件? (y/n): ").strip().lower()
    if response != 'y':
        print("操作已取消")
        return
    
    print("\n开始更新文件...")
    
    total_updated = 0
    
    # 处理每个文件
    for json_file in json_files:
        print(f"\n处理文件: {json_file.name}")
        updated_count = update_recording_file(json_file)
        total_updated += updated_count
    
    print(f"\n=== 更新完成 ===")
    print(f"总共更新了 {total_updated} 个坐标")
    print(f"处理了 {len(json_files)} 个文件")

if __name__ == "__main__":
    main() 