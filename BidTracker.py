#!/usr/bin/env python3
"""
现代战舰市场报价追踪工具
"""

# 运行模式配置
# 0: GUI模式 (推荐)
# 1: 命令行模式 (已废弃，仅兼容)
RUN_MODE = 0

# 静默导入OCR库 - 必须在其他模块之前导入，这是解决cnocr万年难题的关键！
try:
    from cnocr import CnOcr
    CNOCR_AVAILABLE = True
    print("cnocr导入成功")
except ImportError as e:
    CnOcr = None
    CNOCR_AVAILABLE = False
    print("cnocr导入失败: %s" % str(e))

import sys
import os
import glob
import pandas as pd
from datetime import datetime
import re
import time
import RaphaelScriptHelper as rsh
import argparse
import concurrent.futures
from templates.modern_warship.category_mapping import CATEGORY_DICT, ITEM_DICT, get_category_name, get_item_name
import json
import csv

# 导入ModernWarshipMarket
sys.path.append("./")
try:
    import ModernWarshipMarket as mwm
    import MarketPriceRecognizer as mpr
except ImportError as e:
    print("无法导入必要模块: %s" % str(e))
    sys.exit(1)

# 导入AutoTradeGUI（在最后导入避免循环依赖）
try:
    import AutoTradeGUI
    AUTOTRADE_GUI_AVAILABLE = True
    # 设置AutoTradeGUI中的BIDTRACKER_AVAILABLE标志
    AutoTradeGUI.BIDTRACKER_AVAILABLE = True
    print("AutoTradeGUI模块导入成功")
except ImportError as e:
    AutoTradeGUI = None
    AUTOTRADE_GUI_AVAILABLE = False
    print(f"AutoTradeGUI模块导入失败: {str(e)}")

# 设置设备类型和ID
rsh.deviceType = 1  # 安卓设备
rsh.deviceID = ""   # 请在此填写您的设备ID，可通过adb devices命令获取

# 报价追踪相关设置
BID_TRACKER_FILE = "./market_data/报价追踪.csv"
SHOPPING_LIST_FILE = "./market_data/清单.json"  # 新增：购物清单JSON文件
TEMPLATE_DIR = mwm.TEMPLATE_DIR
DEFAULT_DELAY = mwm.DEFAULT_DELAY
SCREENSHOT_DELAY = mwm.SCREENSHOT_DELAY
SCREENSHOT_DIR = "./cache/market_screenshots/"  # 截图保存目录

# 特定坐标点
MARKET_ENTRY_POINT = ((203, 362))  # 进入报价界面的坐标
BUY_ICON_POINT = (330, 143)      # 购买图标的坐标

# 价格识别相关设置
MAX_RECOGNITION_WORKERS = 4  # 最大同时运行的价格识别线程数

# 创建线程池
price_executor = None

# GUI控制变量
is_tracking_active = False
tracking_gui_callback = None

# 确保截图目录存在
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

# 确保市场数据目录存在
if not os.path.exists("./market_data"):
    os.makedirs("./market_data")

def find_latest_price_data():
    """查找最新的价格数据文件"""
    price_files = glob.glob("market_data/price_data_*.csv")
    if not price_files:
        print("未找到价格数据文件")
        return None
    return max(price_files)

def search_items(keyword, price_df):
    """根据关键词搜索物品"""
    pattern = re.compile(keyword, re.IGNORECASE)
    matches = price_df[price_df['物品名称'].str.contains(pattern, na=False)]
    return matches

def load_tracked_items():
    """加载已追踪的物品列表"""
    if os.path.exists(BID_TRACKER_FILE):
        return pd.read_csv(BID_TRACKER_FILE)
    else:
        # 创建一个新的DataFrame，包含所有可能的本人价格列和利润率列
        return pd.DataFrame(columns=[
            "物品名称", "物品分类", "购买价格", "出售价格", "本人购买价格", "本人售出价格", 
            "低买低卖溢价", "利润率", "时间戳", "出价数量", "上架数量", "稀有度"
        ])

def save_tracked_items(tracked_df):
    """保存追踪物品列表"""
    tracked_df.to_csv(BID_TRACKER_FILE, index=False)
    print(f"已保存追踪列表到 {BID_TRACKER_FILE}")

def add_item_to_tracker(item):
    """添加物品到追踪列表"""
    tracked_df = load_tracked_items()
    
    # 检查是否已存在相同物品
    if not tracked_df.empty and item['物品名称'] in tracked_df['物品名称'].values:
        print(f"物品 '{item['物品名称']}' 已在追踪列表中")
        return tracked_df
    
    # 计算利润率
    profit_rate = ''
    try:
        # 获取购买价格和低买低卖溢价
        buying_price_str = item.get('购买价格', '')
        spread_str = item.get('低买低卖溢价', '')
        
        if buying_price_str and spread_str and spread_str != 'N/A':
            # 解析购买价格，找到最高价格
            buying_prices = []
            for price in buying_price_str.split(';'):
                try:
                    clean_price = price.strip().replace(',', '').replace(' ', '')
                    if clean_price:
                        buying_prices.append(float(clean_price))
                except:
                    pass
            
            if buying_prices:
                max_buying = max(buying_prices)
                spread = float(spread_str)
                
                # 计算利润率: 溢价 / (最高购买价格 + 1) * 100%
                profit_rate_value = (spread / (max_buying + 1) * 100) if (max_buying + 1) > 0 else 0
                profit_rate = f"{profit_rate_value:.2f}%"
                print(f"计算利润率: {spread} / ({max_buying} + 1) × 100% = {profit_rate}")
    except Exception as e:
        print(f"计算利润率时出错: {str(e)}")
        profit_rate = ''
    
    # 直接从市场数据复制数据行，添加本人价格列和利润率列并初始化为空值
    new_item = {
        "物品名称": item['物品名称'],
        "物品分类": item['物品分类'],
        "购买价格": item.get('购买价格', ''),
        "出售价格": item.get('出售价格', ''),
        "本人购买价格": '',  # 初始化为空值
        "本人售出价格": '',  # 初始化为空值
        "低买低卖溢价": item.get('低买低卖溢价', ''),
        "利润率": profit_rate,  # 计算得出的利润率
        "时间戳": item.get('时间戳', ''),  # 从市场数据复制时间戳
        "出价数量": item.get('出价数量', ''),
        "上架数量": item.get('上架数量', ''),
        "稀有度": item.get('稀有度', '')
    }
    
    tracked_df = pd.concat([tracked_df, pd.DataFrame([new_item])], ignore_index=True)
    save_tracked_items(tracked_df)
    print(f"已添加 '{item['物品名称']}' 到追踪列表 (利润率: {profit_rate})")
    
    # 同时添加到JSON购物清单
    add_item_to_shopping_list(item['物品名称'], item['物品分类'])
    
    return tracked_df

def open_bid_interface():
    """打开报价界面"""
    # 打开市场
    print("打开市场界面...")
    if not mwm.open_market():
        print("无法打开市场界面，请检查游戏状态")
        return False
    
    # 等待市场界面完全加载
    print("等待市场界面完全加载...")
    time.sleep(1.0)  # 增加1秒等待时间，确保市场界面完全加载
    
    # 点击进入报价界面
    print(f"点击报价入口坐标: {MARKET_ENTRY_POINT}")
    mwm.click_point(MARKET_ENTRY_POINT)
    time.sleep(DEFAULT_DELAY * 2)
    
    # 点击购买图标
    print(f"点击购买图标坐标: {BUY_ICON_POINT}")
    mwm.click_point(BUY_ICON_POINT)
    time.sleep(DEFAULT_DELAY * 2)
    
    return True

def get_item_key_from_name(item_name):
    """从物品中文名获取对应的英文键名"""
    for key, value in ITEM_DICT.items():
        if value == item_name:
            return key
    return None

def get_category_key_from_name(category_name):
    """从分类中文名获取对应的英文键名"""
    for key, value in CATEGORY_DICT.items():
        if value == category_name:
            return key
    return None

def find_and_click_item(item_name, item_category):
    """查找并点击物品"""
    print(f"正在查找物品: {item_name}")
    
    # 获取物品的英文键名
    item_key = get_item_key_from_name(item_name)
    if not item_key:
        print(f"未能找到物品 '{item_name}' 的映射键名")
        return False
    
    # 获取物品分类的英文键名
    category_key = get_category_key_from_name(item_category)
    if not category_key:
        print(f"未能找到分类 '{item_category}' 的映射键名")
        return False
    
    # 构建物品模板路径
    item_template_path = f"{TEMPLATE_DIR}market_items/{category_key}/{item_key}.png"
    
    if not os.path.exists(item_template_path):
        print(f"未找到物品 '{item_name}' 的模板图片: {item_template_path}")
        return False
    
    # 尝试点击物品
    print(f"尝试点击物品图标 (使用模板: {item_template_path})")
    try:
        center = rsh.find_pic(item_template_path, returnCenter=True)
        if center:
            rsh.touch(center)
            print(f"成功点击物品 '{item_name}'")
            time.sleep(DEFAULT_DELAY * 2)  # 等待物品详情页加载
            return True
        else:
            print(f"未能找到物品图标，匹配失败")
            return False
    except Exception as e:
        print(f"查找物品时出错: {str(e)}")
        print(f"跳过物品 '{item_name}'，继续处理下一个")
        return False

def take_stable_screenshot(filename_prefix):
    """
    获取稳定的屏幕截图（确保没有loading图标）
    
    参数:
        filename_prefix: 文件名前缀
    
    返回:
        稳定截图的路径或None
    """
    try:
        max_attempts = 5  # 最大尝试次数
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            print(f"尝试截图 #{attempt}/{max_attempts}...")

            # 获取截图
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            screenshot_path = f"{SCREENSHOT_DIR}{filename_prefix}_{timestamp}.png"
            rsh.ADBHelper.screenCapture(rsh.deviceID, screenshot_path)
            
            # 检查是否有loading图标（简化版检查）
            if os.path.exists(screenshot_path):
                print(f"获取到截图: {screenshot_path}")
                return screenshot_path
            
            print(f"截图失败，将重试...")
            # 额外等待一段时间再尝试
            time.sleep(0.05)
        
        print(f"达到最大尝试次数({max_attempts})，截图可能失败")
        return screenshot_path if 'screenshot_path' in locals() else None
    except Exception as e:
        print(f"获取稳定截图失败: {str(e)}")
        return None

# 修改process_price_recognition函数
def process_price_recognition(screenshot_path, item_name, item_category, detect_own_prices=False):
    """处理价格识别"""
    try:
        # 调用价格识别，根据参数决定是否启用本人价格检测，禁用自动保存避免重复保存
        price_img_paths, markup_img_path, price_data = mpr.process_screenshot(
            screenshot_path, item_name, item_category, detect_own_prices, auto_save=False
        )
        
        # 如果是BidTracker调用且检测到数据，进行自定义溢价计算
        if detect_own_prices and price_data:
            # 计算自定义的低买低卖溢价和利润率
            spread, profit_rate = calculate_custom_spread(item_name, item_category, price_data)
            if spread is not None:
                price_data['低买低卖溢价'] = spread
                price_data['利润率'] = profit_rate
                print(f"使用自定义溢价计算结果: {spread}")
            
            # 保存到报价追踪文件
            save_bid_tracker_data(item_name, item_category, price_data)
        
        return price_img_paths, markup_img_path, price_data
    except Exception as e:
        print("价格识别出错: %s" % str(e))
        return [], None, {}

def calculate_custom_spread(item_name, item_category, price_data):
    """
    计算自定义的低买低卖溢价和利润率
    
    参数:
        item_name: 物品名称
        item_category: 物品分类
        price_data: 价格数据字典
        
    返回:
        (计算出的溢价值, 利润率百分比)，如果无法计算则返回(None, None)
    """
    try:
        # 获取本人购买价格和本人售出价格
        own_buying_price = price_data.get('本人购买价格', '')
        own_selling_price = price_data.get('本人售出价格', '')
        
        # 情况1: 存在本人购买价格时
        if own_buying_price and own_buying_price != '':
            # 获取所有出售价格
            selling_prices = []
            for key, price in price_data.items():
                if 'selling' in key and key != '本人售出价格':
                    try:
                        clean_price = price.replace(',', '').replace(' ', '')
                        if clean_price:
                            selling_prices.append(float(clean_price))
                    except:
                        pass
            
            if selling_prices:
                try:
                    min_selling = min(selling_prices)
                    own_buying = float(own_buying_price.replace(',', '').replace(' ', ''))
                    # 公式: (最低出售价格 × 0.8 - 1) - 本人购买价格
                    spread = int((min_selling * 0.8 - 1) - own_buying)
                    # 利润率 = 溢价 / 本人购买价格 * 100%
                    profit_rate = (spread / own_buying * 100) if own_buying > 0 else 0
                    print(f"本人购买价格溢价计算: ({min_selling} × 0.8 - 1) - {own_buying} = {spread}")
                    print(f"利润率计算: {spread} / {own_buying} × 100% = {profit_rate:.2f}%")
                    return spread, f"{profit_rate:.2f}%"
                except Exception as e:
                    print(f"计算本人购买价格溢价时出错: {str(e)}")
        
        # 情况2: 存在本人售出价格时
        elif own_selling_price and own_selling_price != '':
            # 从购物清单的正在售出字段获取进货价
            purchase_price = get_purchase_price_from_selling_list(item_name, item_category)
            if purchase_price is not None:
                try:
                    own_selling = float(own_selling_price.replace(',', '').replace(' ', ''))
                    # 公式: 本人售出价格 × 0.8 - 进货价
                    spread = int(own_selling * 0.8 - purchase_price)
                    # 利润率 = 溢价 / 进货价 * 100%
                    profit_rate = (spread / purchase_price * 100) if purchase_price > 0 else 0
                    print(f"本人售出价格溢价计算: {own_selling} × 0.8 - {purchase_price} = {spread}")
                    print(f"利润率计算: {spread} / {purchase_price} × 100% = {profit_rate:.2f}%")
                    return spread, f"{profit_rate:.2f}%"
                except Exception as e:
                    print(f"计算本人售出价格溢价时出错: {str(e)}")
            else:
                print(f"未找到物品 '{item_name}' 的进货价，无法计算售出溢价")
        
        # 情况3: 没有本人价格时，使用原有逻辑
        else:
            # 获取所有购买和出售价格
            buying_prices = []
            selling_prices = []
            
            for key, price in price_data.items():
                if 'buying' in key:
                    try:
                        clean_price = price.replace(',', '').replace(' ', '')
                        if clean_price:
                            buying_prices.append(float(clean_price))
                    except:
                        pass
                elif 'selling' in key:
                    try:
                        clean_price = price.replace(',', '').replace(' ', '')
                        if clean_price:
                            selling_prices.append(float(clean_price))
                    except:
                        pass
            
            if buying_prices and selling_prices:
                try:
                    max_buying = max(buying_prices)
                    min_selling = min(selling_prices)
                    # 原有公式: (最低出售价格 × 0.8 - 1) - (最高购买价格 + 1)
                    spread = int((min_selling * 0.8 - 1) - (max_buying + 1))
                    # 利润率 = 溢价 / (最高购买价格 + 1) * 100%
                    profit_rate = (spread / (max_buying + 1) * 100) if (max_buying + 1) > 0 else 0
                    print(f"普通溢价计算: ({min_selling} × 0.8 - 1) - ({max_buying} + 1) = {spread}")
                    print(f"利润率计算: {spread} / ({max_buying} + 1) × 100% = {profit_rate:.2f}%")
                    return spread, f"{profit_rate:.2f}%"
                except Exception as e:
                    print(f"计算普通溢价时出错: {str(e)}")
        
        return None, None
    except Exception as e:
        print(f"计算自定义溢价时出错: {str(e)}")
        return None, None

def get_purchase_price_from_selling_list(item_name, item_category):
    """
    从购物清单的正在售出字段获取进货价
    
    参数:
        item_name: 物品名称
        item_category: 物品分类
        
    返回:
        进货价（数字），如果找不到则返回None
    """
    try:
        shopping_list = load_shopping_list()
        selling_items = shopping_list.get("正在售出", [])
        
        for item in selling_items:
            if (item.get("物品名称") == item_name and 
                item.get("物品分类") == item_category):
                purchase_price = item.get("进货价")
                if purchase_price is not None:
                    try:
                        # 转换为数字
                        if isinstance(purchase_price, str):
                            purchase_price = float(purchase_price.replace(',', '').replace(' ', ''))
                        return float(purchase_price)
                    except:
                        print(f"无法解析进货价: {purchase_price}")
                        return None
        
        print(f"在正在售出清单中未找到物品: {item_name}")
        return None
    except Exception as e:
        print(f"获取进货价时出错: {str(e)}")
        return None

def save_bid_tracker_data(item_name, category_name, price_data):
    """
    保存数据到报价追踪文件（自定义格式）
    增加去重逻辑：当新数据与最新时间戳的该物品没区别时不写入CSV
    
    参数:
        item_name: 物品名称
        category_name: 物品分类
        price_data: 价格数据字典
    """
    try:
        # 收集所有购买和出售价格
        buying_prices = []
        selling_prices = []
        own_buying_price = ""
        own_selling_price = ""
        
        for key, price in price_data.items():
            if key == '本人购买价格':
                own_buying_price = price
            elif key == '本人售出价格':
                own_selling_price = price
            elif 'buying' in key:
                try:
                    clean_price = price.replace(',', '').replace(' ', '')
                    if clean_price:
                        buying_prices.append(int(clean_price))
                except:
                    print(f"无法解析购买价格: {price}")
            elif 'selling' in key:
                try:
                    clean_price = price.replace(',', '').replace(' ', '')
                    if clean_price:
                        selling_prices.append(int(clean_price))
                except:
                    print(f"无法解析出售价格: {price}")
        
        # 格式化价格字符串
        def format_price_with_commas(price):
            return f"{price:,}" if isinstance(price, (int, float)) else str(price)
        
        buying_price_str = '; '.join(format_price_with_commas(p) for p in buying_prices) if buying_prices else ''
        selling_price_str = '; '.join(format_price_with_commas(p) for p in selling_prices) if selling_prices else ''
        
        # 检查购买价格是否为空或nan，如果是则跳过写入
        if not buying_price_str or buying_price_str.strip() == '' or buying_price_str.lower() == 'nan':
            print(f"[跳过写入] 物品 '{item_name}' 的购买价格为空或nan，跳过写入CSV")
            # 如果有GUI回调，通知数据无效
            if tracking_gui_callback:
                tracking_gui_callback('data_invalid', {
                    'item_name': item_name,
                    'category': category_name,
                    'reason': '购买价格为空或nan'
                })
            return False
        
        # 获取额外信息
        bid_count = price_data.get('bid_count', 0)
        listing_count = price_data.get('listing_count', 0)
        rarity = price_data.get('rarity', '')
        spread = price_data.get('低买低卖溢价', 'N/A')
        profit_rate = price_data.get('利润率', '')
        
        # 检查是否需要写入（去重逻辑）
        if os.path.exists(BID_TRACKER_FILE):
            # 读取现有数据
            existing_df = pd.read_csv(BID_TRACKER_FILE)
            
            # 查找该物品的最新记录
            item_records = existing_df[existing_df['物品名称'] == item_name]
            if not item_records.empty:
                # 按时间戳排序，获取最新记录
                item_records_sorted = item_records.sort_values('时间戳')
                latest_record = item_records_sorted.iloc[-1]
                
                # 获取最新记录的各字段值，处理NaN值
                latest_buying = str(latest_record.get('购买价格', '')) if pd.notna(latest_record.get('购买价格')) else ''
                latest_selling = str(latest_record.get('出售价格', '')) if pd.notna(latest_record.get('出售价格')) else ''
                latest_own_buying = str(latest_record.get('本人购买价格', '')) if pd.notna(latest_record.get('本人购买价格')) else ''
                latest_own_selling = str(latest_record.get('本人售出价格', '')) if pd.notna(latest_record.get('本人售出价格')) else ''
                latest_bid_count = str(latest_record.get('出价数量', '')) if pd.notna(latest_record.get('出价数量')) else ''
                latest_listing_count = str(latest_record.get('上架数量', '')) if pd.notna(latest_record.get('上架数量')) else ''
                
                # 当前要写入的数据
                current_own_buying = own_buying_price if own_buying_price else ''
                current_own_selling = own_selling_price if own_selling_price else ''
                
                # 标准化数字字符串的比较函数（处理浮点数.0问题）
                def normalize_number_str(s):
                    """标准化数字字符串，去掉不必要的.0"""
                    s = str(s).strip()
                    if s and s != '':
                        try:
                            # 尝试转换为浮点数再转回字符串，去掉.0
                            num = float(s)
                            if num == int(num):
                                return str(int(num))
                            else:
                                return str(num)
                        except:
                            pass
                    return s
                
                # 标准化比较字段
                latest_own_buying_norm = normalize_number_str(latest_own_buying)
                current_own_buying_norm = normalize_number_str(current_own_buying)
                latest_own_selling_norm = normalize_number_str(latest_own_selling)
                current_own_selling_norm = normalize_number_str(current_own_selling)
                
                print(f"[去重检查] {item_name}")
                print(f"  最新记录购买价格: '{latest_buying}' vs 当前: '{buying_price_str}'")
                print(f"  最新记录出售价格: '{latest_selling}' vs 当前: '{selling_price_str}'")
                print(f"  最新记录本人购买: '{latest_own_buying}' -> '{latest_own_buying_norm}' vs 当前: '{current_own_buying}' -> '{current_own_buying_norm}'")
                print(f"  最新记录本人出售: '{latest_own_selling}' -> '{latest_own_selling_norm}' vs 当前: '{current_own_selling}' -> '{current_own_selling_norm}'")
                print(f"  最新记录出价数量: '{latest_bid_count}' vs 当前: '{bid_count}'")
                print(f"  最新记录上架数量: '{latest_listing_count}' vs 当前: '{listing_count}'")
                
                # 比较关键数据是否完全相同（使用标准化后的数字）
                data_identical = (
                    latest_buying == buying_price_str and
                    latest_selling == selling_price_str and
                    latest_own_buying_norm == current_own_buying_norm and
                    latest_own_selling_norm == current_own_selling_norm and
                    latest_bid_count == str(bid_count) and
                    latest_listing_count == str(listing_count)
                )
                
                if data_identical:
                    print(f"[去重] 物品 '{item_name}' 的数据与最新记录完全相同，跳过写入")
                    # 如果有GUI回调，通知数据未变化
                    if tracking_gui_callback:
                        tracking_gui_callback('data_unchanged', {
                            'item_name': item_name,
                            'category': category_name,
                            'reason': '数据无变化'
                        })
                    return False
                else:
                    print(f"[去重] 物品 '{item_name}' 的数据有变化，将写入新记录")
        
        # 检查CSV文件是否存在，不存在则创建并写入表头
        file_exists = os.path.exists(BID_TRACKER_FILE)
        
        with open(BID_TRACKER_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入表头（如果文件不存在）
            if not file_exists:
                writer.writerow(['物品名称', '物品分类', '购买价格', '出售价格', '本人购买价格', '本人售出价格', '低买低卖溢价', '利润率', '时间戳', '出价数量', '上架数量', '稀有度'])
            
            # 获取当前时间
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 写入数据行
            writer.writerow([
                item_name, 
                category_name, 
                buying_price_str, 
                selling_price_str,
                own_buying_price if own_buying_price else '',
                own_selling_price if own_selling_price else '',
                spread,
                profit_rate,  # 添加利润率列
                timestamp,
                bid_count,
                listing_count,
                rarity
            ])
        
        print(f"价格数据已保存到报价追踪文件: {BID_TRACKER_FILE}")
        
        # 如果有GUI回调，通知数据已更新
        if tracking_gui_callback:
            tracking_gui_callback('data_updated', {
                'item_name': item_name,
                'category': category_name,
                'timestamp': timestamp
            })
        
        return True
    except Exception as e:
        print(f"保存报价追踪数据时出错: {str(e)}")
        return False

def process_tracked_items_gui_loop():
    """GUI控制的循环追踪模式 - 直接遍历物品，不需要打开界面"""
    global price_executor, is_tracking_active
    
    # 初始化价格识别线程池
    price_executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_RECOGNITION_WORKERS)
    
    # 从JSON购物清单加载正在购买的物品
    shopping_items = get_items_from_shopping_list()
    if not shopping_items:
        print("购物清单中没有正在购买的物品，请先添加物品")
        if tracking_gui_callback:
            tracking_gui_callback('error', {
                'message': '购物清单中没有正在购买的物品',
                'reason': '请先添加物品到购物清单'
            })
        return
    
    print(f"开始GUI循环追踪模式，共 {len(shopping_items)} 个物品")
    
    # 通知GUI开始追踪
    if tracking_gui_callback:
        tracking_gui_callback('tracking_started', {
            'total_items': len(shopping_items),
            'items': shopping_items
        })
    
    # 设置追踪状态为活跃
    is_tracking_active = True
    cycle_count = 0
    
    # 循环追踪
    while is_tracking_active:
        cycle_count += 1
        print(f"\n======== 开始第 {cycle_count} 轮追踪 ========")
        
        # 通知GUI开始新一轮
        if tracking_gui_callback:
            tracking_gui_callback('cycle_started', {
                'cycle': cycle_count,
                'total_items': len(shopping_items)
            })
        
        # 遍历购物清单中的物品
        for idx, item in enumerate(shopping_items):
            # 检查是否需要停止
            if not is_tracking_active:
                print("追踪已被停止")
                break
                
            item_name = item['物品名称']
            item_category = item['物品分类']
            
            print(f"\n处理物品 [{idx+1}/{len(shopping_items)}]: {item_name} ({item_category})")
            
            # 通知GUI当前处理的物品
            if tracking_gui_callback:
                tracking_gui_callback('processing_item', {
                    'cycle': cycle_count,
                    'item_index': idx + 1,
                    'total_items': len(shopping_items),
                    'item_name': item_name,
                    'item_category': item_category
                })
            
            # 查找并点击物品
            if find_and_click_item(item_name, item_category):
                # 点击后等待充分的时间以确保界面已切换
                print("等待界面加载...")
                time.sleep(2.0)  # 等待2秒确保界面完全加载
                                            
                # 额外等待界面完全稳定
                print(f"等待界面完全稳定 {SCREENSHOT_DELAY} 秒...")
                time.sleep(SCREENSHOT_DELAY)
                
                # 获取物品的英文键名用于截图命名
                item_key = get_item_key_from_name(item_name)
                if not item_key:
                    item_key = "unknown_item"  # 如果找不到键名，使用默认名称
                
                # 使用take_stable_screenshot获取截图，学习ModernWarshipMarket.py的命名方式
                screenshot_path = take_stable_screenshot(f"bid_item_detail_{item_key}")
                
                if screenshot_path:
                    print(f"已保存物品详情页截图: {screenshot_path}")
                    
                    # 启动价格识别，启用本人价格检测
                    if price_executor is not None:
                        print(f"提交价格识别任务: {item_name}")
                        price_executor.submit(
                            process_price_recognition, 
                            screenshot_path, 
                            item_name, 
                            item_category,
                            True  # 启用本人价格检测
                        )
                else:
                    print("无法获取物品详情页截图")
                
                # 执行第一次返回
                print("执行第一次返回操作")
                mwm.go_back()
                time.sleep(1.5)  # 等待1.5秒
                
                # 执行第二次返回
                print("执行第二次返回操作")
                mwm.go_back()
                time.sleep(1.5)  # 再等待1.5秒确保返回到列表界面
                
                print(f"已完成物品 '{item_name}' 的处理")
            else:
                print(f"无法找到并点击物品 '{item_name}'")
                if tracking_gui_callback:
                    tracking_gui_callback('item_not_found', {
                        'item_name': item_name,
                        'item_category': item_category
                    })
        
        # 完成一轮追踪
        print(f"======== 完成第 {cycle_count} 轮追踪 ========")
        
        # 通知GUI一轮完成
        if tracking_gui_callback:
            tracking_gui_callback('cycle_completed', {
                'cycle': cycle_count,
                'total_items': len(shopping_items)
            })
        
        # 如果还要继续循环，等待一段时间
        if is_tracking_active:
            wait_time = 10  # 每轮之间等待10秒
            print(f"等待 {wait_time} 秒后开始下一轮追踪...")
            
            # 分段等待，以便及时响应停止命令
            for i in range(wait_time):
                if not is_tracking_active:
                    break
                time.sleep(1)
    
    # 追踪结束，等待所有价格识别任务完成
    if price_executor:
        print("等待所有价格识别任务完成...")
        price_executor.shutdown(wait=True)
        print("所有价格识别任务已完成")
    
    # 通知GUI追踪结束
    if tracking_gui_callback:
        tracking_gui_callback('tracking_stopped', {
            'total_cycles': cycle_count,
            'reason': '用户停止' if not is_tracking_active else '完成'
        })
    
    print("GUI循环追踪模式已结束")

def start_gui_tracking(gui_callback=None):
    """启动GUI控制的追踪模式"""
    global tracking_gui_callback
    tracking_gui_callback = gui_callback
    
    # 在新线程中启动追踪，避免阻塞GUI
    import threading
    tracking_thread = threading.Thread(target=process_tracked_items_gui_loop, daemon=True)
    tracking_thread.start()
    return tracking_thread

def stop_gui_tracking():
    """停止GUI控制的追踪模式"""
    global is_tracking_active
    is_tracking_active = False
    print("正在停止追踪...")

def load_shopping_list():
    """加载购物清单JSON文件"""
    if os.path.exists(SHOPPING_LIST_FILE):
        try:
            with open(SHOPPING_LIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载购物清单文件失败: {str(e)}")
            return create_default_shopping_list()
    else:
        return create_default_shopping_list()

def create_default_shopping_list():
    """创建默认的购物清单结构"""
    return {
        "标的清单": [],
        "正在购买": [],
        "正在售出": []
        # 正在售出字段的结构示例：
        # "正在售出": [
        #     {
        #         "物品名称": "物品名称",
        #         "物品分类": "物品分类",
        #         "进货价": 12345,  # 数字格式的进货价
        #         "添加时间": "2025-06-27 13:47:03"
        #     }
        # ]
        # 
        # 报价追踪CSV文件结构：
        # 物品名称,物品分类,购买价格,出售价格,本人购买价格,本人售出价格,低买低卖溢价,利润率,时间戳,出价数量,上架数量,稀有度
    }

def save_shopping_list(shopping_list):
    """保存购物清单到JSON文件"""
    try:
        with open(SHOPPING_LIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(shopping_list, f, ensure_ascii=False, indent=2)
        print(f"购物清单已保存到: {SHOPPING_LIST_FILE}")
        return True
    except Exception as e:
        print(f"保存购物清单失败: {str(e)}")
        return False

def add_item_to_shopping_list(item_name, item_category):
    """将物品添加到购物清单的正在购买类别"""
    shopping_list = load_shopping_list()
    
    # 检查是否已存在
    for item in shopping_list["正在购买"]:
        if item["物品名称"] == item_name and item["物品分类"] == item_category:
            print(f"物品 '{item_name}' 已在正在购买清单中")
            return shopping_list
    
    # 添加新物品
    new_item = {
        "物品名称": item_name,
        "物品分类": item_category,
        "添加时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    shopping_list["正在购买"].append(new_item)
    save_shopping_list(shopping_list)
    print(f"已将 '{item_name}' 添加到正在购买清单")
    return shopping_list

def get_items_from_shopping_list():
    """从购物清单中获取正在购买的物品列表"""
    shopping_list = load_shopping_list()
    return shopping_list.get("正在购买", [])

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='报价追踪工具')
    parser.add_argument('--add', action='store_true', help='添加物品到追踪列表')
    parser.add_argument('--track', action='store_true', help='开始追踪物品价格')
    parser.add_argument('--device', help='设置设备ID')
    return parser.parse_args()

def main():
    """主函数"""
    global price_executor
    
    print("\n" + "="*50)
    print("     现代战舰市场报价追踪工具")
    print("="*50 + "\n")
    
    # 根据运行模式选择
    if RUN_MODE == 0:
        # GUI模式
        print("启动GUI模式...")
        
        if not AUTOTRADE_GUI_AVAILABLE:
            print("错误：AutoTradeGUI模块不可用，无法启动GUI模式")
            print("请检查AutoTradeGUI.py文件是否存在且可正常导入")
            return
        
        # 设置设备ID
        if not rsh.deviceID:
            try:
                devices = rsh.ADBHelper.getDevicesList()
                if devices:
                    rsh.deviceID = devices[0]
                    print(f"已自动设置设备ID为: {rsh.deviceID}")
                else:
                    print("警告：未检测到连接的安卓设备，请检查ADB连接")
                    print("可以在GUI界面中手动设置设备ID")
            except Exception as e:
                print(f"检测设备时出错: {str(e)}")
        
        # 启动GUI - 只有在直接运行BidTracker时才启动
        # 如果是被AutoTradeGUI导入的，则不启动
        if __name__ == "__main__":
            try:
                AutoTradeGUI.main()
            except Exception as e:
                print(f"启动GUI时出错: {str(e)}")
        else:
            print("BidTracker已作为模块导入，GUI将由AutoTradeGUI启动")
        
    else:
        # 命令行模式 (已废弃，仅基本兼容)
        print("命令行模式已废弃，建议使用GUI模式")
        print("如需使用，请将RUN_MODE设置为0以启动GUI模式")
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 设置设备ID
    if args.device:
        rsh.deviceID = args.device
    elif not rsh.deviceID:
        try:
            devices = rsh.ADBHelper.getDevicesList()
            if devices:
                rsh.deviceID = devices[0]
                print(f"已自动设置设备ID为: {rsh.deviceID}")
            else:
                print("错误：未检测到连接的安卓设备，请检查ADB连接")
                return
        except Exception as e:
            print(f"设置设备ID时出错: {str(e)}")
            return
    
    # 检查目录结构
    if not os.path.exists(TEMPLATE_DIR):
        print(f"模板目录不存在: {TEMPLATE_DIR}")
        return
    
    if args.track:
        # 开始追踪物品价格
        process_tracked_items_gui_loop()
    else:
        print("命令行模式功能有限，建议使用GUI模式")
        print("使用 --track 参数开始追踪")
    
    # 确保线程池被关闭
    if price_executor:
        price_executor.shutdown()
    
    print("\n" + "="*50)
    print("     报价追踪工具已退出")
    print("="*50 + "\n")

if __name__ == "__main__":
    main() 