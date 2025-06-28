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
import cv2
import numpy as np

class MobileReplayer:
    """手机端回放器类"""
    
    def __init__(self):
        self.replaying = False
        self.replay_thread = None
        self.device_id = ""
        self.long_press_compensation = 150  # 长按补偿时间(ms)，可通过配置修改
        self.start_timing_calibration = 0.2  # 开局起手时间校准(秒)，默认0.2秒
        
        # 智能视角相关参数
        self.smart_view_enabled = False  # 是否启用智能视角
        self.smart_view_templates = []  # 模板图片路径列表
        self.smart_view_delay_duration = 2.0  # 延迟时长(秒)
        self.smart_view_check_interval = 0.5  # 检查间隔(秒)
        self.delayed_view_threads = {}  # 存储被延迟的视角线程
        
        # 速度检测相关参数
        self.speed_detection_enabled = False  # 是否启用速度检测
        self.speed_templates = {}  # 速度档位模板 {'gear1': 'path', 'gear2': 'path', 'reverse': 'path'}
        self.speed_detection_region = (430, 723, 455, 757)  # 速度检测区域 (x1, y1, x2, y2)
        
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
    
    def enable_smart_view(self, template_paths: list, delay_duration: float = 2.0):
        """启用智能视角功能
        
        Args:
            template_paths: 模板图片路径列表
            delay_duration: 延迟时长(秒)
        """
        self.smart_view_enabled = True
        self.smart_view_templates = template_paths
        self.smart_view_delay_duration = delay_duration
        print(f"智能视角已启用，模板数量: {len(template_paths)}, 延迟时长: {delay_duration}秒")
    
    def disable_smart_view(self):
        """禁用智能视角功能"""
        self.smart_view_enabled = False
        self.smart_view_templates = []
        print("智能视角已禁用")
    
    def enable_speed_detection(self, templates_dict_or_dir):
        """启用速度检测功能
        
        Args:
            templates_dict_or_dir: 可以是模板字典 {'gear1': 'path', 'gear2': 'path', 'reverse': 'path'}
                                 或者是包含模板文件的目录路径
        """
        if isinstance(templates_dict_or_dir, dict):
            # 直接使用提供的模板字典
            self.speed_templates = templates_dict_or_dir
        elif isinstance(templates_dict_or_dir, str) and os.path.isdir(templates_dict_or_dir):
            # 从目录加载模板
            self.speed_templates = {}
            template_dir = templates_dict_or_dir
            
            # 定义模板文件名映射
            template_mapping = {
                'gear1': ['gear1.png', '1挡.png', 'speed1.png'],
                'gear2': ['gear2.png', '2挡.png', 'speed2.png'],
                'reverse': ['reverse.png', '后退.png', 'backward.png']
            }
            
            # 搜索模板文件
            for gear_type, possible_names in template_mapping.items():
                for name in possible_names:
                    template_path = os.path.join(template_dir, name)
                    if os.path.exists(template_path):
                        self.speed_templates[gear_type] = template_path
                        print(f"找到{gear_type}模板: {template_path}")
                        break
            
            if not self.speed_templates:
                print(f"警告: 在目录 {template_dir} 中未找到任何速度模板")
                return
        else:
            print("错误: 无效的模板参数")
            return
        
        self.speed_detection_enabled = True
        print(f"速度检测已启用，模板数量: {len(self.speed_templates)}")
    
    def disable_speed_detection(self):
        """禁用速度检测功能"""
        self.speed_detection_enabled = False
        self.speed_templates = {}
        print("速度检测已禁用")
    
    def set_speed_detection_region(self, x1, y1, x2, y2):
        """设置速度检测区域"""
        self.speed_detection_region = (x1, y1, x2, y2)
        print(f"速度检测区域已设置为: ({x1}, {y1}) -> ({x2}, {y2})")
    
    def detect_current_speed(self):
        """检测当前速度档位
        
        Returns:
            str: 'gear1', 'gear2', 'reverse', 'neutral', 'unknown'
        """
        if not self.speed_detection_enabled or not self.speed_templates:
            return 'unknown'
        
        try:
            # 截取屏幕
            screen_img = self.capture_screen_for_detection()
            if screen_img is None:
                return 'unknown'
            
            # 裁剪检测区域
            x1, y1, x2, y2 = self.speed_detection_region
            h, w = screen_img.shape[:2]
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(x1, min(x2, w))
            y2 = max(y1, min(y2, h))
            
            region_img = screen_img[y1:y2, x1:x2]
            
            # 检测各种速度档位
            best_match = 'unknown'
            best_confidence = 0.7  # 最低匹配阈值
            
            for gear_type, template_path in self.speed_templates.items():
                if not os.path.exists(template_path):
                    continue
                
                template = cv2.imread(template_path)
                if template is None:
                    continue
                
                # 模板匹配
                result = cv2.matchTemplate(region_img, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                print(f"速度检测 - {gear_type}: 匹配度 {max_val:.3f}")
                
                if max_val > best_confidence:
                    best_confidence = max_val
                    best_match = gear_type
            
            if best_match == 'unknown':
                print("速度检测: 未检测到明确的档位，可能为空挡")
                return 'neutral'
            else:
                print(f"速度检测: 当前档位为 {best_match} (置信度: {best_confidence:.3f})")
                return best_match
                
        except Exception as e:
            print(f"速度检测出错: {str(e)}")
            return 'unknown'
    
    def _execute_key_press(self, key, count=1):
        """执行按键操作
        
        Args:
            key: 按键 ('w', 's')
            count: 点击次数
        """
        try:
            # 根据按键设置坐标
            key_positions = {
                'w': (640, 800),  # W键坐标，需要根据实际游戏界面调整
                's': (640, 900),  # S键坐标，需要根据实际游戏界面调整
            }
            
            if key.lower() not in key_positions:
                print(f"不支持的按键: {key}")
                return
            
            position = key_positions[key.lower()]
            
            for i in range(count):
                ADBHelper.touch(self.device_id, position)
                print(f"执行按键 {key.upper()} (第{i+1}次)")
                if i < count - 1:  # 最后一次不需要等待
                    time.sleep(0.2)  # 按键间隔
                    
        except Exception as e:
            print(f"执行按键出错: {str(e)}")
    
    def adjust_speed_after_replay(self):
        """回放结束后调整速度到空挡"""
        if not self.speed_detection_enabled:
            print("速度检测未启用，跳过速度调整")
            return
        
        print("开始速度调整...")
        max_attempts = 10  # 最多尝试10次
        attempt_count = 0
        
        while attempt_count < max_attempts:
            attempt_count += 1
            print(f"速度调整第{attempt_count}次尝试...")
            
            # 等待一下再检测
            time.sleep(1)
            
            # 检测当前速度
            current_speed = self.detect_current_speed()
            
            if current_speed == 'unknown':
                print(f"第{attempt_count}次检测: 无法识别速度档位")
                continue
            elif current_speed == 'gear2':
                print(f"第{attempt_count}次检测: 发现2挡，点击2次S键")
                self._execute_key_press('s', 2)
                time.sleep(1)  # 等待按键执行完成
            elif current_speed == 'gear1':
                print(f"第{attempt_count}次检测: 发现1挡，点击1次S键")
                self._execute_key_press('s', 1)
                time.sleep(1)  # 等待按键执行完成
            elif current_speed == 'reverse':
                print(f"第{attempt_count}次检测: 发现后退挡，点击1次W键")
                self._execute_key_press('w', 1)
                time.sleep(1)  # 等待按键执行完成
            else:
                print(f"第{attempt_count}次检测: 速度已归零或处于空挡，调整完成")
                break
            
            # 检测调整是否成功
            time.sleep(0.5)
            new_speed = self.detect_current_speed()
            if new_speed == current_speed:
                print(f"速度调整似乎无效，当前仍为: {current_speed}")
            else:
                print(f"速度已从 {current_speed} 调整为 {new_speed}")
        
        if attempt_count >= max_attempts:
            print("已达到最大尝试次数，停止速度调整")
        else:
            print("速度调整完成")
    
    def capture_screen_for_detection(self):
        """为图色识别截取屏幕"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            cache_dir = os.path.join(os.path.dirname(__file__), "cache")
            os.makedirs(cache_dir, exist_ok=True)
            screenshot_path = os.path.join(cache_dir, f"smart_view_screen_{timestamp}.png")
            
            if ADBHelper.screenCapture(self.device_id, screenshot_path):
                img = cv2.imread(screenshot_path)
                # 清理临时文件
                try:
                    os.remove(screenshot_path)
                except:
                    pass
                return img
            return None
        except Exception as e:
            print(f"智能视角截屏失败: {str(e)}")
            return None
    
    def detect_template_in_regions(self, screen_img):
        """检测模板在屏幕左右区域的位置
        
        Args:
            screen_img: 屏幕截图
            
        Returns:
            dict: {'left': bool, 'right': bool} 表示模板在左右区域的检测结果
        """
        if not self.smart_view_templates or screen_img is None:
            return {'left': False, 'right': False}
        
        try:
            h, w = screen_img.shape[:2]
            # 修改区域划分：左侧50%，右侧50%，中间不重叠
            left_region = screen_img[:, :int(w * 0.5)]  # 左侧50%区域
            right_region = screen_img[:, int(w * 0.5):]  # 右侧50%区域
            
            result = {'left': False, 'right': False, 'left_confidence': 0, 'right_confidence': 0}
            
            for template_path in self.smart_view_templates:
                if not os.path.exists(template_path):
                    continue
                    
                template = cv2.imread(template_path)
                if template is None:
                    continue
                
                # 检测左侧区域
                try:
                    res_left = cv2.matchTemplate(left_region, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val_left, _, _ = cv2.minMaxLoc(res_left)
                    if max_val_left > 0.7:  # 匹配阈值
                        result['left'] = True
                        result['left_confidence'] = max_val_left
                        print(f"在左侧区域检测到模板: {os.path.basename(template_path)} (匹配度: {max_val_left:.3f})")
                except:
                    pass
                
                # 检测右侧区域
                try:
                    res_right = cv2.matchTemplate(right_region, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val_right, _, _ = cv2.minMaxLoc(res_right)
                    if max_val_right > 0.7:  # 匹配阈值
                        result['right'] = True
                        result['right_confidence'] = max_val_right
                        print(f"在右侧区域检测到模板: {os.path.basename(template_path)} (匹配度: {max_val_right:.3f})")
                except:
                    pass
            
            # 如果两边都检测到，选择置信度更高的一边
            if result['left'] and result['right']:
                if result['left_confidence'] > result['right_confidence']:
                    result['right'] = False
                    print(f"智能视角: 两侧都检测到目标，选择置信度更高的左侧 ({result['left_confidence']:.3f} > {result['right_confidence']:.3f})")
                else:
                    result['left'] = False
                    print(f"智能视角: 两侧都检测到目标，选择置信度更高的右侧 ({result['right_confidence']:.3f} > {result['left_confidence']:.3f})")
            
            return result
            
        except Exception as e:
            print(f"模板检测出错: {str(e)}")
            return {'left': False, 'right': False}
    
    def should_cancel_view_action(self, action):
        """判断是否应该取消视角动作（用于预检测）
        
        Args:
            action: 动作数据
            
        Returns:
            bool: 是否应该取消动作
        """
        try:
            direction = action.get('direction', '')
            
            # 截屏检测
            screen_img = self.capture_screen_for_detection()
            if screen_img is None:
                return False
            
            # 检测模板位置
            detection_result = self.detect_template_in_regions(screen_img)
            
            # 决策逻辑：如果检测到目标在相应区域，取消视角移动
            # 如果敌舰在左侧区域，取消"向右移动视角"的操作
            if direction == 'view_right' and detection_result['left']:
                print(f"智能视角: 敌舰在左侧，取消向右视角操作（保持对准目标）")
                return True
            # 如果敌舰在右侧区域，取消"向左移动视角"的操作
            elif direction == 'view_left' and detection_result['right']:
                print(f"智能视角: 敌舰在右侧，取消向左视角操作（保持对准目标）")
                return True
            
            return False
            
        except Exception as e:
            print(f"智能视角预检测出错: {str(e)}")
            return False
    
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
            if self.smart_view_enabled:
                print(f"智能视角: 已启用，模板数量: {len(self.smart_view_templates)}")
            
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
                # 回放完成后进行速度检测和调整
                self.adjust_speed_after_replay()
            
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
                
                # 智能视角预检测时间（提前500毫秒）
                pre_check_time = target_absolute_time - 0.5
                current_time = time.time()
                
                # 是否需要智能视角检测
                action_type = action.get('type')
                direction = action.get('direction', '')
                needs_smart_check = (self.smart_view_enabled and 
                                   (target_timestamp >= 30.0) and  # 30秒后才启用
                                   action_type in ['view_control', 'swipe'] and 
                                   direction in ['view_left', 'view_right'])
                
                should_cancel = False
                
                # 如果需要智能检测，提前500ms开始检测
                if needs_smart_check and current_time < pre_check_time:
                    # 等待到预检测时间
                    delay_to_precheck = pre_check_time - current_time
                    if delay_to_precheck > 0:
                        time.sleep(delay_to_precheck)
                    
                    if not self.replaying:
                        return
                    
                    # 执行预检测
                    print(f"智能视角预检测: {direction} (提前500ms检测)")
                    should_cancel = self.should_cancel_view_action(action)
                    
                    if should_cancel:
                        print(f"🚫 智能视角: 已取消 {action_type} 动作 [{direction}] (检测到目标，避免视角移开)")
                        return  # 直接返回，不执行这个动作
                
                # 等待到正常执行时间
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
            direction = action.get('direction', '')  # 获取方向信息
            
            # 输出动作信息，包含来源和方向
            action_info = f"{key} ({source})" if source != 'unknown' else key
            if direction:
                action_info += f" [{direction}]"
            
            print(f"开始执行动作: {action_type} - {action_info}")
            
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
                    
                    ADBHelper.slide(self.device_id, start_pos, end_pos, duration)
                    print(f"执行滑动: {direction} ({source}) {start_pos} -> {end_pos}, 时长: {duration}ms")
                else:
                    print(f"跳过滑动操作: 缺少位置信息 - {action}")
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
            console.print("• sv + 路径 - 启用智能视角 (如: sv templates/enemy.png)")
            console.print("• svoff - 禁用智能视角")
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
                    
            elif choice.startswith('sv ') and len(choice) > 3:
                # 启用智能视角
                template_path = choice[3:].strip()
                if os.path.exists(template_path):
                    replayer.enable_smart_view([template_path])
                    console.print(f"[green]智能视角已启用，模板: {template_path}[/green]")
                else:
                    console.print(f"[red]模板文件不存在: {template_path}[/red]")
                    
            elif choice == 'svoff':
                # 禁用智能视角
                replayer.disable_smart_view()
                console.print("[yellow]智能视角已禁用[/yellow]")
                    
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
                    if replayer.smart_view_enabled:
                        console.print(f"[yellow]智能视角: 已启用，模板数量: {len(replayer.smart_view_templates)}[/yellow]")
                    
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