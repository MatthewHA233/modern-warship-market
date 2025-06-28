#!/usr/bin/env python3
"""
测试长按补偿参数配置
验证录制器和回放器是否正确使用配置的补偿参数
"""

import json
from action_recorder import ActionRecorder
from mobile_replayer import MobileReplayer

def test_compensation_settings():
    """测试长按补偿设置"""
    print("=== 测试长按补偿参数配置 ===\n")
    
    # 测试录制器
    print("1. 测试ActionRecorder长按补偿设置:")
    recorder = ActionRecorder()
    print(f"   默认补偿: {recorder.get_long_press_compensation()}ms")
    
    # 设置不同的补偿值
    test_values = [100, 200, 300]
    for value in test_values:
        recorder.set_long_press_compensation(value)
        actual = recorder.get_long_press_compensation()
        print(f"   设置{value}ms -> 实际{actual}ms {'✓' if actual == value else '✗'}")
    
    print()
    
    # 测试回放器
    print("2. 测试MobileReplayer长按补偿设置:")
    replayer = MobileReplayer()
    print(f"   默认补偿: {replayer.long_press_compensation}ms")
    
    # 设置不同的补偿值
    for value in test_values:
        replayer.set_long_press_compensation(value)
        actual = replayer.long_press_compensation
        print(f"   设置{value}ms -> 实际{actual}ms {'✓' if actual == value else '✗'}")
    
    print()
    
    # 测试配置文件读取
    print("3. 测试配置文件读取:")
    try:
        with open('battle_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        config_compensation = config.get('long_press_compensation', 150)
        print(f"   配置文件中的补偿值: {config_compensation}ms")
        
        # 验证设置是否生效
        recorder.set_long_press_compensation(config_compensation)
        replayer.set_long_press_compensation(config_compensation)
        
        recorder_actual = recorder.get_long_press_compensation()
        replayer_actual = replayer.long_press_compensation
        
        print(f"   录制器设置结果: {recorder_actual}ms {'✓' if recorder_actual == config_compensation else '✗'}")
        print(f"   回放器设置结果: {replayer_actual}ms {'✓' if replayer_actual == config_compensation else '✗'}")
        
    except Exception as e:
        print(f"   配置文件读取失败: {e}")
    
    print()
    print("=== 测试完成 ===")

if __name__ == "__main__":
    test_compensation_settings() 