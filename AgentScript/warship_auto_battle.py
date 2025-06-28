#!/usr/bin/env python3
"""
现代战舰代肝脚本 - 主程序
自动识别游戏状态并执行相应操作
"""

# 静默导入OCR库 - 必须在其他模块之前导入
try:
    from cnocr import CnOcr
    OCR_AVAILABLE = True
    print("cnocr导入成功")
except ImportError as e:
    CnOcr = None
    OCR_AVAILABLE = False
    print("cnocr导入失败: %s" % str(e))

import sys
import os
import json
import time
import threading
import cv2
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QComboBox, QLabel, QTextEdit, 
                            QGroupBox, QSpinBox, QCheckBox, QProgressBar, QStatusBar)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QIcon
import ADBHelper
from mobile_replayer import MobileReplayer
import glob

# 获取脚本所在目录作为基础路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 奖励识别区域定义
REWARD_REGIONS = {
    "dollar_base": (1060, 383, 1187, 412),      # 美元奖励
    "dollar_extra": (1477, 382, 1592, 412),    # 美元额外奖励
    "gold_base": (1335, 382, 1375, 410),       # 黄金奖励
    "gold_extra": (1749, 382, 1777, 410),      # 黄金额外奖励
    "vip_check": (1482, 425, 1519, 465)        # VIP状态检查区域
}

class ImageMatcher:
    """图像匹配器"""
    
    def __init__(self, device_id):
        self.device_id = device_id
        self.templates_dir = os.path.join(SCRIPT_DIR, "templates")
        
    def capture_screen(self):
        """截取屏幕"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cache_dir = os.path.join(SCRIPT_DIR, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            screenshot_path = os.path.join(cache_dir, "screen_%s.png" % timestamp)
            
            if ADBHelper.screenCapture(self.device_id, screenshot_path):
                return cv2.imread(screenshot_path)
            return None
        except Exception as e:
            print("截屏失败: %s" % str(e))
            return None
    
    def match_template(self, screen_img, template_name, region=None, threshold=0.8):
        """模板匹配"""
        try:
            template_path = os.path.join(self.templates_dir, template_name)
            if not os.path.exists(template_path):
                print("模板文件不存在: %s" % template_path)
                return False, None
                
            template = cv2.imread(template_path)
            if template is None:
                print("无法读取模板文件: %s" % template_path)
                return False, None
            
            # 如果指定了区域，裁剪屏幕图像
            if region:
                x1, y1, x2, y2 = region
                # 确保区域坐标在屏幕范围内
                h, w = screen_img.shape[:2]
                x1 = max(0, min(x1, w))
                y1 = max(0, min(y1, h))
                x2 = max(x1, min(x2, w))
                y2 = max(y1, min(y2, h))
                screen_region = screen_img[y1:y2, x1:x2]
            else:
                screen_region = screen_img
            
            # 检查尺寸兼容性
            if screen_region.shape[0] < template.shape[0] or screen_region.shape[1] < template.shape[1]:
                print("模板 %s 尺寸(%dx%d) 大于检测区域(%dx%d)" % (
                    template_name, template.shape[1], template.shape[0],
                    screen_region.shape[1], screen_region.shape[0]))
                # 尝试缩放模板到合适尺寸
                scale_h = screen_region.shape[0] / template.shape[0]
                scale_w = screen_region.shape[1] / template.shape[1]
                scale = min(scale_h, scale_w) * 0.8  # 留一些余量
                
                if scale < 0.3:  # 如果缩放太小，跳过匹配
                    print("模板缩放比例过小(%.2f)，跳过匹配" % scale)
                    return False, None
                
                new_w = int(template.shape[1] * scale)
                new_h = int(template.shape[0] * scale)
                template = cv2.resize(template, (new_w, new_h))
                print("已将模板缩放到 %dx%d" % (new_w, new_h))
            
            # 执行模板匹配
            result = cv2.matchTemplate(screen_region, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            print("模板匹配 %s: %.3f" % (template_name, max_val))
            
            if max_val >= threshold:
                return True, max_loc
            return False, None
            
        except Exception as e:
            print("模板匹配出错: %s" % str(e))
            return False, None
    
    def detect_game_state(self):
        """检测游戏状态"""
        try:
            screen = self.capture_screen()
            if screen is None:
                return "unknown"
            
            # 统一检测区域：同时检测主界面、进攻、防守
            detection_region = (2109, 40, 2254, 92)
            
            # 检测主页面
            is_main, _ = self.match_template(screen, "main_page.png", detection_region, 0.7)
            if is_main:
                return "main_page"
            
            # 检测防守模式
            is_defense, _ = self.match_template(screen, "fangshou.png", detection_region, 0.7)
            if is_defense:
                return "fighting_defense"
            
            # 检测进攻模式
            is_attack, _ = self.match_template(screen, "fighting.png", detection_region, 0.7)
            if is_attack:
                return "fighting_attack"
            
            return "other"
            
        except Exception as e:
            print("检测游戏状态出错: %s" % str(e))
            return "unknown"
    
    def check_vip_status(self, screen_img):
        """检测VIP状态"""
        try:
            x1, y1, x2, y2 = REWARD_REGIONS["vip_check"]
            vip_region = screen_img[y1:y2, x1:x2]
            
            # 检测是否匹配no_vip.png
            is_no_vip, _ = self.match_template(screen_img, "no_vip.png", (x1, y1, x2, y2), 0.7)
            return not is_no_vip  # 如果匹配no_vip则返回False，否则返回True
            
        except Exception as e:
            print("检测VIP状态出错: %s" % str(e))
            return True  # 默认假设有VIP
    
    def check_battle_result_screen(self):
        """检测是否为战斗结算画面"""
        try:
            screen = self.capture_screen()
            if screen is None:
                return False
            
            # 检测区域(278, 32)到(513, 123)是否有shengli.png
            detection_region = (278, 32, 513, 123)
            
            # 检测胜利图标
            is_victory, _ = self.match_template(screen, "shengli.png", detection_region, 0.7)
            if is_victory:
                print("检测到战斗结算画面")
                return True
            
            return False
            
        except Exception as e:
            print("检测结算画面出错: %s" % str(e))
            return False
    
    def recognize_reward_text(self, region_img):
        """使用OCR识别奖励文本"""
        # 检查OCR库是否可用
        if CnOcr is None:
            return "OCR库不可用"
        
        try:
            # 保存区域图像到临时文件
            temp_path = os.path.join(SCRIPT_DIR, "cache", "temp_reward_%s.png" % datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            cv2.imwrite(temp_path, region_img)
            
            # 初始化OCR模型
            ocr = CnOcr(rec_model_name='en_PP-OCRv3')
            
            # 识别文本
            result = ocr.ocr_for_single_line(temp_path)
            
            # 删除临时文件
            try:
                os.remove(temp_path)
            except:
                pass
            
            # 处理识别结果
            reward_text = result.get("text", "0")
            cleaned_text = reward_text.replace(',', '').replace(' ', '')
            
            # 只保留数字
            numbers_only = ''.join(c for c in cleaned_text if c.isdigit())
            return numbers_only if numbers_only else "0"
            
        except Exception as e:
            print("识别奖励文本时出错: %s" % str(e))
            return "0"
    
    def recognize_battle_rewards(self):
        """识别战斗结算奖励"""
        try:
            screen = self.capture_screen()
            if screen is None:
                return None
            
            # 检测VIP状态
            has_vip = self.check_vip_status(screen)
            
            rewards = {
                "dollar_base": 0,
                "dollar_extra": 0,
                "gold_base": 0,
                "gold_extra": 0,
                "has_vip": has_vip
            }
            
            # 识别基础奖励
            for reward_type in ["dollar_base", "gold_base"]:
                x1, y1, x2, y2 = REWARD_REGIONS[reward_type]
                region_img = screen[y1:y2, x1:x2]
                reward_text = self.recognize_reward_text(region_img)
                try:
                    rewards[reward_type] = int(reward_text) if reward_text.isdigit() else 0
                except:
                    rewards[reward_type] = 0
                print("识别%s奖励: %d" % (reward_type, rewards[reward_type]))
            
            # 如果有VIP，识别额外奖励
            if has_vip:
                for reward_type in ["dollar_extra", "gold_extra"]:
                    x1, y1, x2, y2 = REWARD_REGIONS[reward_type]
                    region_img = screen[y1:y2, x1:x2]
                    reward_text = self.recognize_reward_text(region_img)
                    try:
                        rewards[reward_type] = int(reward_text) if reward_text.isdigit() else 0
                    except:
                        rewards[reward_type] = 0
                    print("识别%s奖励: %d" % (reward_type, rewards[reward_type]))
            
            return rewards
            
        except Exception as e:
            print("识别战斗奖励时出错: %s" % str(e))
            return None


class AutoBattleWorker(QThread):
    """自动战斗工作线程"""
    
    # 信号定义
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    state_detected = pyqtSignal(str)
    battle_completed = pyqtSignal(dict)  # 新增：战斗完成信号，传递奖励数据
    stats_updated = pyqtSignal(dict)     # 新增：统计数据更新信号
    
    def __init__(self, device_id, replay_file, config):
        super().__init__()
        self.device_id = device_id
        self.replay_file = replay_file
        self.config = config
        self.running = False
        self.in_replay = False  # 添加回放状态标志
        self.matcher = ImageMatcher(device_id)
        self.replayer = MobileReplayer()
        self.replayer.set_device(device_id)
        
        # 统计数据
        self.start_time = None
        self.battle_count = 0
        self.total_dollar = 0
        self.total_gold = 0
        self.current_battle_start_time = None  # 当前战斗开始时间
        self.total_battle_time = 0  # 累计战斗时间（分钟）
        self.cycle_start_time = None  # 单次循环开始时间
        
        # 连续界面计数器
        self.other_interface_count = 0  # 连续其它界面计数器
        
        # 创建battle_stats目录
        self.stats_dir = os.path.join(SCRIPT_DIR, "battle_stats")
        os.makedirs(self.stats_dir, exist_ok=True)
        
        # 获取今天的统计文件路径
        today = datetime.now().strftime("%Y%m%d")
        self.stats_file = os.path.join(self.stats_dir, "battle_stats_%s.csv" % today)
        
    def run(self):
        """主循环"""
        try:
            self.running = True
            self.start_time = datetime.now()
            self.cycle_start_time = datetime.now()  # 记录单次循环开始时间
            self.load_stats()  # 加载历史统计数据
            
            self.status_changed.emit("运行中")
            self.log_message.emit("代肝脚本启动...")
            
            while self.running:
                try:
                    # 如果正在回放，跳过状态检测
                    if self.in_replay:
                        time.sleep(1)
                        continue
                    
                    # 检测游戏状态
                    state = self.matcher.detect_game_state()
                    self.state_detected.emit(state)
                    
                    if state == "main_page":
                        self.handle_main_page()
                    elif state == "fighting_defense":
                        self.handle_defense_mode()
                    elif state == "fighting_attack":
                        self.handle_attack_mode()
                    elif state == "other":
                        self.handle_other_interface()
                    else:
                        self.log_message.emit("未知状态: %s" % state)
                        time.sleep(2)
                    
                    # 检查间隔
                    time.sleep(self.config.get("check_interval", 1))
                    
                except Exception as e:
                    self.log_message.emit("主循环出错: %s" % str(e))
                    time.sleep(2)
                    
        except Exception as e:
            self.log_message.emit("工作线程出错: %s" % str(e))
        finally:
            self.status_changed.emit("已停止")
            self.log_message.emit("代肝脚本已停止")
    
    def handle_main_page(self):
        """处理主页面"""
        # 重置其它界面计数器
        self.other_interface_count = 0
        
        self.log_message.emit("检测到主界面")
        
        # 二次确认是否真的是主界面
        self.log_message.emit("正在二次确认主界面...")
        time.sleep(1)  # 等待1秒再次检测
        
        # 再次检测游戏状态
        current_state = self.matcher.detect_game_state()
        if current_state != "main_page":
            self.log_message.emit("二次确认失败，当前状态: %s，跳过主界面处理" % current_state)
            return
        
        self.log_message.emit("二次确认成功，确实是主界面，点击进入匹配模式")
        # 点击Point:(1227, 987)进入匹配模式
        ADBHelper.touch(self.device_id, (1227, 987))
        match_wait_time = self.config.get("match_wait_time", 12)
        self.log_message.emit("已点击匹配按钮，等待%d秒..." % match_wait_time)
        
        # 启动匹配检查线程
        self.start_match_check_thread()
        
        time.sleep(match_wait_time)
    
    def start_match_check_thread(self):
        """启动匹配检查线程"""
        def check_match_success():
            try:
                # 等待1秒让界面稳定
                time.sleep(1)
                
                self.log_message.emit("检查匹配是否成功...")
                
                # 检查是否还有into_battle.png
                screen_img = self.matcher.capture_screen()
                if screen_img is not None:
                    # 检查是否有into_battle.png，相似度阈值0.7
                    is_match, location = self.matcher.match_template(screen_img, "into_battle.png", threshold=0.7)
                    if is_match:
                        self.log_message.emit("检测到进入战斗按钮仍然存在，匹配失败，执行强制进入战斗")
                        
                        # 强制进入战斗：先点击Point:(1028, 727)
                        ADBHelper.touch(self.device_id, (1028, 727))
                        self.log_message.emit("已点击第一个按钮 (1028, 727)")
                        time.sleep(1)
                        
                        # 再点击Point:(1205, 997)
                        ADBHelper.touch(self.device_id, (1205, 997))
                        self.log_message.emit("已点击第二个按钮 (1205, 997)，强制进入匹配模式")
                        
                        # 强制匹配后也要等待相同的时间
                        match_wait_time = self.config.get("match_wait_time", 12)
                        self.log_message.emit("强制匹配完成，等待%d秒..." % match_wait_time)
                        time.sleep(match_wait_time)
                    else:
                        self.log_message.emit("未检测到进入战斗按钮，匹配成功")
                else:
                    self.log_message.emit("无法捕获屏幕，跳过匹配检查")
                    
            except Exception as e:
                self.log_message.emit("匹配检查线程出错: %s" % str(e))
        
        # 在新线程中执行检查
        import threading
        check_thread = threading.Thread(target=check_match_success, daemon=True)
        check_thread.start()
    
    def handle_defense_mode(self):
        """处理防守模式"""
        # 重置其它界面计数器
        self.other_interface_count = 0
        
        self.log_message.emit("检测到防守模式，退出战斗")
        # 使用安卓返回键
        self.send_back_key()
        time.sleep(1)
        # 点击Point:(1254, 712)
        ADBHelper.touch(self.device_id, (1254, 712))
        time.sleep(0.5)
        # 点击Point:(1385, 723)
        ADBHelper.touch(self.device_id, (1385, 723))
        self.log_message.emit("已退出防守战斗")
        time.sleep(2)
    
    def handle_attack_mode(self):
        """处理进攻模式"""
        # 重置其它界面计数器
        self.other_interface_count = 0
        
        self.log_message.emit("检测到进攻模式，开始自动战斗回放")
        
        # 记录战斗开始时间
        self.current_battle_start_time = datetime.now()
        
        if self.replay_file and os.path.exists(self.replay_file):
            # 设置回放状态，停止图色识别
            self.in_replay = True
            self.state_detected.emit("fighting_attack_replaying")
            
            # 开始回放
            self.log_message.emit("开始执行回放: %s" % os.path.basename(self.replay_file))
            
            # 设置长按补偿
            compensation = self.config.get("long_press_compensation", 150)
            self.replayer.set_long_press_compensation(compensation)
            
            # 设置开局起手时间校准
            start_timing = self.config.get("start_timing_calibration", 0.2)
            self.replayer.set_start_timing_calibration(start_timing)
            
            # 加载并开始回放
            if self.replayer.load_and_replay(self.replay_file):
                self.log_message.emit("回放已开始，停止状态检测...")
                
                # 等待回放真正完成
                while self.replayer.is_replaying() and self.running:
                    time.sleep(0.5)  # 每0.5秒检查一次回放状态
                
                if self.running:  # 确保不是因为手动停止而退出
                    self.log_message.emit("回放完成，等待结算画面...")
                    
                    # 等待并检测结算画面，最多等待400秒
                    result_detected = False
                    check_attempts = 0
                    max_attempts = 400  # 最多检查400次，每次间隔1秒
                    
                    while check_attempts < max_attempts and self.running:
                        time.sleep(1)  # 每秒检查一次
                        check_attempts += 1
                        
                        if self.matcher.check_battle_result_screen():
                            result_detected = True
                            self.log_message.emit("检测到结算画面，开始识别奖励")
                            break
                        
                        self.log_message.emit("等待结算画面... (%d/%d)" % (check_attempts, max_attempts))
                    
                    if not result_detected:
                        self.log_message.emit("未检测到结算画面，跳过奖励识别")
                        self.log_message.emit("发送返回键")
                        self.send_back_key()
                        time.sleep(2)
                        
                        # 清理cache文件夹
                        self.cleanup_cache_files()
                    else:
                        # 检测到结算画面后再等待2秒确保界面稳定
                        time.sleep(2)
                        
                        # 识别奖励
                        rewards = self.matcher.recognize_battle_rewards()
                        if rewards:
                            # 计算战斗时间
                            battle_end_time = datetime.now()
                            if self.current_battle_start_time:
                                battle_duration = (battle_end_time - self.current_battle_start_time).total_seconds()
                                battle_duration_minutes = battle_duration / 60
                                self.total_battle_time += battle_duration_minutes
                                
                                self.log_message.emit("战斗时间: %.1f分钟 (%.0f秒)" % (battle_duration_minutes, battle_duration))
                            else:
                                battle_duration = 0
                                battle_duration_minutes = 0
                            
                            self.log_message.emit("成功识别战斗奖励")
                            total_dollar = rewards["dollar_base"] + rewards["dollar_extra"]
                            total_gold = rewards["gold_base"] + rewards["gold_extra"]
                            vip_status = "有VIP" if rewards["has_vip"] else "无VIP"
                            
                            self.log_message.emit("VIP状态: %s" % vip_status)
                            self.log_message.emit("美元奖励: 基础%d + 额外%d = %d" % (rewards["dollar_base"], rewards["dollar_extra"], total_dollar))
                            self.log_message.emit("黄金奖励: 基础%d + 额外%d = %d" % (rewards["gold_base"], rewards["gold_extra"], total_gold))
                            
                            # 更新统计数据
                            self.battle_count += 1
                            self.total_dollar += total_dollar
                            self.total_gold += total_gold
                            
                            # 计算单次循环时长（在战斗计数器+1时）
                            if self.cycle_start_time:
                                cycle_end_time = datetime.now()
                                cycle_duration = (cycle_end_time - self.cycle_start_time).total_seconds()
                                cycle_duration_minutes = cycle_duration / 60
                                self.log_message.emit("单次循环时长: %.1f分钟 (%.0f秒)" % (cycle_duration_minutes, cycle_duration))
                                # 重置单次循环计时器，为下一次循环做准备
                                self.cycle_start_time = cycle_end_time
                            else:
                                cycle_duration = 0
                                cycle_duration_minutes = 0
                            
                            # 计算每小时收益
                            if self.start_time:
                                # 计算平均战斗时间（无论是否有循环数据都需要计算）
                                avg_battle_time = self.total_battle_time / self.battle_count if self.battle_count > 0 else 0
                                
                                # 使用CSV数据中的单次循环时长之和来计算每小时收益
                                total_cycle_hours = self.get_total_cycle_time_hours()
                                if total_cycle_hours > 0:
                                    dollar_per_hour = int(self.total_dollar / total_cycle_hours)
                                    gold_per_hour = int(self.total_gold / total_cycle_hours)
                                    battles_per_hour = self.battle_count / total_cycle_hours
                                    
                                    self.log_message.emit("当前统计: 战斗%d场, 总美元%d, 总黄金%d" % (self.battle_count, self.total_dollar, self.total_gold))
                                    self.log_message.emit("每小时收益: 美元%d, 黄金%d, 战斗%.1f场 (基于循环时长%.1f小时)" % (dollar_per_hour, gold_per_hour, battles_per_hour, total_cycle_hours))
                                    self.log_message.emit("平均战斗时间: %.1f分钟, 本次循环: %.1f分钟" % (avg_battle_time, cycle_duration_minutes))
                                else:
                                    # 没有有效循环数据时，使用当前单次循环数据来估算每小时收益
                                    if cycle_duration_minutes > 0:
                                        # 基于当前单次循环时间估算每小时收益
                                        cycle_hours = cycle_duration_minutes / 60
                                        dollar_per_hour_estimate = int((self.total_dollar / self.battle_count) / cycle_hours) if self.battle_count > 0 else 0
                                        gold_per_hour_estimate = int((self.total_gold / self.battle_count) / cycle_hours) if self.battle_count > 0 else 0
                                        battles_per_hour_estimate = 1 / cycle_hours
                                        
                                        self.log_message.emit("当前统计: 战斗%d场, 总美元%d, 总黄金%d" % (self.battle_count, self.total_dollar, self.total_gold))
                                        self.log_message.emit("每小时收益估算: 美元%d, 黄金%d, 战斗%.1f场 (基于本次循环%.1f分钟)" % (dollar_per_hour_estimate, gold_per_hour_estimate, battles_per_hour_estimate, cycle_duration_minutes))
                                        self.log_message.emit("平均战斗时间: %.1f分钟, 本次循环: %.1f分钟" % (avg_battle_time, cycle_duration_minutes))
                                    else:
                                        self.log_message.emit("当前统计: 战斗%d场, 总美元%d, 总黄金%d" % (self.battle_count, self.total_dollar, self.total_gold))
                                        self.log_message.emit("暂无有效循环时长数据，无法计算每小时收益")
                                        self.log_message.emit("平均战斗时间: %.1f分钟, 本次循环: %.1f分钟" % (avg_battle_time, cycle_duration_minutes))
                            
                            # 发送战斗完成信号
                            battle_info = rewards.copy()
                            battle_info['battle_duration_minutes'] = battle_duration_minutes
                            battle_info['battle_duration_seconds'] = battle_duration
                            battle_info['cycle_duration_minutes'] = cycle_duration_minutes
                            battle_info['cycle_duration_seconds'] = cycle_duration
                            self.battle_completed.emit(battle_info)
                            
                            # 保存统计数据
                            battle_data = {
                                'rewards': rewards,
                                'battle_duration_minutes': battle_duration_minutes,
                                'battle_duration_seconds': battle_duration,
                                'cycle_duration_minutes': cycle_duration_minutes,
                                'cycle_duration_seconds': cycle_duration
                            }
                            self.save_stats(battle_data)
                            
                            # 发送统计更新信号
                            stats = {
                                "battle_count": self.battle_count,
                                "total_dollar": self.total_dollar,
                                "total_gold": self.total_gold
                            }
                            self.stats_updated.emit(stats)
                        else:
                            # 计算战斗时间（即使奖励识别失败）
                            if self.current_battle_start_time:
                                battle_end_time = datetime.now()
                                battle_duration = (battle_end_time - self.current_battle_start_time).total_seconds()
                                battle_duration_minutes = battle_duration / 60
                                self.total_battle_time += battle_duration_minutes
                                self.log_message.emit("识别奖励失败，但战斗时间: %.1f分钟 (%.0f秒)" % (battle_duration_minutes, battle_duration))
                            
                            self.log_message.emit("识别奖励失败")
                        
                        self.log_message.emit("发送返回键")
                        self.send_back_key()
                        time.sleep(2)
                        
                        # 清理cache文件夹
                        self.cleanup_cache_files()
                else:
                    self.log_message.emit("回放被手动停止")
            else:
                self.log_message.emit("回放启动失败")
            
            # 恢复状态检测
            self.in_replay = False
            self.log_message.emit("恢复状态检测")
            
        else:
            self.log_message.emit("未找到回放文件或文件无效")
            time.sleep(2)
    
    def cleanup_cache_files(self):
        """清理cache文件夹中的所有文件"""
        try:
            cache_dir = os.path.join(SCRIPT_DIR, "cache")
            if os.path.exists(cache_dir):
                # 获取所有文件
                files = os.listdir(cache_dir)
                removed_count = 0
                
                for file in files:
                    file_path = os.path.join(cache_dir, file)
                    if os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                            removed_count += 1
                        except Exception as e:
                            self.log_message.emit("删除缓存文件失败: %s - %s" % (file, str(e)))
                
                if removed_count > 0:
                    self.log_message.emit("已清理 %d 个cache文件" % removed_count)
                else:
                    self.log_message.emit("cache文件夹已经是空的")
            else:
                self.log_message.emit("cache文件夹不存在")
                
        except Exception as e:
            self.log_message.emit("清理cache文件夹失败: %s" % str(e))
    
    def handle_other_interface(self):
        """处理其他界面"""
        self.other_interface_count += 1
        
        self.log_message.emit("检测到其他界面 (连续第%d次)" % self.other_interface_count)
        
        # 如果连续3次检测到其它界面，检查是否有进入战斗按钮
        if self.other_interface_count >= 3:
            self.log_message.emit("连续3次检测到其它界面，检查是否有进入战斗按钮...")
            
            # 捕获当前屏幕
            screen_img = self.matcher.capture_screen()
            if screen_img is not None:
                # 检查是否有into_battle.png，相似度阈值0.7
                is_match, location = self.matcher.match_template(screen_img, "into_battle.png", threshold=0.7)
                if is_match:
                    self.log_message.emit("发现进入战斗按钮，执行强制进入匹配模式")
                    
                    # 先点击Point:(1028, 727)
                    ADBHelper.touch(self.device_id, (1028, 727))
                    self.log_message.emit("已点击第一个按钮 (1028, 727)")
                    time.sleep(1)
                    
                    # 再点击Point:(1205, 997)
                    ADBHelper.touch(self.device_id, (1205, 997))
                    self.log_message.emit("已点击第二个按钮 (1205, 997)，强制进入匹配模式")
                    
                    # 重置计数器
                    self.other_interface_count = 0
                    
                    # 强制匹配后等待配置的匹配时间
                    match_wait_time = self.config.get("match_wait_time", 12)
                    self.log_message.emit("强制匹配完成，等待%d秒..." % match_wait_time)
                    time.sleep(match_wait_time)
                    return
                else:
                    self.log_message.emit("未发现进入战斗按钮，继续发送返回键")
            else:
                self.log_message.emit("无法捕获屏幕，继续发送返回键")
            
            # 重置计数器（无论是否找到按钮都重置，避免无限循环）
            self.other_interface_count = 0
        
        # 默认处理：发送返回键
        self.send_back_key()
        time.sleep(1)
    
    def send_back_key(self):
        """发送安卓返回键"""
        try:
            import subprocess
            cmd = "adb -s %s shell input keyevent 4" % self.device_id
            subprocess.run(cmd, shell=True, capture_output=True, timeout=2)
            self.log_message.emit("已发送返回键")
        except Exception as e:
            self.log_message.emit("发送返回键失败: %s" % str(e))
    
    def stop(self):
        """停止工作线程"""
        self.running = False
        self.in_replay = False  # 重置回放状态
        self.cycle_start_time = None  # 重置单次循环计时器
        if hasattr(self, 'replayer') and self.replayer.is_replaying():
            self.replayer.stop_replay()
        
        # 停止时清理cache文件
        self.cleanup_cache_files()

    def load_stats(self):
        """加载历史统计数据"""
        try:
            if os.path.exists(self.stats_file):
                import csv
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    stats_list = list(reader)
                    if stats_list:
                        # 获取最后一条记录（当天最新的累计数据）
                        last_record = stats_list[-1]
                        self.battle_count = int(last_record.get("累计战斗次数", 0))
                        self.total_dollar = int(last_record.get("累计美元", 0))
                        self.total_gold = int(last_record.get("累计黄金", 0))
                        
                        # 计算累计战斗时间（累加所有战斗时间）
                        self.total_battle_time = 0
                        for record in stats_list:
                            battle_time_str = record.get("战斗时间(分钟)", "0")
                            try:
                                battle_time = float(battle_time_str) if battle_time_str else 0
                                self.total_battle_time += battle_time
                            except ValueError:
                                pass  # 忽略无效的战斗时间数据
                        
                        self.log_message.emit("加载今日统计数据: 战斗%d场, 美元%d, 黄金%d, 累计战斗时间%.1f分钟" % (
                            self.battle_count, self.total_dollar, self.total_gold, self.total_battle_time))
                    else:
                        self.reset_stats()
            else:
                self.reset_stats()
        except Exception as e:
            self.log_message.emit("加载历史统计数据失败: %s" % str(e))
            self.reset_stats()
    
    def get_total_cycle_time_hours(self):
        """从CSV文件计算总的循环时间（小时）"""
        try:
            if not os.path.exists(self.stats_file):
                return 0
            
            import csv
            total_cycle_minutes = 0
            
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for record in reader:
                    cycle_time_str = record.get("单次循环时长(分钟)", "0")
                    try:
                        cycle_time = float(cycle_time_str) if cycle_time_str else 0
                        total_cycle_minutes += cycle_time
                    except ValueError:
                        pass  # 忽略无效的循环时间数据
            
            # 转换为小时
            return total_cycle_minutes / 60.0
            
        except Exception as e:
            self.log_message.emit("计算总循环时间失败: %s" % str(e))
            return 0
    
    def reset_stats(self):
        """重置统计数据"""
        self.battle_count = 0
        self.total_dollar = 0
        self.total_gold = 0
        self.total_battle_time = 0
        self.log_message.emit("初始化今日统计数据")
    
    def save_stats(self, battle_data=None):
        """保存统计数据到CSV文件"""
        try:
            import csv
            
            # 检查文件是否存在，如果不存在则创建并写入表头
            file_exists = os.path.exists(self.stats_file)
            
            with open(self.stats_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 如果文件不存在，写入表头
                if not file_exists:
                    writer.writerow([
                        "时间戳", "累计战斗次数", "累计美元", "累计黄金", 
                        "本次美元基础", "本次美元额外", "本次黄金基础", "本次黄金额外", 
                        "本次总美元", "本次总黄金", "VIP状态", "战斗时间(分钟)", "战斗时间(秒)",
                        "单次循环时长(分钟)", "单次循环时长(秒)"
                    ])
                
                # 准备本次战斗数据
                if battle_data and 'rewards' in battle_data:
                    rewards = battle_data['rewards']
                    dollar_base = rewards.get("dollar_base", 0)
                    dollar_extra = rewards.get("dollar_extra", 0)
                    gold_base = rewards.get("gold_base", 0)
                    gold_extra = rewards.get("gold_extra", 0)
                    total_dollar_this = dollar_base + dollar_extra
                    total_gold_this = gold_base + gold_extra
                    vip_status = "有VIP" if rewards.get("has_vip", False) else "无VIP"
                    battle_duration_minutes = battle_data.get('battle_duration_minutes', 0)
                    battle_duration_seconds = battle_data.get('battle_duration_seconds', 0)
                    cycle_duration_minutes = battle_data.get('cycle_duration_minutes', 0)
                    cycle_duration_seconds = battle_data.get('cycle_duration_seconds', 0)
                else:
                    dollar_base = dollar_extra = gold_base = gold_extra = 0
                    total_dollar_this = total_gold_this = 0
                    vip_status = ""
                    battle_duration_minutes = battle_duration_seconds = 0
                    cycle_duration_minutes = cycle_duration_seconds = 0
                
                # 写入数据行
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([
                    timestamp, self.battle_count, self.total_dollar, self.total_gold,
                    dollar_base, dollar_extra, gold_base, gold_extra,
                    total_dollar_this, total_gold_this, vip_status,
                    "%.2f" % battle_duration_minutes, "%.0f" % battle_duration_seconds,
                    "%.2f" % cycle_duration_minutes, "%.0f" % cycle_duration_seconds
                ])
            
            self.log_message.emit("统计数据已保存到: %s" % self.stats_file)
            
        except Exception as e:
            self.log_message.emit("保存统计数据失败: %s" % str(e))


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.config_file = os.path.join(SCRIPT_DIR, "battle_config.json")
        self.config = self.load_config()
        self.init_ui()
        self.refresh_devices()
        self.refresh_replay_files()
        
        # 创建定时器用于更新当前循环时间
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_current_cycle_time)
        self.update_timer.start(1000)  # 每秒更新一次
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("现代战舰代肝脚本")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 设备选择组
        device_group = QGroupBox("设备设置")
        device_layout = QHBoxLayout(device_group)
        
        device_layout.addWidget(QLabel("选择设备:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        device_layout.addWidget(self.device_combo)
        
        self.refresh_device_btn = QPushButton("刷新设备")
        self.refresh_device_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(self.refresh_device_btn)
        
        device_layout.addStretch()
        main_layout.addWidget(device_group)
        
        # 回放文件选择组
        file_group = QGroupBox("回放设置")
        file_layout = QVBoxLayout(file_group)
        
        file_row1 = QHBoxLayout()
        file_row1.addWidget(QLabel("回放文件:"))
        self.replay_combo = QComboBox()
        self.replay_combo.setMinimumWidth(300)
        file_row1.addWidget(self.replay_combo)
        
        self.refresh_file_btn = QPushButton("刷新文件")
        self.refresh_file_btn.clicked.connect(self.refresh_replay_files)
        file_row1.addWidget(self.refresh_file_btn)
        
        file_row1.addStretch()
        file_layout.addLayout(file_row1)
        
        # 长按补偿设置
        file_row2 = QHBoxLayout()
        file_row2.addWidget(QLabel("长按补偿(ms):"))
        self.compensation_spin = QSpinBox()
        self.compensation_spin.setRange(0, 1000)
        self.compensation_spin.setValue(self.config.get("long_press_compensation", 150))
        file_row2.addWidget(self.compensation_spin)
        
        file_row2.addWidget(QLabel("检查间隔(s):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 10)
        self.interval_spin.setValue(self.config.get("check_interval", 2))
        file_row2.addWidget(self.interval_spin)
        
        file_row2.addStretch()
        file_layout.addLayout(file_row2)
        
        # 开局起手时间校准设置
        file_row3 = QHBoxLayout()
        file_row3.addWidget(QLabel("开局起手时间(s):"))
        self.start_timing_spin = QSpinBox()
        self.start_timing_spin.setRange(0, 10000)  # 支持0到10秒，单位毫秒
        self.start_timing_spin.setSuffix(" ms")
        self.start_timing_spin.setValue(int(self.config.get("start_timing_calibration", 0.2) * 1000))  # 转换为毫秒显示
        self.start_timing_spin.setSingleStep(100)  # 步进100毫秒
        file_row3.addWidget(self.start_timing_spin)
        
        file_row3.addWidget(QLabel("说明: 将第一个动作时间调整到此值"))
        file_row3.addStretch()
        file_layout.addLayout(file_row3)
        
        # 匹配等待时间设置
        file_row4 = QHBoxLayout()
        file_row4.addWidget(QLabel("匹配等待时间(s):"))
        self.match_wait_spin = QSpinBox()
        self.match_wait_spin.setRange(5, 60)  # 5-60秒
        self.match_wait_spin.setValue(self.config.get("match_wait_time", 12))
        file_row4.addWidget(self.match_wait_spin)
        
        file_row4.addWidget(QLabel("说明: 点击匹配按钮后的等待时间"))
        file_row4.addStretch()
        file_layout.addLayout(file_row4)
        
        main_layout.addWidget(file_group)
        
        # 状态显示组
        status_group = QGroupBox("运行状态")
        status_layout = QVBoxLayout(status_group)
        
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("当前状态:"))
        self.status_label = QLabel("未运行")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        status_row.addWidget(self.status_label)
        
        status_row.addWidget(QLabel("游戏状态:"))
        self.game_state_label = QLabel("未检测")
        status_row.addWidget(self.game_state_label)
        
        status_row.addStretch()
        status_layout.addLayout(status_row)
        
        # 统计数据行
        stats_row = QHBoxLayout()
        stats_row.addWidget(QLabel("战斗场次:"))
        self.battle_count_label = QLabel("0")
        stats_row.addWidget(self.battle_count_label)
        
        stats_row.addWidget(QLabel("总美元:"))
        self.total_dollar_label = QLabel("0")
        stats_row.addWidget(self.total_dollar_label)
        
        stats_row.addWidget(QLabel("总黄金:"))
        self.total_gold_label = QLabel("0")
        stats_row.addWidget(self.total_gold_label)
        
        stats_row.addStretch()
        status_layout.addLayout(stats_row)
        
        # 收益率行
        earnings_row = QHBoxLayout()
        earnings_row.addWidget(QLabel("美元/小时:"))
        self.dollar_per_hour_label = QLabel("0")
        earnings_row.addWidget(self.dollar_per_hour_label)
        
        earnings_row.addWidget(QLabel("黄金/小时:"))
        self.gold_per_hour_label = QLabel("0")
        earnings_row.addWidget(self.gold_per_hour_label)
        
        earnings_row.addWidget(QLabel("平均战斗时间:"))
        self.avg_battle_time_label = QLabel("0分钟")
        earnings_row.addWidget(self.avg_battle_time_label)
        
        earnings_row.addStretch()
        status_layout.addLayout(earnings_row)
        
        # 单次循环时长行
        cycle_row = QHBoxLayout()
        cycle_row.addWidget(QLabel("上次循环时长:"))
        self.last_cycle_time_label = QLabel("0分钟")
        cycle_row.addWidget(self.last_cycle_time_label)
        
        cycle_row.addWidget(QLabel("当前循环用时:"))
        self.current_cycle_time_label = QLabel("0:00")
        cycle_row.addWidget(self.current_cycle_time_label)
        
        cycle_row.addStretch()
        status_layout.addLayout(cycle_row)
        
        main_layout.addWidget(status_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始运行")
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }")
        self.start_btn.clicked.connect(self.start_auto_battle)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止运行")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 10px; }")
        self.stop_btn.clicked.connect(self.stop_auto_battle)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_config_btn)
        
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        # 日志显示
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print("加载配置失败: %s" % str(e))
        
        # 返回默认配置
        return {
            "device_id": "",
            "replay_file": "",
            "long_press_compensation": 150,
            "check_interval": 2,
            "start_timing_calibration": 0.2,
            "match_wait_time": 12
        }
    
    def save_config(self):
        """保存配置"""
        try:
            self.config = {
                "device_id": self.device_combo.currentText(),
                "replay_file": self.replay_combo.currentData(),
                "long_press_compensation": self.compensation_spin.value(),
                "check_interval": self.interval_spin.value(),
                "start_timing_calibration": self.start_timing_spin.value() / 1000.0,  # 转换为秒
                "match_wait_time": self.match_wait_spin.value()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            
            self.log_message("配置已保存")
            
        except Exception as e:
            self.log_message("保存配置失败: %s" % str(e))
    
    def refresh_devices(self):
        """刷新设备列表"""
        try:
            self.device_combo.clear()
            devices = ADBHelper.getDevicesList()
            
            if devices:
                for device in devices:
                    self.device_combo.addItem(device)
                
                # 恢复之前选择的设备
                saved_device = self.config.get("device_id", "")
                if saved_device in devices:
                    index = self.device_combo.findText(saved_device)
                    if index >= 0:
                        self.device_combo.setCurrentIndex(index)
                
                self.log_message("找到 %d 个设备" % len(devices))
            else:
                self.log_message("未找到连接的设备")
                
        except Exception as e:
            self.log_message("刷新设备失败: %s" % str(e))
    
    def refresh_replay_files(self):
        """刷新回放文件列表"""
        try:
            self.replay_combo.clear()
            
            recording_dir = os.path.join(SCRIPT_DIR, "recording")
            if not os.path.exists(recording_dir):
                os.makedirs(recording_dir)
            
            # 查找JSON文件
            pattern = os.path.join(recording_dir, "*.json")
            json_files = glob.glob(pattern)
            
            if json_files:
                # 按修改时间排序（最新的在前面）
                json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                
                for file_path in json_files:
                    filename = os.path.basename(file_path)
                    self.replay_combo.addItem(filename, file_path)
                
                # 恢复之前选择的文件
                saved_file = self.config.get("replay_file", "")
                if saved_file:
                    for i in range(self.replay_combo.count()):
                        if self.replay_combo.itemData(i) == saved_file:
                            self.replay_combo.setCurrentIndex(i)
                            break
                
                self.log_message("找到 %d 个回放文件" % len(json_files))
                self.log_message("回放文件目录: %s" % recording_dir)
            else:
                self.log_message("未找到回放文件")
                self.log_message("回放文件目录: %s" % recording_dir)
                
        except Exception as e:
            self.log_message("刷新回放文件失败: %s" % str(e))
    
    def start_auto_battle(self):
        """开始自动战斗"""
        try:
            device_id = self.device_combo.currentText()
            replay_file = self.replay_combo.currentData()
            
            if not device_id:
                self.log_message("请选择设备")
                return
            
            if not replay_file or not os.path.exists(replay_file):
                self.log_message("请选择有效的回放文件")
                return
            
            # 更新配置
            config = {
                "long_press_compensation": self.compensation_spin.value(),
                "check_interval": self.interval_spin.value(),
                "start_timing_calibration": self.start_timing_spin.value() / 1000.0,  # 转换为秒
                "match_wait_time": self.match_wait_spin.value()
            }
            
            # 创建工作线程
            self.worker = AutoBattleWorker(device_id, replay_file, config)
            self.worker.status_changed.connect(self.on_status_changed)
            self.worker.log_message.connect(self.log_message)
            self.worker.state_detected.connect(self.on_state_detected)
            self.worker.battle_completed.connect(self.on_battle_completed)
            self.worker.stats_updated.connect(self.on_stats_updated)
            
            # 启动线程
            self.worker.start()
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            
            self.log_message("自动战斗已启动")
            
        except Exception as e:
            self.log_message("启动失败: %s" % str(e))
    
    def stop_auto_battle(self):
        """停止自动战斗"""
        try:
            if self.worker and self.worker.isRunning():
                self.worker.stop()
                self.worker.wait(5000)  # 等待最多5秒
            
            # 更新UI状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            
            # 重置循环时间显示
            self.current_cycle_time_label.setText("0:00")
            
            self.log_message("自动战斗已停止")
            
        except Exception as e:
            self.log_message("停止失败: %s" % str(e))
    
    def on_status_changed(self, status):
        """状态变化处理"""
        self.status_label.setText(status)
        if status == "运行中":
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def on_state_detected(self, state):
        """游戏状态检测处理"""
        state_map = {
            "main_page": "主界面",
            "fighting_defense": "战斗(防守)",
            "fighting_attack": "战斗(进攻)",
            "fighting_attack_replaying": "战斗(回放中)",
            "other": "其他界面",
            "unknown": "未知"
        }
        self.game_state_label.setText(state_map.get(state, state))
    
    def on_battle_completed(self, battle_info):
        """战斗完成处理"""
        # 这个方法在MainWindow中应该更新UI显示
        total_dollar = battle_info["dollar_base"] + battle_info["dollar_extra"]
        total_gold = battle_info["gold_base"] + battle_info["gold_extra"]
        battle_time_minutes = battle_info.get('battle_duration_minutes', 0)
        cycle_time_minutes = battle_info.get('cycle_duration_minutes', 0)
        
        self.log_message("战斗完成 - 美元: %d, 黄金: %d, 战斗时间: %.1f分钟, 循环时长: %.1f分钟" % (
            total_dollar, total_gold, battle_time_minutes, cycle_time_minutes))
        
        # 更新上次循环时长显示
        self.last_cycle_time_label.setText("%.1f分钟" % cycle_time_minutes)
    
    def on_stats_updated(self, stats):
        """统计数据更新处理"""
        # 更新UI显示
        self.battle_count_label.setText(str(stats["battle_count"]))
        self.total_dollar_label.setText("{:,}".format(stats['total_dollar']))
        self.total_gold_label.setText("{:,}".format(stats['total_gold']))
        
        # 计算每小时收益和平均战斗时间
        if hasattr(self.worker, 'get_total_cycle_time_hours'):
            # 使用CSV数据中的单次循环时长之和来计算每小时收益
            total_cycle_hours = self.worker.get_total_cycle_time_hours()
            if total_cycle_hours > 0:
                dollar_per_hour = int(stats["total_dollar"] / total_cycle_hours)
                gold_per_hour = int(stats["total_gold"] / total_cycle_hours)
                self.dollar_per_hour_label.setText("{:,}".format(dollar_per_hour))
                self.gold_per_hour_label.setText("{:,}".format(gold_per_hour))
            else:
                self.dollar_per_hour_label.setText("0")
                self.gold_per_hour_label.setText("0")
        else:
            # 如果worker不存在或没有相应方法，显示0
            self.dollar_per_hour_label.setText("0")
            self.gold_per_hour_label.setText("0")
        
        # 显示平均战斗时间
        if stats["battle_count"] > 0 and hasattr(self.worker, 'total_battle_time'):
            avg_time = self.worker.total_battle_time / stats["battle_count"]
            self.avg_battle_time_label.setText("%.1f分钟" % avg_time)
        else:
            self.avg_battle_time_label.setText("0分钟")
        
        # 更新当前循环用时
        if hasattr(self.worker, 'cycle_start_time') and self.worker and self.worker.cycle_start_time:
            current_cycle_duration_seconds = (datetime.now() - self.worker.cycle_start_time).total_seconds()
            minutes = int(current_cycle_duration_seconds // 60)
            seconds = int(current_cycle_duration_seconds % 60)
            self.current_cycle_time_label.setText("%d:%02d" % (minutes, seconds))
        else:
            self.current_cycle_time_label.setText("0:00")
        
        self.log_message("统计更新 - 战斗: %d场, 美元: %s, 黄金: %s" % (stats['battle_count'], "{:,}".format(stats['total_dollar']), "{:,}".format(stats['total_gold'])))
    
    def handle_rewards(self, rewards):
        """处理奖励"""
        # 这个方法已经在AutoBattleWorker中处理了，MainWindow中不需要重复实现
        pass
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = "[%s] %s" % (timestamp, message)
        self.log_text.append(formatted_message)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.worker and self.worker.isRunning():
            self.stop_auto_battle()
        
        # 保存配置
        self.save_config()
        event.accept()

    def update_current_cycle_time(self):
        """更新当前循环时间"""
        if hasattr(self.worker, 'cycle_start_time') and self.worker and self.worker.cycle_start_time:
            current_cycle_duration_seconds = (datetime.now() - self.worker.cycle_start_time).total_seconds()
            minutes = int(current_cycle_duration_seconds // 60)
            seconds = int(current_cycle_duration_seconds % 60)
            self.current_cycle_time_label.setText("%d:%02d" % (minutes, seconds))
        else:
            self.current_cycle_time_label.setText("0:00")


def cleanup_cache_on_startup():
    """启动时清理cache文件夹"""
    try:
        cache_dir = os.path.join(SCRIPT_DIR, "cache")
        if os.path.exists(cache_dir):
            files = os.listdir(cache_dir)
            removed_count = 0
            
            for file in files:
                file_path = os.path.join(cache_dir, file)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        removed_count += 1
                    except Exception as e:
                        print("删除缓存文件失败: %s - %s" % (file, str(e)))
            
            if removed_count > 0:
                print("启动时清理了 %d 个cache文件" % removed_count)
            else:
                print("cache文件夹已经是空的")
        else:
            print("cache文件夹不存在")
            
    except Exception as e:
        print("启动时清理cache文件夹失败: %s" % str(e))


def main():
    """主函数"""
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("现代战舰代肝脚本")
        
        # 检查依赖
        print("检查依赖...")
        
        # 检查OCR库
        if not OCR_AVAILABLE:
            print("警告: CnOcr库不可用，将无法识别战斗奖励")
            print("请运行: pip install cnocr")
        else:
            print("OCR库检查通过")
        
        # 创建必要目录（相对于脚本目录）
        os.makedirs(os.path.join(SCRIPT_DIR, "templates"), exist_ok=True)
        os.makedirs(os.path.join(SCRIPT_DIR, "recording"), exist_ok=True)
        os.makedirs(os.path.join(SCRIPT_DIR, "cache"), exist_ok=True)
        os.makedirs(os.path.join(SCRIPT_DIR, "battle_stats"), exist_ok=True)
        
        # 启动时清理cache文件夹
        cleanup_cache_on_startup()
        
        # 创建主窗口
        window = MainWindow()
        window.show()
        
        print("现代战舰代肝脚本启动成功")
        print("如果程序正常运行，这个窗口会保持打开状态")
        
        sys.exit(app.exec_())
        
    except Exception as e:
        import traceback
        error_msg = "程序启动失败: %s\n\n详细错误信息:\n%s" % (str(e), traceback.format_exc())
        print(error_msg)
        
        # 尝试显示错误对话框
        try:
            app = QApplication(sys.argv) if 'app' not in locals() else app
            from PyQt5.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("代肝脚本启动错误")
            msg.setText("程序启动时发生错误")
            msg.setDetailedText(error_msg)
            msg.exec_()
        except:
            pass
        
        # 暂停5秒让用户看到错误信息
        print("\n程序将在5秒后退出...")
        import time
        time.sleep(5)
        sys.exit(1)


if __name__ == "__main__":
    main() 