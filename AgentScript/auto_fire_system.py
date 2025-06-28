#!/usr/bin/env python3
"""
全自动开火系统
实现敌舰识别、镜头校准和自动射击
"""

import cv2
import numpy as np
import time
import os
import threading
from datetime import datetime
import ADBHelper
from game_config import WEAPON_CONTROLS, SCREEN_CENTER

class AutoFireSystem:
    """全自动开火系统"""
    
    def __init__(self, device_id):
        self.device_id = device_id
        self.enabled = False
        self.running = False
        self.fire_thread = None
        self.templates_dir = os.path.join(os.path.dirname(__file__), "templates", "auto_fire")
        
        # 确保模板目录存在
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # 自动开火配置
        self.config = {
            "start_delay": 30.0,  # 开始自动开火的延迟时间（秒）
            "detection_interval": 0.5,  # 检测间隔（秒）
            "aim_tolerance": 50,  # 瞄准容忍度（像素）
            "max_aim_attempts": 3,  # 最大瞄准尝试次数
            "weapon_fire_rounds": 2,  # 每轮武器发射次数
            "weapon_fire_interval": 0.1,  # 武器发射间隔（秒）
            "search_turn_duration": 1000,  # 搜索转向持续时间（毫秒）
            "calibration_sensitivity": 0.8,  # 校准灵敏度倍数
            "y_axis_sensitivity_ratio": 0.25,  # Y轴灵敏度比例（相对于X轴）
            "health_bar_offset_y": 200,  # 血条目标Y轴偏移（像素，向下为正）
        }
        
        # 目标检测优先级
        self.detection_priority = [
            "blue_health_bar",  # 蓝色血条（最高优先级）
            "ship_hull",        # 船体轮廓
            "enemy_faction"     # 敌方阵营图标
        ]
        
        print("自动开火系统初始化完成")
    
    def set_config(self, **kwargs):
        """设置配置参数"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
                print(f"自动开火配置更新: {key} = {value}")
    
    def enable(self, start_delay=30.0):
        """启用自动开火系统"""
        self.enabled = True
        self.config["start_delay"] = start_delay
        print(f"自动开火系统已启用，将在{start_delay}秒后开始")
    
    def disable(self):
        """禁用自动开火系统"""
        self.enabled = False
        self.stop()
        print("自动开火系统已禁用")
    
    def start(self):
        """开始自动开火"""
        if not self.enabled:
            print("自动开火系统未启用")
            return
        
        if self.running:
            print("自动开火系统已在运行")
            return
        
        self.running = True
        self.fire_thread = threading.Thread(target=self._fire_loop, daemon=True)
        self.fire_thread.start()
        print("自动开火系统已启动")
    
    def stop(self):
        """停止自动开火"""
        self.running = False
        if self.fire_thread and self.fire_thread.is_alive():
            self.fire_thread.join(timeout=2)
        print("自动开火系统已停止")
    
    def _fire_loop(self):
        """自动开火主循环"""
        try:
            # 等待开始延迟
            if self.config["start_delay"] > 0:
                print(f"自动开火等待{self.config['start_delay']}秒后开始...")
                time.sleep(self.config["start_delay"])
            
            print("自动开火系统开始工作")
            
            while self.running:
                try:
                    # 截屏
                    screen_img = self.capture_screen()
                    if screen_img is None:
                        time.sleep(self.config["detection_interval"])
                        continue
                    
                    # 按优先级检测目标
                    target_found = False
                    for target_type in self.detection_priority:
                        target_location = self.detect_target(screen_img, target_type)
                        if target_location:
                            print(f"检测到目标: {target_type} at {target_location}")
                            
                            # 校准镜头
                            if self.calibrate_view(target_location, target_type):
                                # 如果是蓝色血条，直接开火
                                if target_type == "blue_health_bar":
                                    self.fire_weapons()
                                    target_found = True
                                    break
                                # 如果是船体轮廓，先检查是否有血条
                                elif target_type == "ship_hull":
                                    # 重新截屏检测血条
                                    new_screen = self.capture_screen()
                                    if new_screen is not None:
                                        health_bar_location = self.detect_target(new_screen, "blue_health_bar")
                                        if health_bar_location:
                                            print("船体校准后发现蓝色血条，开火")
                                            self.fire_weapons()
                                        else:
                                            print("船体校准后未发现蓝色血条，继续搜索")
                                    target_found = True
                                    break
                                # 如果是敌方阵营图标，继续搜索血条和船体
                                elif target_type == "enemy_faction":
                                    target_found = True
                                    # 不break，继续检测其他目标
                    
                    # 如果没有找到任何目标，执行搜索转向
                    if not target_found:
                        print("未检测到任何目标，执行搜索转向")
                        self.search_turn()
                    
                    # 检测间隔
                    time.sleep(self.config["detection_interval"])
                    
                except Exception as e:
                    print(f"自动开火循环出错: {str(e)}")
                    time.sleep(1)
                    
        except Exception as e:
            print(f"自动开火主循环出错: {str(e)}")
        finally:
            print("自动开火循环结束")
    
    def capture_screen(self):
        """截取屏幕"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            cache_dir = os.path.join(os.path.dirname(__file__), "cache")
            os.makedirs(cache_dir, exist_ok=True)
            screenshot_path = os.path.join(cache_dir, f"auto_fire_screen_{timestamp}.png")
            
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
            print(f"自动开火截屏失败: {str(e)}")
            return None
    
    def detect_target(self, screen_img, target_type):
        """检测目标位置
        
        Args:
            screen_img: 屏幕截图
            target_type: 目标类型 ('blue_health_bar', 'ship_hull', 'enemy_faction')
            
        Returns:
            tuple: (x, y) 目标中心位置，如果未检测到返回None
        """
        try:
            if target_type == "blue_health_bar":
                return self.detect_blue_health_bar(screen_img)
            elif target_type == "ship_hull":
                return self.detect_ship_hull(screen_img)
            elif target_type == "enemy_faction":
                return self.detect_enemy_faction(screen_img)
            else:
                print(f"未知的目标类型: {target_type}")
                return None
                
        except Exception as e:
            print(f"检测目标{target_type}时出错: {str(e)}")
            return None
    
    def detect_blue_health_bar(self, screen_img):
        """检测蓝色血条"""
        try:
            # 获取屏幕尺寸
            h, w = screen_img.shape[:2]
            
            # 转换为HSV颜色空间
            hsv = cv2.cvtColor(screen_img, cv2.COLOR_BGR2HSV)
            
            # 定义蓝色范围 - 基于用户提供的颜色值 00a3ff
            # RGB(0, 163, 255) -> HSV(101, 255, 255)
            # 考虑游戏中光照、抗锯齿等因素，设置合理的容差范围
            lower_blue = np.array([91, 180, 180])   # H±10, S和V降低以适应游戏环境
            upper_blue = np.array([111, 255, 255])  # H±10, S和V保持较高值
            
            # 创建蓝色掩码
            mask = cv2.inRange(hsv, lower_blue, upper_blue)
            
            # 创建排除区域掩码（排除地图等干扰区域）
            exclude_mask = np.ones_like(mask) * 255
            
            # 排除左上角地图区域
            map_w = int(w * 0.25)
            map_h = int(h * 0.25)
            exclude_mask[0:map_h, 0:map_w] = 0
            
            # 排除屏幕边缘区域（但保留底部，因为血条可能在下方）
            edge_margin = 50
            exclude_mask[:, 0:edge_margin] = 0  # 左边缘
            exclude_mask[:, w-edge_margin:w] = 0  # 右边缘
            exclude_mask[0:edge_margin, :] = 0  # 上边缘
            # 不排除底部区域 - 血条可能在屏幕下方
            
            # 应用排除掩码
            mask = cv2.bitwise_and(mask, exclude_mask)
            
            # 形态学操作去除噪声
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 筛选血条轮廓（更严格的条件）
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 200:  # 提高面积阈值
                    # 计算边界矩形
                    x, y, w_rect, h_rect = cv2.boundingRect(contour)
                    aspect_ratio = w_rect / h_rect if h_rect > 0 else 0
                    center_x = x + w_rect // 2
                    center_y = y + h_rect // 2
                    
                    # 更严格的血条特征检查
                    is_valid_health_bar = (
                        aspect_ratio > 3.0 and      # 血条应该是长条形，宽高比>3
                        w_rect > 50 and             # 宽度至少50像素
                        h_rect < 20 and             # 高度不超过20像素
                        area > 200                  # 面积至少200像素
                        # 移除位置限制 - 血条可能在屏幕任何位置
                    )
                    
                    if is_valid_health_bar:
                        print(f"检测到蓝色血条(00a3ff): 中心({center_x}, {center_y}), 尺寸({w_rect}x{h_rect}), 面积{area}, 宽高比{aspect_ratio:.2f}")
                        return (center_x, center_y)
            
            return None
            
        except Exception as e:
            print(f"检测蓝色血条出错: {str(e)}")
            return None
    
    def detect_ship_hull(self, screen_img):
        """检测船体轮廓"""
        try:
            # 检查是否有船体模板
            hull_template_path = os.path.join(self.templates_dir, "ship_hull.png")
            if not os.path.exists(hull_template_path):
                print("船体模板不存在，跳过船体检测")
                return None
            
            template = cv2.imread(hull_template_path)
            if template is None:
                print("无法读取船体模板")
                return None
            
            # 模板匹配
            result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val > 0.6:  # 匹配阈值
                # 计算模板中心位置
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                print(f"检测到船体轮廓: 中心({center_x}, {center_y}), 匹配度{max_val:.3f}")
                return (center_x, center_y)
            
            return None
            
        except Exception as e:
            print(f"检测船体轮廓出错: {str(e)}")
            return None
    
    def detect_enemy_faction(self, screen_img):
        """检测敌方阵营图标"""
        try:
            # 检查是否有敌方阵营模板
            faction_template_path = os.path.join(self.templates_dir, "enemy_faction.png")
            if not os.path.exists(faction_template_path):
                print("敌方阵营模板不存在，跳过阵营检测")
                return None
            
            template = cv2.imread(faction_template_path)
            if template is None:
                print("无法读取敌方阵营模板")
                return None
            
            # 模板匹配
            result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val > 0.7:  # 匹配阈值
                # 计算模板中心位置
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                print(f"检测到敌方阵营图标: 中心({center_x}, {center_y}), 匹配度{max_val:.3f}")
                return (center_x, center_y)
            
            return None
            
        except Exception as e:
            print(f"检测敌方阵营图标出错: {str(e)}")
            return None
    
    def calibrate_view(self, target_location, target_type="unknown"):
        """校准视角，将目标移动到屏幕中心
        
        Args:
            target_location: (x, y) 目标位置
            target_type: 目标类型，用于确定校准偏移
            
        Returns:
            bool: 是否校准成功
        """
        try:
            target_x, target_y = target_location
            
            # 如果是血条，校准到血条下方指定像素
            if target_type == "blue_health_bar":
                offset_y = self.config["health_bar_offset_y"]
                target_y += offset_y  # 血条下方偏移
                print(f"血条目标校准：从({target_location[0]}, {target_location[1]}) 调整到 ({target_x}, {target_y})，偏移+{offset_y}px")
            
            screen_center_x, screen_center_y = SCREEN_CENTER
            
            # 计算偏移量
            offset_x = target_x - screen_center_x
            offset_y = target_y - screen_center_y
            
            # 检查是否在容忍范围内
            distance = np.sqrt(offset_x**2 + offset_y**2)
            if distance <= self.config["aim_tolerance"]:
                print(f"目标已在中心附近，偏移距离: {distance:.1f}像素，直接开火")
                return True
            
            print(f"目标偏离中心 ({offset_x:+d}, {offset_y:+d})，距离: {distance:.1f}像素，开始校准")
            
            # 计算滑动参数（根据偏移量调整）
            # 校准逻辑：目标在右侧时向右滑动，目标在下方时向下滑动
            # 这样可以让目标移动到屏幕中心
            sensitivity = self.config["calibration_sensitivity"]
            y_ratio = self.config["y_axis_sensitivity_ratio"]
            swipe_x = int(offset_x * sensitivity)
            swipe_y = int(offset_y * sensitivity * y_ratio)
            
            print(f"校准灵敏度: X轴={sensitivity}, Y轴={sensitivity * y_ratio:.2f} (比例={y_ratio})")
            
            # 限制滑动范围
            max_swipe = 300
            swipe_x = max(-max_swipe, min(max_swipe, swipe_x))
            swipe_y = max(-max_swipe, min(max_swipe, swipe_y))
            
            # 执行视角校准滑动
            start_x, start_y = screen_center_x, screen_center_y
            end_x = start_x + swipe_x  # 修正方向：目标在右侧时向右滑动
            end_y = start_y + swipe_y  # 修正方向：目标在下方时向下滑动
            
            duration = min(500, max(100, int(distance / 2)))  # 根据距离调整滑动时长
            
            ADBHelper.slide(self.device_id, (start_x, start_y), (end_x, end_y), duration)
            print(f"执行校准滑动: ({start_x}, {start_y}) -> ({end_x}, {end_y}), 时长: {duration}ms")
            
            # 等待视角稳定
            time.sleep(0.3)
            return True
            
        except Exception as e:
            print(f"校准视角出错: {str(e)}")
            return False
    
    def fire_weapons(self):
        """发射武器"""
        try:
            print("开始自动开火")
            
            # 发射1、2、3号武器，每个武器连续点击3次，只打1轮
            weapons = ['1', '2', '3']
            rounds = 3  # 每个武器连击3次
            interval = self.config["weapon_fire_interval"]
            
            print("开火轮次: 1轮")
            for weapon in weapons:
                if not self.running:  # 检查是否仍在运行
                    return
                
                weapon_pos = WEAPON_CONTROLS.get(weapon)
                if weapon_pos:
                    for shot in range(rounds):
                        ADBHelper.touch(self.device_id, weapon_pos)
                        print(f"发射{weapon}号武器 (第{shot + 1}次)")
                        if shot < rounds - 1:  # 最后一次不需要等待
                            time.sleep(interval)
                    
                    # 武器间间隔
                    time.sleep(interval)
                else:
                    print(f"未找到{weapon}号武器配置")
            
            print("自动开火完成")
            
        except Exception as e:
            print(f"发射武器出错: {str(e)}")
    
    def search_turn(self):
        """搜索转向（向右大转视角）"""
        try:
            print("执行搜索转向")
            
            screen_center_x, screen_center_y = SCREEN_CENTER
            turn_distance = 400  # 转向距离
            duration = self.config["search_turn_duration"]
            
            # 向右大幅转向
            start_pos = (screen_center_x, screen_center_y)
            end_pos = (screen_center_x + turn_distance, screen_center_y)  # 向右滑动使视角向右转
            
            ADBHelper.slide(self.device_id, start_pos, end_pos, duration)
            print(f"搜索转向: {start_pos} -> {end_pos}, 时长: {duration}ms")
            
            # 等待转向完成
            time.sleep(duration / 1000.0 + 0.5)
            
        except Exception as e:
            print(f"搜索转向出错: {str(e)}")
    
    def create_template_guide(self):
        """创建模板文件指南"""
        guide_path = os.path.join(self.templates_dir, "README.md")
        
        guide_content = """# 自动开火系统模板文件指南

## 模板文件说明

请将以下模板图片放入此目录：

### 1. enemy_faction.png
- **用途**: 敌方阵营图标识别
- **要求**: 截取敌方阵营标识的清晰图片
- **建议尺寸**: 50x50 到 100x100 像素
- **优先级**: 低（用于初步定位）

### 2. ship_hull.png
- **用途**: 敌舰船体轮廓识别
- **要求**: 截取敌舰船体的特征部分
- **建议尺寸**: 100x100 到 200x200 像素
- **优先级**: 中（用于粗略瞄准）

### 3. blue_health_bar.png（可选）
- **用途**: 蓝色血条识别模板
- **说明**: 系统主要使用颜色检测，此模板为备用
- **要求**: 截取蓝色血条的典型样本
- **优先级**: 高（主要目标）

## 使用建议

1. **enemy_faction.png**: 必需，用于初步搜索敌舰
2. **ship_hull.png**: 推荐，提高识别准确性
3. **blue_health_bar.png**: 可选，系统会自动检测蓝色

## 截图技巧

- 确保图片清晰，无模糊
- 选择具有代表性的特征部分
- 避免包含过多背景干扰
- PNG格式，保持透明度信息
"""
        
        try:
            with open(guide_path, 'w', encoding='utf-8') as f:
                f.write(guide_content)
            print(f"已创建模板指南: {guide_path}")
        except Exception as e:
            print(f"创建模板指南失败: {str(e)}")


# 测试函数
def test_auto_fire_system():
    """测试自动开火系统"""
    print("自动开火系统测试")
    
    # 这里需要设备ID，实际使用时从外部传入
    device_id = "test_device"
    
    fire_system = AutoFireSystem(device_id)
    fire_system.create_template_guide()
    
    print("测试完成")


if __name__ == "__main__":
    test_auto_fire_system() 