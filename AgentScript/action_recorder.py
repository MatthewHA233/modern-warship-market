import time
import json
from datetime import datetime
from typing import List, Dict, Any
from game_config import *
import threading

class ActionRecorder:
    """动作录制器类"""
    
    def __init__(self):
        self.actions: List[Dict[str, Any]] = []
        self.recording = False
        self.start_time = None
        self.current_view_mode = 'fast'  # 默认快速视角模式
        self.device_id = ""
        self.pc_replay_file = None  # 记录使用的PC回放文件
        self.pc_replay_actions = []  # 存储PC回放的动作
        self.long_press_compensation = 150  # 长按补偿时间(ms)，默认150ms
        
    def start_recording(self, device_id: str = "", clear_existing: bool = True):
        """开始录制
        
        Args:
            device_id: 设备ID
            clear_existing: 是否清空现有动作，默认True
        """
        self.device_id = device_id
        
        if clear_existing:
            self.actions.clear()
            self.pc_replay_file = None
            self.pc_replay_actions = []
            print("开始新录制，已清空现有动作...")
        else:
            print(f"继续录制，当前已有 {len(self.actions)} 个动作...")
            
        self.recording = True
        self.start_time = time.time()
        print("开始录制动作...")
        
    def stop_recording(self):
        """停止录制"""
        self.recording = False
        print(f"录制结束，共录制 {len(self.actions)} 个动作")
        
    def is_recording(self):
        """检查是否正在录制"""
        return self.recording
        
    def get_current_time(self):
        """获取当前录制时间(相对于开始时间)"""
        if self.start_time is None:
            return 0
        return time.time() - self.start_time
        
    def record_tap(self, key: str, position: tuple, duration: int = None, timestamp: float = None):
        """录制点击动作"""
        if not self.recording:
            return
            
        if duration is None:
            duration = DEFAULT_PARAMS['tap_duration']
        
        if timestamp is None:
            timestamp = self.get_current_time()
            
        action = {
            'type': 'tap',
            'key': key,
            'position': position,
            'timestamp': timestamp,
            'duration': duration,
            'executed': True  # 标记已执行ADB操作
        }
        self.actions.append(action)
        print(f"录制点击: {key} -> {position}, 时间戳: {timestamp:.3f}s, 持续时间: {duration}ms")
        
    def record_long_press_start(self, key: str, position: tuple):
        """录制长按开始"""
        if not self.recording:
            return
            
        action = {
            'type': 'long_press_start',
            'key': key,
            'position': position,
            'timestamp': self.get_current_time(),
            'executed': True  # 标记已执行ADB操作
        }
        self.actions.append(action)
        print(f"录制长按开始: {key} -> {position}")
        
    def record_long_press_end(self, key: str, position: tuple):
        """录制长按结束"""
        if not self.recording:
            return
            
        # 查找对应的长按开始动作
        start_action = None
        for i in range(len(self.actions) - 1, -1, -1):
            if (self.actions[i]['type'] == 'long_press_start' and 
                self.actions[i]['key'] == key):
                start_action = self.actions[i]
                break
                
        if start_action:
            duration = (self.get_current_time() - start_action['timestamp']) * 1000  # 转换为毫秒
            duration = max(duration, DEFAULT_PARAMS['long_press_duration'])  # 最小持续时间
            
            # 更新开始动作为完整的长按动作
            start_action.update({
                'type': 'long_press',
                'duration': int(duration),
                'end_timestamp': self.get_current_time(),
                'actual_duration': int(duration)  # 记录实际持续时间
            })
            print(f"录制长按结束: {key} -> 持续时间 {int(duration)}ms")
        else:
            print(f"警告: 未找到对应的长按开始动作: {key}")
            
    def record_swipe(self, start_pos: tuple, end_pos: tuple, duration: int = None):
        """录制滑动动作"""
        if not self.recording:
            return
            
        if duration is None:
            duration = DEFAULT_PARAMS['swipe_duration']
            
        action = {
            'type': 'swipe',
            'start_position': start_pos,
            'end_position': end_pos,
            'timestamp': self.get_current_time(),
            'duration': duration
        }
        self.actions.append(action)
        print(f"录制滑动: {start_pos} -> {end_pos}, 持续时间: {duration}ms")
        
    def record_view_control(self, direction: str, timestamp: float = None):
        """录制视角控制"""
        if not self.recording:
            return
            
        if timestamp is None:
            timestamp = self.get_current_time()
            
        # 根据当前视角模式设置滑动参数
        speed = VIEW_CONTROL['slow_speed'] if self.current_view_mode == 'slow' else VIEW_CONTROL['fast_speed']
        # 慢速模式使用更小的滑动距离
        distance = VIEW_CONTROL['slow_swipe_distance'] if self.current_view_mode == 'slow' else VIEW_CONTROL['swipe_distance']
        
        # 计算滑动的起点和终点
        center_x, center_y = SCREEN_CENTER
        
        if direction == 'view_up':
            start_pos = (center_x, center_y)
            end_pos = (center_x, center_y - distance)
        elif direction == 'view_down':
            start_pos = (center_x, center_y)
            end_pos = (center_x, center_y + distance)
        elif direction == 'view_left':
            start_pos = (center_x, center_y)
            end_pos = (center_x - distance, center_y)
        elif direction == 'view_right':
            start_pos = (center_x, center_y)
            end_pos = (center_x + distance, center_y)
        else:
            return
            
        action = {
            'type': 'view_control',
            'direction': direction,
            'mode': self.current_view_mode,
            'start_position': start_pos,
            'end_position': end_pos,
            'timestamp': timestamp,
            'duration': speed
        }
        self.actions.append(action)
        print(f"录制视角控制: {direction} ({self.current_view_mode}模式), 距离: {distance}px, 时间戳: {timestamp:.3f}s")
        
    def set_view_mode(self, mode: str):
        """设置视角控制模式"""
        if mode in ['slow', 'fast']:
            self.current_view_mode = mode
            print(f"视角控制模式切换为: {mode}")
            
    def get_actions(self):
        """获取录制的动作列表"""
        return self.actions.copy()
        
    def clear_actions(self):
        """清空录制的动作"""
        self.actions.clear()
        self.recording = False
        self.start_time = None
        print("已清空录制的动作和状态")
        
    def save_to_file(self, filename: str):
        """保存录制结果到文件，如果使用了PC回放则自动合并"""
        try:
            # 如果使用了PC回放文件，则自动合并
            if self.pc_replay_file and self.pc_replay_actions:
                merged_actions = self._merge_with_pc_actions()
                total_duration = self.get_current_time() if self.start_time else 0
                
                data = {
                    'device_id': self.device_id,
                    'pc_replay_file': self.pc_replay_file,
                    'total_duration': total_duration,
                    'total_actions': len(merged_actions),
                    'adb_actions_count': len(self.actions),
                    'pc_actions_count': len(self.pc_replay_actions),
                    'created_time': datetime.now().isoformat(),
                    'auto_merged': True,
                    'actions': merged_actions
                }
                print(f"自动合并PC回放文件: {self.pc_replay_file}")
                print(f"ADB动作: {len(self.actions)} 个, PC动作: {len(self.pc_replay_actions)} 个")
                print(f"合并后总计: {len(merged_actions)} 个动作")
            else:
                # 没有使用PC回放，正常保存
                data = {
                    'device_id': self.device_id,
                    'total_duration': self.get_current_time() if self.start_time else 0,
                    'total_actions': len(self.actions),
                    'created_time': datetime.now().isoformat(),
                    'actions': self.actions
                }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"录制结果已保存到: {filename}")
            return True
        except Exception as e:
            print(f"保存文件失败: {str(e)}")
            return False
            
    def load_from_file(self, filename: str):
        """从文件加载录制结果"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.actions = data.get('actions', [])
            self.device_id = data.get('device_id', '')
            
            # 重置录制状态
            self.recording = False
            self.start_time = None
            
            print(f"已加载录制文件: {filename}")
            print(f"共加载 {len(self.actions)} 个动作")
            return True
        except Exception as e:
            print(f"加载文件失败: {str(e)}")
            return False
            
    def get_statistics(self):
        """获取录制统计信息"""
        if not self.actions:
            return {}
        
        # 计算总时长：如果正在录制，使用当前时间；否则使用最后一个动作的时间戳
        if self.recording and self.start_time:
            total_duration = self.get_current_time()
        elif self.actions:
            # 从动作中计算总时长
            max_timestamp = max(action.get('timestamp', 0) for action in self.actions)
            total_duration = max_timestamp
        else:
            total_duration = 0
            
        stats = {
            'total_actions': len(self.actions),
            'total_duration': total_duration,
            'action_types': {},
            'key_usage': {}
        }
        
        for action in self.actions:
            action_type = action['type']
            stats['action_types'][action_type] = stats['action_types'].get(action_type, 0) + 1
            
            if 'key' in action:
                key = action['key']
                stats['key_usage'][key] = stats['key_usage'].get(key, 0) + 1
                
        return stats
        
    def modify_last_action(self, key: str, new_type: str, **kwargs):
        """修改最后一个匹配的动作"""
        if not self.actions:
            return False
            
        # 从后往前查找匹配的动作
        for i in range(len(self.actions) - 1, -1, -1):
            action = self.actions[i]
            if action.get('key') == key:
                # 更新动作类型和其他参数
                action['type'] = new_type
                action.update(kwargs)
                print(f"修改动作: {key} -> {new_type}")
                return True
                
        return False
        
    def get_last_action(self, key: str = None):
        """获取最后一个动作（可选择指定按键）"""
        if not self.actions:
            return None
            
        if key is None:
            return self.actions[-1]
            
        # 查找指定按键的最后一个动作
        for i in range(len(self.actions) - 1, -1, -1):
            if self.actions[i].get('key') == key:
                return self.actions[i]
                
        return None
        
    def replay_pc_actions(self, pc_file: str):
        """回放PC端录制的船体操控动作（用于ADB录制时的同步）"""
        try:
            # 记录使用的PC回放文件
            self.pc_replay_file = pc_file
            
            # 加载PC端录制文件
            with open(pc_file, 'r', encoding='utf-8') as f:
                pc_data = json.load(f)
            pc_actions = pc_data.get('actions', [])
            
            # 存储PC回放动作用于后续合并
            self.pc_replay_actions = pc_actions.copy()
            
            if not pc_actions:
                print("PC录制文件中没有动作")
                return False
            
            print(f"开始回放PC端录制动作，共 {len(pc_actions)} 个")
            
            # 使用ADB录制的时间基准，而不是重新设置时间基准
            if not self.start_time:
                print("警告: ADB录制尚未开始，无法确定时间基准")
                return False
                
            # 计算PC回放开始时相对于ADB录制开始的时间偏移
            pc_replay_start_time = time.time()
            time_offset = pc_replay_start_time - self.start_time
            
            print(f"ADB录制开始时间: {self.start_time}")
            print(f"PC回放开始时间: {pc_replay_start_time}")
            print(f"时间偏移: {time_offset:.3f}秒")
            
            # 为每个动作创建独立的延迟执行线程，避免累积延迟
            def schedule_action(action):
                """为单个动作安排执行时间"""
                original_timestamp = action.get('timestamp', 0)
                # 调整时间戳：PC动作的原始时间戳 + 时间偏移
                adjusted_timestamp = original_timestamp + time_offset
                
                def execute_delayed():
                    # 计算动作应该执行的绝对时间（基于ADB录制开始时间）
                    target_absolute_time = self.start_time + adjusted_timestamp
                    
                    # 等待到指定的绝对时间点
                    current_time = time.time()
                    delay = target_absolute_time - current_time
                    
                    if delay > 0:
                        time.sleep(delay)
                    
                    # 执行ADB操作
                    if self.device_id:
                        self._execute_pc_action_on_device(action)
                
                # 启动独立的执行线程
                thread = threading.Thread(target=execute_delayed, daemon=True)
                thread.start()
                
                # 更新存储的PC动作时间戳（用于后续合并）
                for stored_action in self.pc_replay_actions:
                    if stored_action is action:
                        stored_action['timestamp'] = adjusted_timestamp
                        stored_action['original_timestamp'] = original_timestamp
                        stored_action['time_offset'] = time_offset
                        break
            
            # 为所有动作安排执行
            for action in pc_actions:
                schedule_action(action)
            
            print("PC端动作回放已安排完成，所有动作将按调整后的时间戳并发执行")
            print(f"PC动作时间戳已调整，增加偏移: +{time_offset:.3f}秒")
            return True
            
        except Exception as e:
            print(f"回放PC录制失败: {str(e)}")
            return False
            
    def _execute_pc_action_on_device(self, action):
        """在设备上执行PC录制的动作"""
        try:
            import ADBHelper
            
            action_type = action.get('type')
            position = action.get('position')
            key = action.get('key', '')
            
            if action_type == 'tap' and position:
                duration = action.get('duration', 50)
                
                # 判断是否为长按操作（基于按键和持续时间）
                if key in ['a', 'd'] and duration > 100:  # A/D键且持续时间>100ms认为是长按
                    # 长按操作增加150ms补偿
                    compensated_duration = duration + self.long_press_compensation
                    print(f"回放PC长按: {position}, 原时长: {duration}ms, 补偿后: {compensated_duration}ms")
                    
                    # 使用一次性长按命令
                    x, y = position
                    import subprocess
                    cmd = f"adb -s {self.device_id} shell input swipe {x} {y} {x} {y} {compensated_duration}"
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=max(2, compensated_duration/1000 + 1))
                    print(f"回放PC长按完成: {position}")
                else:
                    # 普通点击
                    ADBHelper.touch(self.device_id, position)
                    print(f"回放PC点击: {position}")
                
            elif action_type == 'long_press' and position:
                # 长按操作增加150ms补偿
                duration = action.get('duration', 500)
                compensated_duration = duration + self.long_press_compensation
                print(f"回放长按: {position}, 原时长: {duration}ms, 补偿后: {compensated_duration}ms")
                
                # 使用一次性长按命令
                x, y = position
                import subprocess
                cmd = f"adb -s {self.device_id} shell input swipe {x} {y} {x} {y} {compensated_duration}"
                subprocess.run(cmd, shell=True, capture_output=True, timeout=max(2, compensated_duration/1000 + 1))
                print(f"回放长按完成: {position}")
                
            elif action_type in ['view_control', 'swipe']:
                # 视角控制和滑动操作
                if 'start_position' in action and 'end_position' in action:
                    start_pos = action['start_position']
                    end_pos = action['end_position']
                    duration = action.get('duration', 300)
                    
                    ADBHelper.slide(self.device_id, start_pos, end_pos, duration)
                    print(f"回放滑动: {start_pos} -> {end_pos}, 时长: {duration}ms")
                    
        except Exception as e:
            print(f"执行PC动作失败: {str(e)}") 

    def _merge_with_pc_actions(self):
        """将ADB录制动作与PC回放动作智能合并"""
        try:
            # 复制PC动作并标记来源
            pc_actions = []
            for action in self.pc_replay_actions:
                pc_action = action.copy()
                pc_action['source'] = 'pc'
                pc_actions.append(pc_action)
            
            # 复制ADB动作并标记来源
            adb_actions = []
            for action in self.actions:
                adb_action = action.copy()
                adb_action['source'] = 'adb'
                adb_actions.append(adb_action)
            
            # 处理长按分割
            pc_actions = self._split_long_press_by_interruptions(pc_actions, adb_actions)
            
            # 合并所有动作
            all_actions = pc_actions + adb_actions
            
            # 按时间戳排序
            all_actions.sort(key=lambda x: x.get('timestamp', 0))
            
            return all_actions
            
        except Exception as e:
            print(f"合并动作失败: {str(e)}")
            return self.actions  # 出错时返回原始ADB动作

    def _split_long_press_by_interruptions(self, pc_actions, adb_actions):
        """根据ADB动作的时间戳分割PC长按动作"""
        try:
            result_actions = []
            
            for pc_action in pc_actions:
                if pc_action.get('type') != 'long_press':
                    # 非长按动作直接添加
                    result_actions.append(pc_action)
                    continue
                
                # 处理长按动作
                long_press_start = pc_action.get('timestamp', 0)
                long_press_duration = pc_action.get('duration', 0) / 1000  # 转换为秒
                long_press_end = long_press_start + long_press_duration
                
                # 查找在长按期间的ADB动作
                interruptions = []
                for adb_action in adb_actions:
                    adb_timestamp = adb_action.get('timestamp', 0)
                    if long_press_start < adb_timestamp < long_press_end:
                        interruptions.append(adb_timestamp)
                
                if not interruptions:
                    # 没有中断，保持原长按
                    result_actions.append(pc_action)
                    continue
                
                # 有中断，分割长按
                interruptions.sort()
                
                # 添加第一段长按（从开始到第一个中断）
                first_duration = (interruptions[0] - long_press_start) * 1000  # 转换为毫秒
                if first_duration > 50:  # 只有足够长的时间才创建长按
                    first_action = pc_action.copy()
                    first_action['duration'] = int(first_duration)
                    first_action['split_part'] = 1
                    first_action['original_duration'] = pc_action.get('duration', 0)
                    result_actions.append(first_action)
                    print(f"分割长按第1段: {first_duration:.0f}ms")
                
                # 添加中间段长按（在中断之间）
                for i in range(len(interruptions) - 1):
                    segment_start = interruptions[i]
                    segment_end = interruptions[i + 1]
                    segment_duration = (segment_end - segment_start) * 1000  # 转换为毫秒
                    
                    if segment_duration > 50:  # 只有足够长的时间才创建长按
                        segment_action = pc_action.copy()
                        segment_action['timestamp'] = segment_start
                        segment_action['duration'] = int(segment_duration)
                        segment_action['split_part'] = i + 2
                        segment_action['original_duration'] = pc_action.get('duration', 0)
                        result_actions.append(segment_action)
                        print(f"分割长按第{i + 2}段: {segment_duration:.0f}ms")
                
                # 添加最后一段长按（从最后一个中断到结束）
                last_duration = (long_press_end - interruptions[-1]) * 1000  # 转换为毫秒
                if last_duration > 50:  # 只有足够长的时间才创建长按
                    last_action = pc_action.copy()
                    last_action['timestamp'] = interruptions[-1]
                    last_action['duration'] = int(last_duration)
                    last_action['split_part'] = len(interruptions) + 1
                    last_action['original_duration'] = pc_action.get('duration', 0)
                    result_actions.append(last_action)
                    print(f"分割长按第{len(interruptions) + 1}段: {last_duration:.0f}ms")
            
            return result_actions
            
        except Exception as e:
            print(f"分割长按动作失败: {str(e)}")
            return pc_actions  # 出错时返回原始PC动作 

    def set_long_press_compensation(self, compensation_ms: int):
        """设置长按补偿时间"""
        self.long_press_compensation = compensation_ms
        print(f"录制器长按补偿时间已设置为: {compensation_ms}ms")
        
    def get_long_press_compensation(self):
        """获取当前长按补偿时间"""
        return self.long_press_compensation 