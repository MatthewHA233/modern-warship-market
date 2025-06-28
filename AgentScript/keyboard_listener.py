import keyboard
import threading
import time
from typing import Callable
from game_config import *
import ADBHelper
import subprocess

class KeyboardListener:
    """键盘监听器类"""
    
    def __init__(self, recorder):
        self.recorder = recorder
        self.listening = False
        self.pressed_keys = set()  # 记录当前按下的按键
        self.key_press_times = {}  # 记录按键按下的时间
        self.key_timers = {}  # 记录按键的定时器
        self.callbacks = {}  # 回调函数字典
        self.view_mode = 'fast'  # 当前视角模式
        
        # 录制模式配置
        self.recording_mode = 'adb'  # 'adb' 或 'pc'
        self.pc_long_press_active = {}  # 记录PC模式下的长按状态
        
        # 预设长按时长配置
        self.preset_durations = {
            1: 100,   # 100ms
            2: 200,   # 200ms
            3: 300,   # 300ms
            4: 400,   # 400ms
            5: 500,   # 500ms
            6: 600,   # 600ms
            7: 700,   # 700ms
            8: 800,   # 800ms
            9: 900    # 900ms
        }
        self.current_preset = 3  # 默认使用300ms
        self.preset_mode = False  # 是否启用预设模式
        
    def start_listening(self, recording_mode='adb'):
        """开始监听键盘"""
        if self.listening:
            return
            
        self.recording_mode = recording_mode
        self.listening = True
        
        if recording_mode == 'pc':
            print("开始监听键盘输入 - 电脑端录制模式")
            print("只录制船体操控动作(WASD + 视角控制)")
            print("使用轮询方式检测按键释放")
            
            # 启动按键状态轮询线程
            self._start_polling_thread()
        else:
            print("开始监听键盘输入 - ADB录制模式")
            print(f"当前预设长按时长: {self.get_current_preset_info()}")
        
        # 注册按键事件
        keyboard.on_press(self._on_key_press)
        if recording_mode == 'adb':
            # 只有ADB模式才注册释放事件
            keyboard.on_release(self._on_key_release)
        
    def stop_listening(self):
        """停止监听键盘"""
        if not self.listening:
            return
            
        self.listening = False
        print("停止监听键盘输入")
        
        # 清理所有定时器
        for timer in self.key_timers.values():
            timer.cancel()
        self.key_timers.clear()
        
        # 结束所有未完成的长按操作
        device_id = self.recorder.device_id
        if device_id:
            for key_name in list(self.pressed_keys):
                if key_name in KEY_MAPPING:
                    action = KEY_MAPPING[key_name]
                    if action in ['left', 'right']:
                        position = MOVEMENT_CONTROLS[action]
                        ADBHelper.endLongPress(device_id, position)
        
        # 取消注册按键事件
        keyboard.unhook_all()
        
        # 清理所有状态变量
        self.pressed_keys.clear()
        self.key_press_times.clear()
        self.pc_long_press_active.clear()
        self.callbacks.clear()
        
        print("已清理所有键盘监听状态")
        
    def _on_key_press(self, event):
        """按键按下事件处理"""
        if not self.listening or not self.recorder.is_recording():
            return
        
        # 立即记录时间戳，减少处理延迟
        event_timestamp = time.time()
        relative_timestamp = event_timestamp - self.recorder.start_time if self.recorder.start_time else 0
            
        key_name = event.name.lower()
        current_time = time.time()
        
        # 处理Ctrl+数字键切换预设（只在ADB模式下有效）
        if self.recording_mode == 'adb' and keyboard.is_pressed('ctrl'):
            if key_name.isdigit() and key_name != '0':
                preset_num = int(key_name)
                if preset_num in self.preset_durations:
                    self.current_preset = preset_num
                    duration = self.preset_durations[preset_num]
                    print(f"切换到预设 {preset_num}: {duration}ms")
                    return
        
        # 视角控制按键（方向键）- 两种模式都支持
        if key_name in ['up', 'down', 'left', 'right']:
            self._handle_key_press(key_name, relative_timestamp)
            return
            
        # 视角模式切换按键 - 两种模式都支持
        if key_name in ['z', 'x']:
            self._handle_key_press(key_name, relative_timestamp)
            return
        
        # 检查是否在键位映射中
        if key_name in KEY_MAPPING:
            action = KEY_MAPPING[key_name]
            
            # PC模式：简化处理
            if self.recording_mode == 'pc':
                if action in MOVEMENT_CONTROLS:
                    position = MOVEMENT_CONTROLS[action]
                    
                    # 上下是点按
                    if action in ['up', 'down']:
                        # 使用事件开始时的时间戳
                        self.recorder.record_tap(key_name, position, timestamp=relative_timestamp)
                        print(f"录制PC点按: {action} -> {position}, 时间戳: {relative_timestamp:.3f}s")
                    
                    # 左右是长按 - 简化处理
                    elif action in ['left', 'right']:
                        # 避免重复按键
                        if key_name not in self.pressed_keys:
                            self.pressed_keys.add(key_name)
                            self.key_press_times[key_name] = event_timestamp  # 使用事件时间戳
                            print(f"PC长按开始: {action} -> {position}")
                return  # PC模式下忽略武器和特殊功能
            
            # ADB模式：处理所有操作
            else:
                # 对于点击类型的按键，允许连续点击
                if action in ['up', 'down'] or action in WEAPON_CONTROLS or action in SPECIAL_CONTROLS:
                    # 直接处理点击，不需要记录到pressed_keys
                    self._handle_key_press(key_name, relative_timestamp)
                    return
                    
                # 对于长按类型的按键，使用预设时长
                if action in ['left', 'right']:
                    position = MOVEMENT_CONTROLS[action]
                    
                    # 使用预设时长长按
                    duration = self.preset_durations[self.current_preset]
                    print(f"执行预设长按 - {key_name}, 时长: {duration}ms, 时间戳: {relative_timestamp:.3f}s")
                    
                    # 先录制预设长按动作（使用事件开始时的时间戳）
                    self.recorder.record_tap(key_name, position, duration=duration, timestamp=relative_timestamp)
                    
                    # 异步执行ADB预设长按操作，避免阻塞
                    device_id = self.recorder.device_id
                    if device_id:
                        def execute_async():
                            # 使用传统的长按方法，指定确切时长
                            self._execute_preset_long_press(device_id, position, duration)
                        thread = threading.Thread(target=execute_async, daemon=True)
                        thread.start()
                    
                    return
        
        # 处理其他按键
        if key_name not in self.pressed_keys:
            self.pressed_keys.add(key_name)
            self.key_press_times[key_name] = event_timestamp  # 使用事件时间戳
            self._handle_key_press(key_name, relative_timestamp)
        
    def _on_key_release(self, event):
        """按键释放事件处理"""
        if not self.listening or not self.recorder.is_recording():
            return
        
        # 立即记录时间戳，减少处理延迟
        event_timestamp = time.time()
        relative_timestamp = event_timestamp - self.recorder.start_time if self.recorder.start_time else 0
            
        key_name = event.name.lower()
        
        # 视角控制按键（方向键）- 不需要处理释放事件
        if key_name in ['up', 'down', 'left', 'right']:
            return
            
        # 视角模式切换按键 - 不需要处理释放事件
        if key_name in ['z', 'x']:
            return
        
        # 检查是否在键位映射中
        if key_name in KEY_MAPPING:
            action = KEY_MAPPING[key_name]
            
            # PC模式：轮询方式处理，这里不需要处理释放
            if self.recording_mode == 'pc':
                # PC模式下释放事件由轮询线程处理
                return
            
            # ADB模式：只有长按类型的按键需要处理释放事件
            else:
                if action in ['left', 'right']:
                    if key_name in self.pressed_keys:
                        print(f"处理长按释放 - {key_name}")
                        self.pressed_keys.remove(key_name)
                        self._handle_key_release(key_name, relative_timestamp)
                    else:
                        print(f"长按按键不在pressed_keys中 - {key_name}")
                    return
                    
                # 点击类型的按键不需要处理释放事件
                return
        
        # 处理其他按键的释放
        if key_name not in self.pressed_keys:
            return
            
        self.pressed_keys.remove(key_name)
        
        # 处理按键释放
        self._handle_key_release(key_name, relative_timestamp)
            
    def _handle_key_press(self, key_name: str, relative_timestamp: float):
        """处理按键按下"""
        try:
            device_id = self.recorder.device_id
            if not device_id:
                print("警告: 未设置设备ID")
                return
                
            # 视角模式切换
            if key_name == 'z':
                self.view_mode = 'slow'
                self.recorder.set_view_mode('slow')
                return
            elif key_name == 'x':
                self.view_mode = 'fast'
                self.recorder.set_view_mode('fast')
                return
                
            # 视角控制
            if key_name in ['up', 'down', 'left', 'right']:
                direction = f'view_{key_name}'
                # 使用事件开始时的时间戳
                self.recorder.record_view_control(direction, timestamp=relative_timestamp)
                
                # 异步执行视角控制的ADB操作，避免阻塞时间戳记录
                if self.recording_mode == 'adb':
                    # 创建独立线程执行ADB操作，不等待完成
                    def execute_async():
                        self._execute_view_control(key_name, device_id)
                    
                    thread = threading.Thread(target=execute_async, daemon=True)
                    thread.start()
                return
                
            # 检查是否在键位映射中
            if key_name not in KEY_MAPPING:
                return
                
            action = KEY_MAPPING[key_name]
            
            # 移动控制
            if action in MOVEMENT_CONTROLS:
                position = MOVEMENT_CONTROLS[action]
                
                # 上下是点按，左右是长按
                if action in ['up', 'down']:
                    # 先录制点按动作（使用事件开始时的时间戳）
                    self.recorder.record_tap(key_name, position, timestamp=relative_timestamp)
                    # 异步执行ADB点按操作，避免阻塞
                    def execute_async():
                        ADBHelper.touch(device_id, position)
                    thread = threading.Thread(target=execute_async, daemon=True)
                    thread.start()
                    print(f"执行点按操作: {action} -> {position}, 时间戳: {relative_timestamp:.3f}s")
                    
                elif action in ['left', 'right']:
                    # 先录制长按开始（使用事件开始时的时间戳）
                    self.recorder.record_long_press_start(key_name, position)
                    # 手动设置时间戳
                    if self.recorder.actions:
                        self.recorder.actions[-1]['timestamp'] = relative_timestamp
                    # 异步开始ADB长按，避免阻塞
                    def execute_async():
                        ADBHelper.startLongPress(device_id, position)
                    thread = threading.Thread(target=execute_async, daemon=True)
                    thread.start()
                    print(f"开始长按操作: {action} -> {position}, 时间戳: {relative_timestamp:.3f}s")
                    
            # 武器控制 - 点按
            elif action in WEAPON_CONTROLS:
                position = WEAPON_CONTROLS[action]
                # 先录制点按动作（使用事件开始时的时间戳）
                self.recorder.record_tap(key_name, position, timestamp=relative_timestamp)
                # 异步执行ADB点按操作，避免阻塞
                def execute_async():
                    ADBHelper.touch(device_id, position)
                thread = threading.Thread(target=execute_async, daemon=True)
                thread.start()
                print(f"执行武器发射: {action} -> {position}, 时间戳: {relative_timestamp:.3f}s")
                
            # 特殊功能 - 点按
            elif action in SPECIAL_CONTROLS:
                position = SPECIAL_CONTROLS[action]
                # 先录制点按动作（使用事件开始时的时间戳）
                self.recorder.record_tap(key_name, position, timestamp=relative_timestamp)
                # 异步执行ADB点按操作，避免阻塞
                def execute_async():
                    ADBHelper.touch(device_id, position)
                thread = threading.Thread(target=execute_async, daemon=True)
                thread.start()
                print(f"执行特殊功能: {action} -> {position}, 时间戳: {relative_timestamp:.3f}s")
                
        except Exception as e:
            print(f"处理按键按下时出错: {str(e)}")
            
    def _handle_key_release(self, key_name: str, relative_timestamp: float):
        """处理按键释放"""
        try:
            device_id = self.recorder.device_id
            if not device_id:
                return
                
            # 计算实际按下时长（使用绝对时间）
            actual_duration = 0
            if key_name in self.key_press_times:
                current_absolute_time = time.time()
                actual_duration = current_absolute_time - self.key_press_times[key_name]
                del self.key_press_times[key_name]
            
            # 只有长按类型的按键需要处理释放事件
            if key_name not in KEY_MAPPING:
                return
                
            action = KEY_MAPPING[key_name]
            
            # 只处理左右移动的长按释放
            if action in ['left', 'right']:
                position = MOVEMENT_CONTROLS[action]
                
                # 先录制长按结束（使用准确的时间戳）
                self.recorder.record_long_press_end(key_name, position)
                # 手动设置结束时间戳
                if self.recorder.actions:
                    # 查找最后一个匹配的长按动作并更新其结束时间戳
                    for i in range(len(self.recorder.actions) - 1, -1, -1):
                        action_record = self.recorder.actions[i]
                        if (action_record.get('key') == key_name and 
                            action_record.get('type') == 'long_press'):
                            action_record['end_timestamp'] = relative_timestamp
                            break
                
                # 异步结束ADB长按，避免阻塞
                def execute_async():
                    ADBHelper.endLongPress(device_id, position)
                thread = threading.Thread(target=execute_async, daemon=True)
                thread.start()
                print(f"结束长按操作: {action} -> {position}, 结束时间戳: {relative_timestamp:.3f}s, 实际时长: {actual_duration*1000:.0f}ms")
                
        except Exception as e:
            print(f"处理按键释放时出错: {str(e)}")
            
    def _execute_view_control(self, direction: str, device_id: str):
        """执行视角控制的ADB操作"""
        try:
            # 根据当前视角模式设置滑动参数
            speed = VIEW_CONTROL['slow_speed'] if self.view_mode == 'slow' else VIEW_CONTROL['fast_speed']
            # 慢速模式使用更小的滑动距离
            distance = VIEW_CONTROL['slow_swipe_distance'] if self.view_mode == 'slow' else VIEW_CONTROL['swipe_distance']
            
            # 计算滑动的起点和终点
            center_x, center_y = SCREEN_CENTER
            
            if direction == 'up':
                start_pos = (center_x, center_y)
                end_pos = (center_x, center_y - distance)
            elif direction == 'down':
                start_pos = (center_x, center_y)
                end_pos = (center_x, center_y + distance)
            elif direction == 'left':
                start_pos = (center_x, center_y)
                end_pos = (center_x - distance, center_y)
            elif direction == 'right':
                start_pos = (center_x, center_y)
                end_pos = (center_x + distance, center_y)
            else:
                return
                
            # 执行滑动操作
            ADBHelper.slide(device_id, start_pos, end_pos, speed)
            print(f"执行视角控制: {direction} ({self.view_mode}模式) 距离: {distance}px, {start_pos} -> {end_pos}")
            
        except Exception as e:
            print(f"执行视角控制出错: {str(e)}")
            
    def register_callback(self, key: str, callback: Callable):
        """注册按键回调函数"""
        self.callbacks[key] = callback
        
    def unregister_callback(self, key: str):
        """取消注册按键回调函数"""
        if key in self.callbacks:
            del self.callbacks[key]
            
    def is_listening(self):
        """检查是否正在监听"""
        return self.listening
        
    def get_pressed_keys(self):
        """获取当前按下的按键列表"""
        return list(self.pressed_keys)
        
    def get_view_mode(self):
        """获取当前视角模式"""
        return self.view_mode
        
    def _execute_preset_long_press(self, device_id: str, position: tuple, duration: int):
        """执行预设时长的长按操作"""
        try:
            x, y = position
            # 使用swipe命令模拟长按，起点和终点相同
            cmd = f"adb -s {device_id} shell input swipe {x} {y} {x} {y} {duration}"
            subprocess.run(cmd, shell=True, capture_output=True, timeout=max(2, duration/1000 + 1))
            print(f"执行预设长按: {position}, 持续时间: {duration}ms")
            return True
        except Exception as e:
            print(f"预设长按失败: {str(e)}")
            return False
            
    def get_current_preset_info(self):
        """获取当前预设信息"""
        duration = self.preset_durations[self.current_preset]
        return f"预设 {self.current_preset}: {duration}ms"

    def _handle_pc_movement(self, key_name: str, action: str, current_time: float):
        """处理PC模式下的移动控制"""
        try:
            position = MOVEMENT_CONTROLS[action]
            
            # 上下是点按，左右是长按
            if action in ['up', 'down']:
                # 录制点按动作（不执行ADB）
                self.recorder.record_tap(key_name, position)
                print(f"录制PC点按: {action} -> {position}")
                
            elif action in ['left', 'right']:
                # 开始长按（不执行ADB）
                if key_name not in self.pc_long_press_active:
                    self.pc_long_press_active[key_name] = current_time
                    # 同时添加到pressed_keys和key_press_times以便释放时能找到
                    self.pressed_keys.add(key_name)
                    self.key_press_times[key_name] = current_time
                    self.recorder.record_long_press_start(key_name, position)
                    print(f"录制PC长按开始: {action} -> {position}")
                    
        except Exception as e:
            print(f"处理PC移动时出错: {str(e)}")

    def _start_polling_thread(self):
        """启动按键状态轮询线程"""
        def polling_thread():
            """按键状态轮询线程"""
            while self.listening and self.recording_mode == 'pc':
                current_time = time.time()
                
                # 检查已按下的按键是否还在按下状态
                keys_to_remove = []
                for key_name, start_time in list(self.key_press_times.items()):
                    if not keyboard.is_pressed(key_name):
                        # 按键已释放，处理PC模式下的长按
                        if key_name in KEY_MAPPING:
                            action = KEY_MAPPING[key_name]
                            if action in ['left', 'right'] and key_name in self.pressed_keys:
                                position = MOVEMENT_CONTROLS[action]
                                duration = (current_time - start_time) * 1000
                                
                                # 计算相对于录制开始的时间戳
                                relative_start_time = start_time - self.recorder.start_time if self.recorder.start_time else 0
                                
                                # 录制完整的长按动作，使用按键开始时的时间戳
                                self.recorder.record_tap(
                                    key_name, 
                                    position, 
                                    duration=int(duration),
                                    timestamp=relative_start_time
                                )
                                print(f"录制PC长按完成: {action} -> 开始时间戳: {relative_start_time:.3f}s, 持续时间 {duration:.0f}ms")
                                
                                # 清理状态
                                self.pressed_keys.discard(key_name)
                        
                        keys_to_remove.append(key_name)
                
                # 移除已释放的按键
                for key_name in keys_to_remove:
                    if key_name in self.key_press_times:
                        del self.key_press_times[key_name]
                
                time.sleep(0.01)  # 10ms轮询间隔，提高精度
        
        # 启动守护线程
        thread = threading.Thread(target=polling_thread, daemon=True)
        thread.start()

    def clear_states(self):
        """清理所有状态变量"""
        # 清理所有定时器
        for timer in self.key_timers.values():
            timer.cancel()
        self.key_timers.clear()
        
        # 清理所有状态变量
        self.pressed_keys.clear()
        self.key_press_times.clear()
        self.pc_long_press_active.clear()
        self.callbacks.clear()
        
        print("已清理键盘监听器状态")

# 测试用的主函数
def main():
    """测试键盘监听功能"""
    print("=== 键盘监听测试模式 ===")
    print("由于释放事件可能不工作，改用状态轮询方式")
    print("按 Ctrl+C 退出测试")
    print()
    
    # 简单的测试变量
    pressed_keys = {}  # 记录按键状态和开始时间
    
    def test_on_key_press(event):
        """测试按键按下"""
        key_name = event.name.lower()
        current_time = time.time()
        
        if key_name not in pressed_keys:
            pressed_keys[key_name] = current_time
            print(f"[按下] {key_name} - 时间: {current_time:.3f}")
            
            # 特别关注WASD键
            if key_name in ['w', 'a', 's', 'd']:
                print(f"  >>> 检测到移动键: {key_name}")
    
    # 只注册按下事件
    keyboard.on_press(test_on_key_press)
    
    print("开始监听键盘事件...")
    print("使用轮询方式检测按键释放...")
    print("请测试按键，特别是 A 和 D 键的长按...")
    print()
    
    try:
        # 保持程序运行，并轮询检查按键状态
        while True:
            current_time = time.time()
            
            # 检查已按下的按键是否还在按下状态
            keys_to_remove = []
            for key_name, start_time in pressed_keys.items():
                if not keyboard.is_pressed(key_name):
                    # 按键已释放
                    duration = (current_time - start_time) * 1000
                    print(f"[释放] {key_name} - 持续时间: {duration:.0f}ms")
                    
                    # 特别关注WASD键
                    if key_name in ['w', 'a', 's', 'd']:
                        print(f"  >>> 移动键释放: {key_name}, 持续: {duration:.0f}ms")
                    
                    keys_to_remove.append(key_name)
            
            # 移除已释放的按键
            for key_name in keys_to_remove:
                del pressed_keys[key_name]
            
            time.sleep(0.05)  # 50ms轮询间隔
            
    except KeyboardInterrupt:
        print("\n测试结束")
        keyboard.unhook_all()
        print("已清理键盘钩子")

if __name__ == "__main__":
    main() 