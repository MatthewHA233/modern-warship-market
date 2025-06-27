import RaphaelScriptHelper as rsh
import time
import os
import csv
import sys
import glob
import cv2
from datetime import datetime
import SimpleScroll as scroll
import threading
import concurrent.futures
import MarketPriceRecognizer as mpr
import json
import argparse
import numpy as np

# 起始位置设置（可以修改这里以从特定位置开始）
# 从0开始计数，例如：
# START_CATEGORY_INDEX = 0 表示从第一个分类开始
# START_ITEM_INDEX = 0 表示从该分类的第一个物品开始
# 示例：设置 START_CATEGORY_INDEX = 1, START_ITEM_INDEX = 10 
# 将从第二个分类的第11个物品开始处理
START_CATEGORY_INDEX = 0  # 起始分类索引（0=第一个分类）
START_ITEM_INDEX = 0     # 起始物品索引（0=该分类的第一个物品）

# 预设物品文件路径（默认为None，表示处理所有物品）
PRESET_FILE = None

# 导入分类和物品映射
sys.path.append("./templates/modern_warship/")
try:
    from category_mapping import get_category_name, get_item_name, CATEGORY_DICT, ITEM_DICT
except ImportError:
    print("无法导入分类映射模块，请确保category_mapping.py文件存在")
    
    # 如果导入失败，提供默认的映射函数和字典
    CATEGORY_DICT = {}
    ITEM_DICT = {}
    
    def get_category_name(category_key):
        return category_key
    
    def get_item_name(item_key):
        return item_key

# 设置设备类型和ID
rsh.deviceType = 1  # 安卓设备
rsh.deviceID = ""   # 请在此填写您的设备ID，可通过adb devices命令获取

# 设置脚本配置参数
TEMPLATE_DIR = "./templates/modern_warship/"  # 存放模板图片的目录
MARKET_ITEMS_DIR = f"{TEMPLATE_DIR}market_items/"  # 市场物品图片目录
MARKET_ICONS_DIR = f"{TEMPLATE_DIR}market_icons/"  # 市场分类图标目录
OUTPUT_DIR = "./market_data/"  # 输出数据目录
OUTPUT_FILE = f"{OUTPUT_DIR}market_access_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"  # 输出文件名
SCREENSHOT_DIR = "./cache/market_screenshots/"  # 截图保存目录
MAX_RETRY = 3  # 操作失败时的最大重试次数
DELAY_BETWEEN_ITEMS = 0.1  # 处理物品之间的延迟时间(秒)
DEFAULT_DELAY = 0.1  # 默认延时时间(秒)
BACK_DELAY = 0.3  # 从物品详情页返回时的更快延迟(秒)
SCROLL_AFTER_DELAY = 0.1  # 滑动后等待时间
SCREENSHOT_DELAY = 0.5  # 截图前的等待时间(秒)，确保界面完全加载
MAX_COMPENSATION_ATTEMPTS = 3  # 物品识别失败后的最大补偿移动尝试次数

# 价格识别相关设置
ENABLE_PRICE_RECOGNITION = True  # 是否启用价格识别
MAX_RECOGNITION_WORKERS = 4     # 最大同时运行的价格识别线程数
KEEP_TEMP_IMAGES = False        # 是否保留临时价格图像
# 按小时生成价格数据文件
PRICE_DATA_FILE = f"./market_data/price_data_{datetime.now().strftime('%Y%m%d_%H')}.csv"

# 创建线程池
price_executor = None  # 将在main函数中初始化

# 确保所需目录存在
for directory in [TEMPLATE_DIR, OUTPUT_DIR, SCREENSHOT_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"已创建目录：{directory}")

# 检查模板图片是否存在
required_templates = [
    "market_icon.png",  # 市场图标
    "back_button.png",  # 返回按钮
]

missing_templates = []
for template in required_templates:
    if not os.path.exists(f"{TEMPLATE_DIR}{template}"):
        missing_templates.append(template)

if missing_templates:
    print("警告：以下基础模板图片未找到，脚本可能无法正常工作：")
    for template in missing_templates:
        print(f"  - {template}")
    print(f"请查阅 {TEMPLATE_DIR}README.md 获取如何准备模板图片的说明")

def safe_find_pic(template_path, **kwargs):
    """安全版本的find_pic，不会因为无法识别而报错"""
    try:
        return rsh.find_pic(template_path, **kwargs)
    except Exception as e:
        print(f"识别图片失败，错误: {str(e)}")
        return None

def retry_operation(operation_func, max_retries=MAX_RETRY, *args, **kwargs):
    """带重试机制的操作函数"""
    for attempt in range(max_retries):
        try:
            result = operation_func(*args, **kwargs)
            if result:
                return result
        except Exception as e:
            print(f"操作执行出错: {str(e)}")
            result = False
        
        if attempt < max_retries - 1:
            retry_delay = 0.2 + attempt * 0.2  # 递增的延迟
            print(f"操作失败，{retry_delay:.1f}秒后进行第{attempt+2}次尝试...")
            time.sleep(retry_delay)
    
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
            
            # 检查是否有loading图标
            if not check_loading_indicator(screenshot_path):
                print(f"获取到稳定截图: {screenshot_path}")
                return screenshot_path
            
            print(f"截图还在加载中，将重试...")
            # 删除不稳定的截图
            try:
                os.remove(screenshot_path)
            except:
                pass
            
            # 额外等待一段时间再尝试
            time.sleep(0.05)
        
        print(f"达到最大尝试次数({max_attempts})，使用最后一次截图")
        return screenshot_path
    except Exception as e:
        print(f"获取稳定截图失败: {str(e)}")
        return None

def center_click(template_path):
    """使用中心点击模式，点击图标的中心位置"""
    try:
        # 使用返回中心位置的方式查找图标
        center_pos = safe_find_pic(template_path, returnCenter=True)
        if center_pos:
            print(f"找到图标，中心位置：{center_pos}")
            rsh.touch(center_pos)
            return True
        else:
            print(f"未找到图标: {template_path}")
            return False
    except Exception as e:
        print(f"点击图标时出错: {str(e)}")
        return False

def click_point(pos):
    """点击屏幕上的指定坐标"""
    try:
        print(f"点击坐标: {pos}")
        rsh.touch(pos)
        return True
    except Exception as e:
        print(f"点击坐标时出错: {str(e)}")
        return False

def open_market():
    """打开游戏市场"""
    try:
        print("正在尝试打开市场...")
        if retry_operation(center_click, 3, f"{TEMPLATE_DIR}market_icon.png"):
            print("成功打开市场界面")
            rsh.delay(DEFAULT_DELAY)
            return True
        else:
            print("无法找到市场图标，尝试继续执行")
            return True  # 即使找不到市场图标也继续执行
    except Exception as e:
        print(f"打开市场时出错: {str(e)}，继续执行")
        return True  # 出错也继续执行

def go_back():
    """返回上一级界面"""
    try:
        print("正在返回上一级界面...")
        # 直接使用Android系统返回键，不再尝试图像识别
        try:
            os.system(f"adb -s {rsh.deviceID} shell input keyevent 4")
            rsh.delay(BACK_DELAY)
        except Exception as e:
            print(f"使用Android返回键出错: {str(e)}，继续执行")
            
            # 图像识别作为备选方案
            if retry_operation(center_click, 2, f"{TEMPLATE_DIR}back_button.png"):
                print("已点击返回按钮")
                rsh.delay(BACK_DELAY)
        return True
    except Exception as e:
        print(f"返回上一级界面时出错: {str(e)}，继续执行")
        return True

def get_item_templates(category_name):
    """获取特定分类下的所有物品模板"""
    try:
        item_templates = []
        category_dir = f"{MARKET_ITEMS_DIR}{category_name}/"
        
        if not os.path.exists(category_dir):
            print(f"警告：分类目录 {category_name} 不存在")
            return []
            
        # 获取该分类下的所有物品图片
        item_files = {}
        for item_path in glob.glob(f"{category_dir}*.png"):
            item_filename = os.path.basename(item_path)
            item_name = os.path.splitext(item_filename)[0]
            item_files[item_name] = item_path
        
        # 先处理在ITEM_DICT中定义了的物品，按照定义顺序
        for item_name in ITEM_DICT.keys():
            if item_name in item_files:
                item_templates.append({
                    'category': category_name,
                    'name': item_name,
                    'path': item_files[item_name],
                    'display_category': get_category_name(category_name),
                    'display_name': get_item_name(item_name)
                })
                # 从文件列表中移除已处理的项
                del item_files[item_name]
        
        # 处理剩余未在ITEM_DICT中定义的物品
        for item_name, item_path in item_files.items():
            item_templates.append({
                'category': category_name,
                'name': item_name,
                'path': item_path,
                'display_category': get_category_name(category_name),
                'display_name': get_item_name(item_name)
            })
        
        return item_templates
    except Exception as e:
        print(f"获取物品模板时出错: {str(e)}")
        return []

def access_item(item_info, item_number):
    """访问特定物品的详情页面，item_number是当前物品在分类中的序号(从1开始)"""
    try:
        print(f"正在访问物品: {item_info['display_name']} (分类: {item_info['display_category']}, 序号: {item_number})")
        
        # 获取图像尺寸用于计算中心点
        try:
            img = cv2.imread(item_info['path'])
            if img is not None:
                h, w = img.shape[:2]
                
                # 计算该物品的正常滑动次数
                normal_scroll_times = calculate_scroll_times(item_number)
                
                # 尝试识别物品，如果失败则使用补偿移动重试
                left_top = None
                compensation_attempts = 0
                max_compensation_cycles = 3  # 最多进行3个完整的补偿循环(每个循环包含4次尝试)
                
                while not left_top and compensation_attempts < MAX_COMPENSATION_ATTEMPTS * max_compensation_cycles:
                    # 使用safe_find_pic查找图标并返回左上角坐标
                    left_top = safe_find_pic(item_info['path'])
                    
                    if left_top:
                        # 成功识别，跳出循环
                        break
                    
                    # 识别失败，执行补偿移动
                    if compensation_attempts < MAX_COMPENSATION_ATTEMPTS * max_compensation_cycles:
                        compensation_attempts += 1
                        print(f"物品识别失败，执行补偿移动重试 ({compensation_attempts}/{MAX_COMPENSATION_ATTEMPTS * max_compensation_cycles})...")
                        # 传递normal_scroll_times给compensation_move
                        scroll.compensation_move(1, SCROLL_AFTER_DELAY, 
                                               attempt_number=compensation_attempts,
                                               normal_scroll_times=normal_scroll_times)
                    else:
                        print(f"物品识别失败，已达到最大补偿移动尝试次数 ({MAX_COMPENSATION_ATTEMPTS * max_compensation_cycles})")
                
                if left_top:
                    # 计算中心点位置
                    try:
                        x, y = left_top
                        center_x = x + w // 2
                        center_y = y + h // 2
                        center_pos = (center_x, center_y)
                        
                        print(f"找到物品图标，中心位置：{center_pos}" + (f"（补偿移动后识别成功）" if compensation_attempts > 0 else ""))
                        rsh.touch(center_pos)
                        
                        # 点击物品后等待界面初始加载
                        print(f"等待物品界面初始加载 {DEFAULT_DELAY} 秒...")
                        rsh.delay(DEFAULT_DELAY)
                        
                        # 额外等待界面完全加载稳定，确保截图时界面不再模糊
                        print(f"等待界面完全稳定 {SCREENSHOT_DELAY} 秒...")
                        time.sleep(SCREENSHOT_DELAY)
                        
                        # 获取稳定的物品详情页截图
                        screenshot_path = take_stable_screenshot(f"item_detail_{item_info['name']}")
                        if screenshot_path:
                            print(f"已保存物品详情页截图: {screenshot_path}")
                        else:
                            print("无法获取稳定的物品详情页截图")
                            screenshot_path = take_screenshot(f"item_detail_{item_info['name']}")  # 退回到普通截图
                        
                        # 检查loading图标
                        if check_loading_indicator(screenshot_path):
                            print("检测到loading图标，需要重新截图")
                            return {
                                'success': False,
                                'screenshot': None
                            }
                        
                        # 启动非阻塞价格识别
                        if ENABLE_PRICE_RECOGNITION and price_executor is not None:
                            # 提交价格识别任务到线程池
                            price_executor.submit(
                                process_item_price, 
                                screenshot_path, 
                                item_info['display_name'], 
                                item_info['display_category'],
                                not KEEP_TEMP_IMAGES  # 是否在处理后删除临时图像
                            )
                        
                        # 返回到市场列表
                        go_back()
                        
                        return {
                            'success': True,
                            'screenshot': screenshot_path
                        }
                    except Exception as e:
                        print(f"处理图标中心点时出错: {str(e)}")
            
            # 如果上面的方法失败，回退到使用find_pic_touch方法
            try:
                # 再次尝试使用补偿移动
                compensation_attempts = 0
                result = False
                
                while not result and compensation_attempts <= MAX_COMPENSATION_ATTEMPTS:
                    result = retry_operation(rsh.find_pic_touch, 2, item_info['path'])
                    
                    if result:
                        # 成功识别并点击
                        break
                    
                    # 识别失败，执行补偿移动
                    if compensation_attempts < MAX_COMPENSATION_ATTEMPTS:
                        compensation_attempts += 1
                        print(f"物品识别失败(使用默认方法)，执行补偿移动重试 ({compensation_attempts}/{MAX_COMPENSATION_ATTEMPTS})...")
                        scroll.compensation_move(1, SCROLL_AFTER_DELAY, attempt_number=compensation_attempts)
                        rsh.delay(DEFAULT_DELAY)  # 等待画面稳定
                    else:
                        print(f"物品识别失败(使用默认方法)，已达到最大补偿移动尝试次数 ({MAX_COMPENSATION_ATTEMPTS})")
                
                if result:
                    print(f"成功点击物品图标（使用默认方法）" + (f"（补偿移动后识别成功）" if compensation_attempts > 0 else ""))
                    
                    # 点击物品后等待界面初始加载
                    print(f"等待物品界面初始加载 {DEFAULT_DELAY} 秒...")
                    rsh.delay(DEFAULT_DELAY)
                    
                    # 额外等待界面完全加载稳定，确保截图时界面不再模糊
                    print(f"等待界面完全稳定 {SCREENSHOT_DELAY} 秒...")
                    time.sleep(SCREENSHOT_DELAY)
                    
                    # 检查loading图标
                    if check_loading_indicator(f"{SCREENSHOT_DIR}item_detail_{item_info['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"):
                        print("检测到loading图标，需要重新截图")
                        return {
                            'success': False,
                            'screenshot': None
                        }
                    
                    # 获取稳定的物品详情页截图
                    screenshot_path = take_stable_screenshot(f"item_detail_{item_info['name']}")
                    if screenshot_path:
                        print(f"已保存物品详情页截图: {screenshot_path}")
                    else:
                        print("无法获取稳定的物品详情页截图")
                        screenshot_path = take_screenshot(f"item_detail_{item_info['name']}")  # 退回到普通截图
                    
                    # 启动非阻塞价格识别
                    if ENABLE_PRICE_RECOGNITION and price_executor is not None:
                        # 提交价格识别任务到线程池
                        price_executor.submit(
                            process_item_price, 
                            screenshot_path, 
                            item_info['display_name'], 
                            item_info['display_category'],
                            not KEEP_TEMP_IMAGES  # 是否在处理后删除临时图像
                        )
                    
                    # 返回到市场列表
                    go_back()
                    
                    return {
                        'success': True,
                        'screenshot': screenshot_path
                    }
            except Exception as e:
                print(f"使用默认方法点击图标时出错: {str(e)}")
        except Exception as e:
            print(f"读取图片时出错: {str(e)}")
        
        print(f"未找到物品图标: {item_info['path']}")
        return {
            'success': False,
            'screenshot': None
        }
    except Exception as e:
        print(f"访问物品时出错: {str(e)}")
        return {
            'success': False,
            'screenshot': None
        }

def parse_arguments():
    parser = argparse.ArgumentParser(description='现代战舰市场数据采集')
    parser.add_argument('--start_category', type=int, default=START_CATEGORY_INDEX, help='起始分类索引')
    parser.add_argument('--start_item', type=int, default=START_ITEM_INDEX, help='起始物品索引')
    parser.add_argument('--preset', type=str, default=None, help='预设文件路径')
    parser.add_argument('--output', type=str, default=None, help='自定义输出CSV文件名（不含扩展名）')
    parser.add_argument('--price_output', type=str, default=None, help='自定义价格数据CSV文件名（不含扩展名）')
    return parser.parse_args()

def generate_output_filename(custom_name=None, file_type="access"):
    """
    生成输出文件名
    
    参数:
        custom_name: 自定义文件名（不含扩展名）
        file_type: 文件类型，"access"表示访问日志，"price"表示价格数据
    
    返回:
        完整的文件路径
    """
    if custom_name:
        # 使用自定义文件名
        if file_type == "access":
            return f"{OUTPUT_DIR}{custom_name}.csv"
        elif file_type == "price":
            return f"./market_data/{custom_name}.csv"
    else:
        # 使用默认文件名
        if file_type == "access":
            return f"{OUTPUT_DIR}market_access_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        elif file_type == "price":
            return f"./market_data/price_data_{datetime.now().strftime('%Y%m%d_%H')}.csv"
    
    return None

def save_results(results, output_file=None):
    """保存访问记录到CSV文件"""
    try:
        if not results:
            print("没有数据需要保存")
            return
        
        # 使用指定的输出文件或默认文件
        file_path = output_file or OUTPUT_FILE
        
        print(f"正在保存结果到文件：{file_path}")
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['物品分类', '物品名称', '访问结果', '截图路径', '时间戳'])
            for item in results:
                writer.writerow([
                    item['category_display'],
                    item['name_display'],
                    '成功' if item['success'] else '失败',
                    item['screenshot'] or '无',
                    item['timestamp']
                ])
        print(f"结果已保存到文件：{file_path}")
    except Exception as e:
        print(f"保存结果时出错: {str(e)}")

def print_progress(current, total=None):
    """打印进度信息"""
    try:
        if total:
            print(f"进度: [{current}/{total}] {(current/total*100):.1f}%")
        else:
            print(f"已处理: {current}个物品")
    except Exception as e:
        print(f"打印进度时出错: {str(e)}")

def click_category_icon(category_name):
    """点击分类图标进入该分类"""
    try:
        icon_path = f"{MARKET_ICONS_DIR}{category_name}_icon.png"
        
        if not os.path.exists(icon_path):
            print(f"错误: 未找到分类图标 {icon_path}")
            return False
        
        print(f"点击分类 [{get_category_name(category_name)}] 图标")
        if retry_operation(center_click, 3, icon_path):
            print(f"成功进入 {get_category_name(category_name)} 分类")
            rsh.delay(DEFAULT_DELAY)
            return True
        else:
            print(f"无法点击分类图标: {category_name}，继续执行")
            return True  # 即使点击失败也继续执行
    except Exception as e:
        print(f"点击分类图标时出错: {str(e)}，继续执行")
        return True  # 即使出错也继续执行

def calculate_scroll_times(item_number):
    """计算物品需要滑动的次数"""
    try:
        if item_number <= 10:
            return 0
        elif item_number <= 20:
            return 1
        elif item_number <= 30:
            return 2
        else:
            return (item_number - 1) // 10
    except Exception as e:
        print(f"计算滑动次数时出错: {str(e)}")
        return 0

def wait_after_scroll():
    """滑动后的额外等待，确保滑动完全稳定后再继续操作"""
    print(f"等待滑动稳定 {SCROLL_AFTER_DELAY} 秒...")
    time.sleep(SCROLL_AFTER_DELAY)

def process_item_price(screenshot_path, item_name, category_name, delete_after=True):
    """
    处理物品价格识别（用于线程池）
    
    参数:
        screenshot_path: 物品详情页截图路径
        item_name: 物品名称
        category_name: 物品分类名称
        delete_after: 处理后是否删除临时图像文件
    """
    try:
        print(f"[价格识别] 开始处理 {item_name} ({category_name})")
        
        # 使用全局的价格数据文件路径
        global PRICE_DATA_FILE
        mpr.PRICE_DATA_FILE = PRICE_DATA_FILE
        
        # 设置不保存临时图像
        if not KEEP_TEMP_IMAGES:
            # 临时改变输出目录到临时文件夹
            original_output_dir = mpr.OUTPUT_DIR
            mpr.OUTPUT_DIR = "./cache/temp_price_images/"
            
            # 确保临时目录存在
            if not os.path.exists(mpr.OUTPUT_DIR):
                os.makedirs(mpr.OUTPUT_DIR)
        
        # 执行价格识别
        price_img_paths, markup_img_path, price_data = mpr.process_screenshot(
            screenshot_path, 
            item_name, 
            category_name
        )
        
        # 恢复原始输出目录
        if not KEEP_TEMP_IMAGES:
            mpr.OUTPUT_DIR = original_output_dir
        
        # 打印识别结果
        if price_data:
            print(f"[价格识别] {item_name} 价格数据识别成功:")
            for label, price in price_data.items():
                label_display = "购买价格" if "buying" in label else "出售价格" if "selling" in label else label
                print(f"  - {label_display}: {price}")
        else:
            print(f"[价格识别] {item_name} 未识别到价格数据")
        
        # 删除临时文件
        if delete_after:
            # 删除价格区域图像
            for path in price_img_paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    print(f"[价格识别] 删除临时文件失败: {path}, 错误: {str(e)}")
            
            # 删除带标记的原图
            if markup_img_path and os.path.exists(markup_img_path):
                try:
                    os.remove(markup_img_path)
                except Exception as e:
                    print(f"[价格识别] 删除临时文件失败: {markup_img_path}, 错误: {str(e)}")
        
        return True
    except Exception as e:
        print(f"[价格识别] 处理出错: {str(e)}")
        return False

def load_preset_items():
    """加载预设物品列表"""
    global PRESET_FILE
    
    if not PRESET_FILE or not os.path.exists(PRESET_FILE):
        print("未指定预设物品文件或文件不存在，将处理所有物品")
        return None
    
    try:
        print(f"正在加载预设物品文件: {PRESET_FILE}")
        with open(PRESET_FILE, 'r', encoding='utf-8') as f:
            preset_data = json.load(f)
        
        if not preset_data or 'items' not in preset_data or not preset_data['items']:
            print("预设文件中未找到有效物品数据")
            return None
        
        preset_items = preset_data['items']
        print(f"已加载 {len(preset_items)} 个预设物品")
        return preset_items
    except Exception as e:
        print(f"加载预设物品文件时出错: {str(e)}")
        return None

def main():
    """主函数"""
    try:
        global price_executor, OUTPUT_FILE, PRICE_DATA_FILE
        
        # 解析命令行参数
        args = parse_arguments()
        
        # 更新起始位置设置
        global START_CATEGORY_INDEX, START_ITEM_INDEX, PRESET_FILE
        START_CATEGORY_INDEX = args.start_category
        START_ITEM_INDEX = args.start_item
        PRESET_FILE = args.preset
        
        # 生成输出文件名
        OUTPUT_FILE = generate_output_filename(args.output, "access")
        custom_price_file = generate_output_filename(args.price_output, "price")
        if custom_price_file:
            PRICE_DATA_FILE = custom_price_file
        
        print("\n" + "="*50)
        print("现代战舰市场物品访问脚本 - 按分类遍历")
        print("="*50 + "\n")
        
        print("请确保:")
        print("1. 已将所需模板图片放置在模板目录中")
        print("2. 已将物品图片放置在对应分类目录下")
        print("3. 已将分类图标放置在market_icons目录下")
        print("4. 游戏已运行并位于主界面")
        print("5. 已在脚本开头设置正确的设备ID")
        print("\n游戏和脚本的分辨率必须匹配，否则识别将失败")
        
        # 打印文件名信息
        print(f"\n输出文件设置:")
        print(f"访问日志文件: {OUTPUT_FILE}")
        if ENABLE_PRICE_RECOGNITION:
            print(f"价格数据文件: {PRICE_DATA_FILE}")
        
        # 加载预设物品
        preset_items = load_preset_items()
        
        # 打印起始位置信息
        if START_CATEGORY_INDEX > 0 or START_ITEM_INDEX > 0:
            print(f"\n注意: 脚本将从第 {START_CATEGORY_INDEX+1} 个分类的第 {START_ITEM_INDEX+1} 个物品开始处理")
        
        if preset_items:
            print(f"\n注意: 脚本将只处理预设的 {len(preset_items)} 个物品")
        
        # 检查设备ID是否已设置
        if not rsh.deviceID:
            try:
                devices = rsh.ADBHelper.getDevicesList()
                if devices:
                    rsh.deviceID = devices[0]
                    print(f"已自动设置设备ID为: {rsh.deviceID}")
                    # 设置滚动工具的设备ID
                    scroll.set_device_id(rsh.deviceID)
                else:
                    print("错误：未检测到连接的安卓设备，请检查ADB连接")
                    return
            except Exception as e:
                print(f"设置设备ID时出错: {str(e)}")
                return
        else:
            # 设置滚动工具的设备ID
            try:
                scroll.set_device_id(rsh.deviceID)
            except Exception as e:
                print(f"设置滚动工具的设备ID时出错: {str(e)}")
        
        # 准备结果记录
        results = []
        total_items_processed = 0
        
        # 打开市场
        open_market()  # 即使打开失败也继续执行
        
        # 首先点击固定坐标(220, 163)
        try:
            print("点击市场初始位置...")
            click_point((220, 163))
            rsh.delay(DEFAULT_DELAY)
        except Exception as e:
            print(f"点击市场初始位置时出错: {str(e)}，继续执行")
        
        start_time = time.time()
        
        # 初始化价格识别线程池
        if ENABLE_PRICE_RECOGNITION:
            print("初始化价格识别线程池...")
            price_executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_RECOGNITION_WORKERS)
        
        # 转换字典为列表以支持索引访问
        category_items = list(CATEGORY_DICT.items())
        
        # 外层循环：按照CATEGORY_DICT的顺序遍历分类
        need_scroll_category = False
        for category_index, (category_name, category_display) in enumerate(category_items):
            # 跳过起始分类索引之前的分类
            if category_index < START_CATEGORY_INDEX:
                print(f"跳过分类 [{category_index+1}/{len(category_items)}]: {category_display}")
                continue
                
            try:
                print(f"\n{'='*30}")
                print(f"开始处理分类 [{category_index+1}/{len(category_items)}]: {category_display}")
                print(f"{'='*30}")
                
                # 判断是否需要滑动分类栏
                if need_scroll_category:
                    try:
                        print("需要滑动分类栏以显示后续分类...")
                        scroll.category_down(1, SCROLL_AFTER_DELAY)  # 使用新的滑动后延迟参数
                        wait_after_scroll()  # 额外等待确保滑动完全稳定
                    except Exception as e:
                        print(f"滑动分类栏时出错: {str(e)}，继续执行")
                    need_scroll_category = False
                
                # 检查该分类是否是"对空武器"，如果是，下一个分类前需要滑动
                if category_name == "aa_weapons":
                    need_scroll_category = True
                
                # 点击分类图标
                click_category_icon(category_name)  # 即使点击失败也继续执行
                
                # 获取该分类下的所有物品
                item_templates = get_item_templates(category_name)
                if not item_templates:
                    print(f"分类 {category_display} 下未找到物品，跳过")
                    continue  # 如果没有物品，直接处理下一个分类，不需要返回
                
                print(f"分类 {category_display} 下找到 {len(item_templates)} 个物品")
                
                # 内层循环：遍历该分类下的所有物品
                for item_index, item in enumerate(item_templates):
                    # 如果是起始分类，则跳过起始物品索引之前的物品
                    if category_index == START_CATEGORY_INDEX and item_index < START_ITEM_INDEX:
                        print(f"跳过物品 {item_index+1}: {item['display_name']}")
                        continue
                        
                    try:
                        item_number = item_index + 1
                        total_items_processed += 1
                        
                        print(f"\n正在处理第 {item_number}/{len(item_templates)} 个物品: {item['display_name']}")
                        
                        # 如果有预设物品列表，检查当前物品是否在预设列表中
                        if preset_items and not is_item_in_preset(item['name'], item['category'], preset_items):
                            print(f"跳过非预设物品: {item['display_name']}")
                            continue
                        
                        # 为每个超过第10个的物品执行滑动
                        scroll_times = calculate_scroll_times(item_number)
                        if scroll_times > 0:
                            try:
                                # 直接执行所需次数的滑动
                                print(f"物品序号 {item_number} 需要向下滑动 {scroll_times} 次")
                                # 使用新的滑动后延迟，确保滑动完成后再继续
                                scroll.market_down(scroll_times, SCROLL_AFTER_DELAY)
                                wait_after_scroll()  # 额外等待确保滑动完全稳定
                            except Exception as e:
                                print(f"滑动列表时出错: {str(e)}，继续执行")
                        
                        # 访问物品
                        access_result = access_item(item, item_number)
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 记录结果
                        results.append({
                            'category': item['category'],
                            'category_display': item['display_category'],
                            'name': item['name'],
                            'name_display': item['display_name'],
                            'success': access_result['success'],
                            'screenshot': access_result['screenshot'],
                            'timestamp': timestamp
                        })
                        
                        print(f"访问结果: {'成功' if access_result['success'] else '失败'}")
                        print_progress(total_items_processed)
                        
                        # 每处理10个物品就保存一次结果，防止中途中断丢失数据
                        if total_items_processed % 10 == 0:
                            save_results(results)
                            print("已保存当前进度")
                        
                        # 添加延迟，避免操作过快
                        time.sleep(DELAY_BETWEEN_ITEMS)
                    except Exception as e:
                        print(f"处理物品时出错: {str(e)}，继续处理下一个物品")
                        continue
                
                # 该分类下的所有物品处理完毕，直接处理下一个分类，不需要返回
                print(f"分类 {category_display} 下的所有物品处理完毕")
                # 删除此处的go_back()调用，不需要返回上一级界面
            except Exception as e:
                print(f"处理分类 {category_display} 时出错: {str(e)}，继续处理下一个分类")
                continue
        
        # 所有分类和物品处理完毕
        # 等待所有价格识别任务完成
        if ENABLE_PRICE_RECOGNITION and price_executor is not None:
            print("等待所有价格识别任务完成...")
            price_executor.shutdown(wait=True)
            print("所有价格识别任务已完成")
        
        # 保存最终结果
        save_results(results)
        
        # 计算耗时
        elapsed_time = time.time() - start_time
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        print("\n" + "="*50)
        print(f"脚本执行完毕")
        print(f"共访问了 {len(results)} 个物品")
        print(f"总耗时: {int(hours)}小时 {int(minutes)}分钟 {seconds:.1f}秒")
        print(f"结果已保存至: {OUTPUT_FILE}")
        print("="*50 + "\n")
    except Exception as e:
        print(f"\n主函数发生错误: {str(e)}，但脚本继续运行")

def is_item_in_preset(item_name, item_category, preset_items):
    """
    检查物品是否在预设列表中，支持中英文名称比对
    
    item_name: 物品的英文代码名
    item_category: 物品分类的英文代码名
    preset_items: 预设物品列表（包含中文显示名称）
    """
    # 获取当前物品的中文显示名称
    display_name = get_item_name(item_name)
    display_category = get_category_name(item_category)
    
    # 首先尝试使用中文名称进行比对
    for preset_item in preset_items:
        # 检查中文名称是否匹配
        if preset_item['name'] == display_name and preset_item['category'] == display_category:
            return True
            
        # 后备方案：如果预设中保存的是英文代码名，则直接比对
        if preset_item['name'] == item_name and preset_item['category'] == item_category:
            return True
    
    return False

# 创建反向映射（中文名 -> 英文代码）
REVERSE_ITEM_DICT = {}
for eng_name, cn_name in ITEM_DICT.items():
    REVERSE_ITEM_DICT[cn_name] = eng_name

REVERSE_CATEGORY_DICT = {}
for eng_cat, cn_cat in CATEGORY_DICT.items():
    REVERSE_CATEGORY_DICT[cn_cat] = eng_cat

def get_code_by_display_name(display_name):
    """根据中文显示名获取英文代码名"""
    return REVERSE_ITEM_DICT.get(display_name, display_name)

def get_category_code_by_name(display_category):
    """根据中文分类名获取英文分类代码"""
    return REVERSE_CATEGORY_DICT.get(display_category, display_category)

def is_item_in_preset(item_name, item_category, preset_items):
    """检查物品是否在预设列表中"""
    display_name = get_item_name(item_name)  # 获取中文显示名
    display_category = get_category_name(item_category)  # 获取中文分类名
    
    for preset_item in preset_items:
        preset_display_name = preset_item['name']
        preset_display_category = preset_item['category']
        
        # 直接比对中文显示名和分类名
        if preset_display_name == display_name and preset_display_category == display_category:
            print(f"预设匹配成功: {display_name} ({display_category})")
            return True
    
    return False

def check_loading_indicator(image_path):
    """
    检查图像中是否处于加载状态
    
    参数:
        image_path: 截图路径
        
    返回:
        True: 存在loading状态（需要重新截图）
        False: 不存在loading状态
    """
    try:
        # 读取图像
        img = cv2.imread(image_path)
        if img is None:
            print("无法读取截图")
            return True
        
        # 使用模板匹配检测loading图标
        template_path = f"{TEMPLATE_DIR}loading.png"
        if os.path.exists(template_path):
            template = cv2.imread(template_path)
            if template is not None:
                # 提取目标区域 (1207, 627) 到 (1327, 668)
                roi = img[627:668, 1207:1327]
                
                # 调整尺寸
                if roi.shape[0] != template.shape[0] or roi.shape[1] != template.shape[1]:
                    template = cv2.resize(template, (roi.shape[1], roi.shape[0]))
                
                # 执行模板匹配
                result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                # 关键修改：直接打印小数点后2位，不使用格式化字符串
                print(f"loading图标匹配度: {float(max_val):.2f}")
                
                if float(max_val) >= 0.6:
                    return True
        
        # 检查灰色状态（避免使用直方图）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 计算80-180灰度值的像素数量（不使用直方图）
        mid_gray_mask = cv2.inRange(gray, 80, 180)
        mid_gray_pixels = cv2.countNonZero(mid_gray_mask)
        total_pixels = gray.size
        
        # 计算占比 - 关键修改：转换为Python类型
        gray_ratio = float(mid_gray_pixels) / float(total_pixels)
        print("灰色区域占比: %.2f" % gray_ratio)  # 使用%格式化而不是f-string
        
        # 60%以上是中灰色认为是加载状态
        if gray_ratio > 0.6:
            return True
            
        return False
    except Exception as e:
        print(f"检查loading状态时出错: {str(e)}")
        return True  # 出错时默认返回True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n脚本已被用户中断")
    except Exception as e:
        print(f"\n脚本发生错误: {str(e)}，但会继续执行")
        try:
            main()  # 即使出错也尝试重新执行
        except:
            print("再次执行仍然失败，脚本退出")
    finally:
        # 确保线程池关闭
        if 'price_executor' in globals() and price_executor is not None:
            price_executor.shutdown(wait=False)
        print("脚本退出") 