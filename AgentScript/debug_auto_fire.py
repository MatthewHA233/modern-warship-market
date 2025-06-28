#!/usr/bin/env python3
"""
自动开火系统实战调试脚本
分模块测试各个功能，逐步调教参数
"""

import cv2
import numpy as np
import time
import os
import ADBHelper
from auto_fire_system import AutoFireSystem
from game_config import WEAPON_CONTROLS, SCREEN_CENTER

class AutoFireDebugger:
    """自动开火调试器"""
    
    def __init__(self):
        self.device_id = None
        self.fire_system = None
        self.debug_mode = True
        
    def setup_device(self):
        """设置设备"""
        devices = ADBHelper.getDevicesList()
        if not devices:
            print("❌ 未找到连接的设备")
            return False
        
        print("📱 可用设备:")
        for i, device in enumerate(devices, 1):
            print(f"  {i}. {device}")
        
        while True:
            try:
                choice = input("选择设备序号: ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(devices):
                        self.device_id = devices[idx]
                        self.fire_system = AutoFireSystem(self.device_id)
                        print(f"✅ 已选择设备: {self.device_id}")
                        return True
                print("❌ 无效选择，请重新输入")
            except KeyboardInterrupt:
                return False
    
    def test_screenshot(self):
        """测试截屏功能"""
        print("\n🖼️  测试截屏功能...")
        
        screen_img = self.fire_system.capture_screen()
        if screen_img is not None:
            h, w = screen_img.shape[:2]
            print(f"✅ 截屏成功: {w}x{h}")
            
            # 保存截屏用于分析
            cv2.imwrite("debug_screenshot.png", screen_img)
            print("📁 截屏已保存为: debug_screenshot.png")
            return screen_img
        else:
            print("❌ 截屏失败")
            return None
    
    def test_color_detection(self, screen_img):
        """测试颜色检测"""
        print("\n🎨 测试蓝色血条检测...")
        
        if screen_img is None:
            print("❌ 无截屏图像")
            return
        
        # 获取屏幕尺寸
        h, w = screen_img.shape[:2]
        print(f"📐 屏幕尺寸: {w}x{h}")
        
        # 转换为HSV
        hsv = cv2.cvtColor(screen_img, cv2.COLOR_BGR2HSV)
        
        # 当前检测范围
        lower_blue = np.array([91, 180, 180])
        upper_blue = np.array([111, 255, 255])
        
        print(f"🔍 检测范围: H({lower_blue[0]}-{upper_blue[0]}), S({lower_blue[1]}-{upper_blue[1]}), V({lower_blue[2]}-{upper_blue[2]})")
        
        # 创建掩码
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # 创建排除区域掩码（排除地图区域）
        # 通常地图在屏幕左上角，血条在屏幕中央偏上
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
        
        # 保存掩码图像
        cv2.imwrite("debug_blue_mask.png", mask)
        cv2.imwrite("debug_exclude_mask.png", exclude_mask)
        print("📁 蓝色掩码已保存为: debug_blue_mask.png")
        print("📁 排除区域掩码已保存为: debug_exclude_mask.png")
        
        # 创建标记图像（在原始截图上用红色填充检测区域）
        marked_img = screen_img.copy()
        
        # 在标记图像上显示排除区域（半透明灰色）
        overlay = marked_img.copy()
        overlay[exclude_mask == 0] = [128, 128, 128]  # 灰色
        marked_img = cv2.addWeighted(marked_img, 0.8, overlay, 0.2, 0)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"🔍 找到 {len(contours)} 个蓝色区域（排除干扰区域后）")
        
        # 分析每个轮廓
        valid_targets = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area > 100:  # 提高面积阈值
                x, y, w_rect, h_rect = cv2.boundingRect(contour)
                aspect_ratio = w_rect / h_rect if h_rect > 0 else 0
                center_x = x + w_rect // 2
                center_y = y + h_rect // 2
                
                print(f"  区域{i+1}: 中心({center_x}, {center_y}), 尺寸({w_rect}x{h_rect}), 面积{area}, 宽高比{aspect_ratio:.2f}")
                
                # 在标记图像上用红色填充检测区域
                cv2.fillPoly(marked_img, [contour], (0, 0, 255))  # 红色填充
                
                # 添加区域标号和详细信息
                cv2.putText(marked_img, f"{i+1}", (center_x-10, center_y-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(marked_img, f"{aspect_ratio:.1f}", (center_x-15, center_y+15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
                # 更严格的血条特征检查
                is_valid_health_bar = (
                    aspect_ratio > 3.0 and  # 血条应该是长条形，宽高比>3
                    w_rect > 50 and         # 宽度至少50像素
                    h_rect < 20 and         # 高度不超过20像素
                    area > 200              # 面积至少200像素
                    # 移除位置限制 - 血条可能在屏幕任何位置
                )
                
                if is_valid_health_bar:
                    print(f"    ✅ 符合血条特征")
                    valid_targets.append((center_x, center_y))
                    
                    # 用绿色框标记有效血条
                    cv2.rectangle(marked_img, (x, y), (x+w_rect, y+h_rect), (0, 255, 0), 3)
                    cv2.circle(marked_img, (center_x, center_y), 8, (0, 255, 0), -1)
                    cv2.putText(marked_img, "HEALTH BAR", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                else:
                    print(f"    ❌ 不符合血条特征")
                    reasons = []
                    if aspect_ratio <= 3.0:
                        reasons.append(f"宽高比{aspect_ratio:.1f}<=3.0")
                    if w_rect <= 50:
                        reasons.append(f"宽度{w_rect}<=50")
                    if h_rect >= 20:
                        reasons.append(f"高度{h_rect}>=20")
                    if area <= 200:
                        reasons.append(f"面积{area}<=200")
                    print(f"      原因: {', '.join(reasons)}")
                    
                    # 用黄色框标记无效区域
                    cv2.rectangle(marked_img, (x, y), (x+w_rect, y+h_rect), (0, 255, 255), 1)
        
        # 保存标记后的图像
        cv2.imwrite("debug_blue_detection_marked.png", marked_img)
        print("📁 标记图像已保存为: debug_blue_detection_marked.png")
        print("   🔴 红色填充: 检测到的蓝色区域")
        print("   🟢 绿色框: 符合血条特征的区域")
        print("   🟡 黄色框: 不符合血条特征的区域")
        print("   🔘 灰色半透明: 排除的干扰区域（地图、边缘）")
        print("   💡 支持检测屏幕任何位置的血条（包括底部）")
        print(f"\n🎯 最终发现 {len(valid_targets)} 个有效血条目标")
        
        return valid_targets
    
    def test_template_detection(self, screen_img):
        """测试模板检测"""
        print("\n🎯 测试模板检测...")
        
        if screen_img is None:
            print("❌ 无截屏图像")
            return []
        
        templates_dir = os.path.join(os.path.dirname(__file__), "templates", "auto_fire")
        template_files = ["enemy_faction.png", "ship_hull.png"]
        
        found_targets = []
        
        for template_file in template_files:
            template_path = os.path.join(templates_dir, template_file)
            if not os.path.exists(template_path):
                print(f"⚠️  模板不存在: {template_file}")
                continue
            
            template = cv2.imread(template_path)
            if template is None:
                print(f"❌ 无法读取模板: {template_file}")
                continue
            
            print(f"🔍 检测模板: {template_file}")
            
            # 模板匹配
            result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            print(f"  最高匹配度: {max_val:.3f}")
            
            # 设置不同的阈值
            threshold = 0.5 if "faction" in template_file else 0.4  # 降低阈值用于调试
            
            if max_val > threshold:
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                
                print(f"  ✅ 检测到目标: 中心({center_x}, {center_y})")
                found_targets.append((center_x, center_y, template_file))
                
                # 在截图上标记检测结果
                debug_img = screen_img.copy()
                cv2.rectangle(debug_img, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
                cv2.circle(debug_img, (center_x, center_y), 10, (0, 0, 255), -1)
                cv2.imwrite(f"debug_{template_file}_detection.png", debug_img)
                print(f"  📁 检测结果已保存为: debug_{template_file}_detection.png")
            else:
                print(f"  ❌ 匹配度过低 (阈值: {threshold})")
        
        return found_targets
    
    def test_weapon_fire(self):
        """测试武器开火（单次）"""
        print("\n🔫 测试武器开火...")
        print("💡 每个武器连击3次，总共9次点击")
        
        weapons = ['1', '2', '3']
        
        for weapon in weapons:
            weapon_pos = WEAPON_CONTROLS.get(weapon)
            if weapon_pos:
                print(f"🎯 {weapon}号武器位置: {weapon_pos}")
                
                execute = input(f"是否发射{weapon}号武器? (y/n): ").strip().lower()
                if execute in ['y', 'yes']:
                    # 连续点击3次
                    for shot in range(3):
                        ADBHelper.touch(self.device_id, weapon_pos)
                        print(f"💥 发射{weapon}号武器 (第{shot + 1}次)")
                        if shot < 2:  # 前两次需要间隔
                            time.sleep(0.1)
                    time.sleep(0.2)  # 武器间间隔
                else:
                    print(f"⏭️  跳过{weapon}号武器")
            else:
                print(f"❌ 未找到{weapon}号武器配置")
        
        print("🎯 武器测试完成：总共最多9次点击（每个武器3次）")
    
    def run_debug_session(self):
        """运行调试会话"""
        print("🔧 自动开火系统实战调试")
        print("=" * 50)
        
        # 1. 设置设备
        if not self.setup_device():
            return
        
        while True:
            print("\n🎯 调试选项:")
            print("1. 测试截屏")
            print("2. 测试蓝色血条检测")
            print("3. 测试模板检测")
            print("4. 自动检测目标并测试校准")
            print("5. 测试武器开火")
            print("6. 完整流程测试")
            print("7. 快速目标扫描")
            print("8. 调整检测参数")
            print("q. 退出")
            
            choice = input("\n选择操作: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '1':
                self.test_screenshot()
            elif choice == '2':
                screen_img = self.test_screenshot()
                if screen_img is not None:
                    self.test_color_detection(screen_img)
            elif choice == '3':
                screen_img = self.test_screenshot()
                if screen_img is not None:
                    self.test_template_detection(screen_img)
            elif choice == '4':
                self.test_view_calibration_auto()
            elif choice == '5':
                self.test_weapon_fire()
            elif choice == '6':
                self.full_flow_test()
            elif choice == '7':
                self.quick_target_scan()
            elif choice == '8':
                self.adjust_parameters()
            else:
                print("❌ 无效选择")
    
    def full_flow_test(self):
        """完整流程测试 - 全自动开火（模拟正式文件逻辑）"""
        print("\n🎯 完整流程测试 - 全自动开火模式")
        print("-" * 40)
        print("💡 完全按照正式文件逻辑：检测→校准→完整开火18次→检测间隔→继续")
        
        auto_mode = input("是否启动全自动模式? (y/n): ").strip().lower()
        if auto_mode not in ['y', 'yes']:
            print("❌ 已取消全自动模式")
            return
        
        print("\n🚀 全自动开火模式已启动!")
        print("🔄 按照正式文件逻辑运行...")
        
        # 确保fire_system处于运行状态
        self.fire_system.running = True
        
        while True:
            try:
                # 截屏
                print("\n📸 正在截屏...")
                screen_img = self.fire_system.capture_screen()
                if screen_img is None:
                    print("❌ 截屏失败，等待检测间隔后重试...")
                    time.sleep(self.fire_system.config["detection_interval"])
                    continue
                
                # 按优先级检测目标（完全按照正式文件逻辑）
                target_found = False
                
                for target_type in self.fire_system.detection_priority:
                    print(f"🔍 检测目标类型: {target_type}")
                    target_location = self.fire_system.detect_target(screen_img, target_type)
                    
                    if target_location:
                        print(f"✅ 检测到目标: {target_type} at {target_location}")
                        
                        # 校准镜头
                        print("🎮 开始校准镜头...")
                        if self.fire_system.calibrate_view(target_location, target_type):
                            print("✅ 校准成功")
                            
                            # 如果是蓝色血条，直接开火
                            if target_type == "blue_health_bar":
                                print("🔥 检测到蓝色血条，立即开火!")
                                self.fire_system.fire_weapons()  # 完整开火18次
                                print("💥 开火完成")
                                target_found = True
                                break
                            
                            # 如果是船体轮廓，先检查是否有血条
                            elif target_type == "ship_hull":
                                print("🚢 船体校准完成，重新检测血条...")
                                # 重新截屏检测血条
                                new_screen = self.fire_system.capture_screen()
                                if new_screen is not None:
                                    health_bar_location = self.fire_system.detect_target(new_screen, "blue_health_bar")
                                    if health_bar_location:
                                        print("🩸 船体校准后发现蓝色血条，开火!")
                                        self.fire_system.fire_weapons()  # 完整开火18次
                                        print("💥 开火完成")
                                    else:
                                        print("⚠️  船体校准后未发现蓝色血条，继续搜索")
                                target_found = True
                                break
                            
                            # 如果是敌方阵营图标，继续搜索血条和船体
                            elif target_type == "enemy_faction":
                                print("⚓ 敌方阵营校准完成，继续检测其他目标...")
                                target_found = True
                                # 不break，继续检测其他目标
                        else:
                            print("❌ 校准失败")
                    else:
                        print(f"❌ 未检测到 {target_type}")
                
                # 如果没有找到任何目标，执行搜索转向
                if not target_found:
                    print("❌ 未检测到任何目标，执行搜索转向")
                    self.fire_system.search_turn()
                
                # 检测间隔（完全按照正式文件逻辑）
                interval = self.fire_system.config["detection_interval"]
                print(f"⏱️  检测间隔: {interval}秒")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n\n⏹️  用户中断，退出全自动模式")
                break
            except Exception as e:
                print(f"❌ 全自动流程出错: {str(e)}")
                time.sleep(1)
        
        print("🏁 全自动开火测试结束")
    
    def _calculate_distance_to_center(self, position):
        """计算位置到屏幕中心的距离"""
        x, y = position
        center_x, center_y = SCREEN_CENTER
        return np.sqrt((x - center_x)**2 + (y - center_y)**2)
    
    def adjust_parameters(self):
        """调整检测参数"""
        print("\n⚙️  参数调整")
        
        # 显示当前配置
        print("当前校准配置:")
        print(f"  X轴灵敏度: {self.fire_system.config['calibration_sensitivity']}")
        print(f"  Y轴灵敏度比例: {self.fire_system.config['y_axis_sensitivity_ratio']}")
        print(f"  实际Y轴灵敏度: {self.fire_system.config['calibration_sensitivity'] * self.fire_system.config['y_axis_sensitivity_ratio']:.2f}")
        print(f"  血条偏移: +{self.fire_system.config['health_bar_offset_y']}px (向下)")
        
        print("\n蓝色检测范围:")
        print("  H: 91-111")
        print("  S: 180-255") 
        print("  V: 180-255")
        
        print("\n调整选项:")
        print("1. 调整X轴校准灵敏度")
        print("2. 调整Y轴灵敏度比例")
        print("3. 调整血条偏移距离")
        print("4. 重置为默认值")
        print("5. 返回主菜单")
        
        choice = input("\n选择操作: ").strip()
        
        if choice == '1':
            try:
                new_sensitivity = float(input(f"输入新的X轴灵敏度 (当前: {self.fire_system.config['calibration_sensitivity']}): "))
                self.fire_system.set_config(calibration_sensitivity=new_sensitivity)
                print(f"✅ X轴灵敏度已设置为: {new_sensitivity}")
            except ValueError:
                print("❌ 无效输入")
        elif choice == '2':
            try:
                new_ratio = float(input(f"输入新的Y轴灵敏度比例 (当前: {self.fire_system.config['y_axis_sensitivity_ratio']}): "))
                self.fire_system.set_config(y_axis_sensitivity_ratio=new_ratio)
                print(f"✅ Y轴灵敏度比例已设置为: {new_ratio}")
                print(f"   实际Y轴灵敏度: {self.fire_system.config['calibration_sensitivity'] * new_ratio:.2f}")
            except ValueError:
                print("❌ 无效输入")
        elif choice == '3':
            try:
                new_offset = int(input(f"输入新的血条偏移距离 (当前: {self.fire_system.config['health_bar_offset_y']}px): "))
                self.fire_system.set_config(health_bar_offset_y=new_offset)
                print(f"✅ 血条偏移已设置为: +{new_offset}px")
            except ValueError:
                print("❌ 无效输入")
        elif choice == '4':
            self.fire_system.set_config(
                calibration_sensitivity=2.0, 
                y_axis_sensitivity_ratio=0.25,
                health_bar_offset_y=200
            )
            print("✅ 已重置为默认值")
        elif choice == '5':
            return
        else:
            print("❌ 无效选择")
        
        print("\n可以通过修改 auto_fire_system.py 中的配置来永久保存这些设置")
        input("按回车键继续...")

    def test_view_calibration_auto(self):
        """自动检测目标并测试视角校准"""
        print("\n🎯 自动目标检测与视角校准测试")
        print("-" * 40)
        
        while True:
            # 截屏
            screen_img = self.test_screenshot()
            if screen_img is None:
                break
            
            # 检测所有目标
            print("\n🔍 正在检测所有目标...")
            blue_targets = self.test_color_detection(screen_img)
            template_targets = self.test_template_detection(screen_img)
            
            # 整理目标列表
            all_targets = []
            
            # 1. 蓝色血条目标
            if blue_targets:
                for i, (x, y) in enumerate(blue_targets):
                    all_targets.append({
                        'id': len(all_targets) + 1,
                        'type': 'blue_health_bar',
                        'position': (x, y),
                        'description': f"蓝色血条 #{i+1}"
                    })
            
            # 2. 模板目标
            if template_targets:
                for x, y, template_name in template_targets:
                    template_type = template_name.replace('.png', '')
                    all_targets.append({
                        'id': len(all_targets) + 1,
                        'type': template_type,
                        'position': (x, y),
                        'description': f"模板目标: {template_type}"
                    })
            
            if not all_targets:
                print("❌ 未检测到任何目标")
                retry = input("是否重新检测? (y/n): ").strip().lower()
                if retry not in ['y', 'yes']:
                    break
                continue
            
            # 显示目标列表
            print(f"\n🎯 检测到 {len(all_targets)} 个目标:")
            for target in all_targets:
                x, y = target['position']
                print(f"  {target['id']}. {target['description']} - 位置({x}, {y})")
            
            # 让用户选择目标
            try:
                choice = input(f"\n选择目标进行校准 (1-{len(all_targets)}) 或 q 退出: ").strip().lower()
                
                if choice == 'q':
                    break
                
                if choice.isdigit():
                    target_id = int(choice)
                    if 1 <= target_id <= len(all_targets):
                        selected_target = all_targets[target_id - 1]
                        
                        print(f"\n🎯 选择目标: {selected_target['description']}")
                        print(f"   位置: {selected_target['position']}")
                        print(f"   类型: {selected_target['type']}")
                        
                        # 立即执行校准（不询问确认）
                        print("🎮 立即执行校准...")
                        self.execute_calibration_immediately(selected_target['position'], selected_target['type'])
                        
                        # 校准后继续检测新目标
                        print("\n🔄 校准完成，继续检测新目标...")
                        time.sleep(0.5)  # 短暂等待视角稳定
                        continue
                    else:
                        print(f"❌ 无效选择，请输入 1-{len(all_targets)}")
                else:
                    print("❌ 请输入数字或 q")
                    
            except ValueError:
                print("❌ 输入格式错误")
            except KeyboardInterrupt:
                break
    
    def execute_calibration_immediately(self, target_location, target_type="unknown"):
        """立即执行校准（不询问确认）"""
        target_x, target_y = target_location
        
        # 如果是血条，校准到血条下方指定像素
        if target_type == "blue_health_bar":
            offset_y = self.fire_system.config["health_bar_offset_y"]
            target_y += offset_y  # 血条下方偏移
            print(f"🩸 血条目标校准：从({target_location[0]}, {target_location[1]}) 调整到 ({target_x}, {target_y})，偏移+{offset_y}px")
        
        screen_center_x, screen_center_y = SCREEN_CENTER
        
        # 计算偏移量
        offset_x = target_x - screen_center_x
        offset_y = target_y - screen_center_y
        distance = np.sqrt(offset_x**2 + offset_y**2)
        
        print(f"📐 目标偏移: ({offset_x:+d}, {offset_y:+d}), 距离: {distance:.1f}px")
        
        # 计算滑动参数
        # 使用AutoFireSystem的配置参数
        sensitivity = self.fire_system.config["calibration_sensitivity"]
        y_ratio = self.fire_system.config["y_axis_sensitivity_ratio"]
        swipe_x = int(offset_x * sensitivity)
        swipe_y = int(offset_y * sensitivity * y_ratio)
        
        print(f"🎮 灵敏度: X轴={sensitivity}, Y轴={sensitivity * y_ratio:.2f} (比例={y_ratio})")
        
        # 限制滑动范围
        max_swipe = 300
        swipe_x = max(-max_swipe, min(max_swipe, swipe_x))
        swipe_y = max(-max_swipe, min(max_swipe, swipe_y))
        
        # 计算滑动起终点
        start_x, start_y = screen_center_x, screen_center_y
        end_x = start_x + swipe_x
        end_y = start_y + swipe_y
        
        duration = min(500, max(100, int(distance / 2)))
        
        print(f"🎮 滑动参数: ({start_x}, {start_y}) -> ({end_x}, {end_y}), {duration}ms")
        
        # 立即执行校准
        ADBHelper.slide(self.device_id, (start_x, start_y), (end_x, end_y), duration)
        print("✅ 校准完成")

    def quick_target_scan(self):
        """快速目标扫描"""
        print("\n🔍 快速目标扫描")
        print("-" * 30)
        
        # 截屏
        screen_img = self.test_screenshot()
        if screen_img is None:
            return
        
        # 静默检测所有目标（不输出详细过程）
        print("\n🔍 正在扫描目标...")
        
        # 检测蓝色血条
        blue_targets = []
        try:
            h, w = screen_img.shape[:2]
            hsv = cv2.cvtColor(screen_img, cv2.COLOR_BGR2HSV)
            lower_blue = np.array([91, 180, 180])
            upper_blue = np.array([111, 255, 255])
            mask = cv2.inRange(hsv, lower_blue, upper_blue)
            
            # 排除区域
            exclude_mask = np.ones_like(mask) * 255
            map_w = int(w * 0.25)
            map_h = int(h * 0.25)
            exclude_mask[0:map_h, 0:map_w] = 0
            edge_margin = 50
            exclude_mask[:, 0:edge_margin] = 0
            exclude_mask[:, w-edge_margin:w] = 0
            exclude_mask[0:edge_margin, :] = 0
            # 不排除底部区域 - 血条可能在屏幕下方
            mask = cv2.bitwise_and(mask, exclude_mask)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 200:
                    x, y, w_rect, h_rect = cv2.boundingRect(contour)
                    aspect_ratio = w_rect / h_rect if h_rect > 0 else 0
                    center_x = x + w_rect // 2
                    center_y = y + h_rect // 2
                    
                    if (aspect_ratio > 3.0 and w_rect > 50 and h_rect < 20 and 
                        area > 200):
                        blue_targets.append((center_x, center_y))
        except Exception as e:
            print(f"⚠️  蓝色血条检测出错: {str(e)}")
        
        # 检测模板目标
        template_targets = []
        try:
            templates_dir = os.path.join(os.path.dirname(__file__), "templates", "auto_fire")
            template_files = ["enemy_faction.png", "ship_hull.png"]
            
            for template_file in template_files:
                template_path = os.path.join(templates_dir, template_file)
                if os.path.exists(template_path):
                    template = cv2.imread(template_path)
                    if template is not None:
                        result = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(result)
                        threshold = 0.5 if "faction" in template_file else 0.4
                        
                        if max_val > threshold:
                            h_t, w_t = template.shape[:2]
                            center_x = max_loc[0] + w_t // 2
                            center_y = max_loc[1] + h_t // 2
                            template_targets.append((center_x, center_y, template_file, max_val))
        except Exception as e:
            print(f"⚠️  模板检测出错: {str(e)}")
        
        # 整理目标列表
        all_targets = []
        
        # 蓝色血条目标
        if blue_targets:
            for i, (x, y) in enumerate(blue_targets):
                distance = self._calculate_distance_to_center((x, y))
                all_targets.append({
                    'id': len(all_targets) + 1,
                    'type': 'blue_health_bar',
                    'position': (x, y),
                    'description': f"🩸 蓝色血条 #{i+1}",
                    'distance': distance,
                    'priority': 1
                })
        
        # 模板目标
        if template_targets:
            for x, y, template_file, confidence in template_targets:
                template_type = template_file.replace('.png', '')
                distance = self._calculate_distance_to_center((x, y))
                icon = "🚢" if "ship" in template_type else "⚓"
                all_targets.append({
                    'id': len(all_targets) + 1,
                    'type': template_type,
                    'position': (x, y),
                    'description': f"{icon} {template_type}",
                    'distance': distance,
                    'confidence': confidence,
                    'priority': 2 if "ship" in template_type else 3
                })
        
        if not all_targets:
            print("❌ 未检测到任何目标")
            print("\n💡 建议:")
            print("  1. 确保屏幕中有敌舰")
            print("  2. 检查模板文件是否存在")
            print("  3. 调整检测参数")
            return
        
        # 按优先级和距离排序
        all_targets.sort(key=lambda t: (t['priority'], t['distance']))
        
        # 显示扫描结果
        print(f"\n🎯 扫描结果: 发现 {len(all_targets)} 个目标")
        print("=" * 60)
        
        for target in all_targets:
            x, y = target['position']
            distance = target['distance']
            priority_text = {1: "高优先级", 2: "中优先级", 3: "低优先级"}[target['priority']]
            
            print(f"{target['id']}. {target['description']}")
            print(f"   位置: ({x}, {y})")
            print(f"   距中心: {distance:.0f}px")
            print(f"   优先级: {priority_text}")
            
            if 'confidence' in target:
                print(f"   匹配度: {target['confidence']:.3f}")
            
            print()
        
        # 推荐最佳目标
        best_target = all_targets[0]
        print(f"🎯 推荐目标: {best_target['description']}")
        print(f"   理由: {priority_text}，距离中心最近({best_target['distance']:.0f}px)")
        
        input("\n按回车键继续...")

def main():
    """主函数"""
    debugger = AutoFireDebugger()
    try:
        debugger.run_debug_session()
    except KeyboardInterrupt:
        print("\n\n👋 调试结束")

if __name__ == "__main__":
    main() 