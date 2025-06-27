import cv2
import numpy as np
import os
import sys
import time
import csv
from datetime import datetime

# 价格区域相关参数
PRICE_OFFSET_X = 590  # 价格区域相对于标签右侧的水平偏移量
PRICE_WIDTH = 110  # 价格区域宽度
PRICE_HEIGHT = 40  # 价格区域高度

# 新增区域参数
BID_COUNT_REGION = (1140, 278, 38, 42)  # 出价数量区域 (x, y, w, h)
LISTING_COUNT_REGION = (1505, 285, 69, 32)  # 上架数量区域 (x, y, w, h)
RARITY_REGION = (270, 197, 52, 20)  # 稀有度区域 (x, y, w, h)

# 编辑按钮检测参数（用于识别本人价格）
EDIT_BUTTON_REGION = (2094, 407, 238, 65)  # 编辑按钮区域 (x, y, w, h)
EDIT_BUTTON_TEMPLATE = "edit_button.png"  # 编辑按钮模板文件名
EDIT_BUTTON_THRESHOLD = 0.7  # 编辑按钮匹配阈值

# 标签识别参数
TEMPLATE_DIR = "./templates/modern_warship/market_tags/"  # 模板目录
RARITY_TEMPLATE_DIR = "./templates/modern_warship/rarity/"  # 稀有度模板目录
OUTPUT_DIR = "./market_data/price_images/"  # 价格图像输出目录
DEVICE_SCREENSHOT_DIR = "./cache/test/"  # 设备截图保存目录
PRICE_DATA_FILE = "./market_data/price_data.csv"  # 价格数据CSV文件

# 标签模板文件名
LABEL_TEMPLATES = ["buying.png", "selling.png"]  # 移除了lowest_price.png

# 稀有度模板文件名
RARITY_TEMPLATES = {
    "改良": "common.png", 
    "稀有": "rare.png", 
    "史诗": "epic.png", 
    "传说": "legendary.png"
}

# 匹配阈值
MATCH_THRESHOLD = 0.8  # 模板匹配置信度阈值
RARITY_MATCH_THRESHOLD = 0.3  # 稀有度匹配置信度阈值
OVERLAP_THRESHOLD = 0.5  # 重叠区域判定阈值

# 确保输出目录存在
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 确保设备截图目录存在
if not os.path.exists(DEVICE_SCREENSHOT_DIR):
    os.makedirs(DEVICE_SCREENSHOT_DIR)

# 计算两个矩形的重叠程度
def calculate_overlap(rect1, rect2):
    """
    计算两个矩形的重叠程度
    
    参数:
        rect1: 第一个矩形 (x, y, w, h)
        rect2: 第二个矩形 (x, y, w, h)
        
    返回:
        重叠面积占较小矩形面积的比例
    """
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2
    
    # 计算重叠区域
    x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
    overlap_area = x_overlap * y_overlap
    
    # 计算两个矩形的面积
    area1 = w1 * h1
    area2 = w2 * h2
    
    # 返回重叠面积与较小矩形面积的比例
    if min(area1, area2) == 0:
        return 0
    return overlap_area / min(area1, area2)

def recognize_rarity(rarity_img):
    """
    使用模板匹配识别稀有度
    
    参数:
        rarity_img: 稀有度区域图像
        
    返回:
        识别的稀有度字符串和匹配度
    """
    best_match = None
    best_score = 0
    best_rarity = "未知"
    
    # 确保目录存在
    if not os.path.exists(RARITY_TEMPLATE_DIR):
        print(f"警告: 稀有度模板目录不存在: {RARITY_TEMPLATE_DIR}")
        return best_rarity, 0
    
    # 遍历所有稀有度模板
    for rarity_name, template_file in RARITY_TEMPLATES.items():
        template_path = os.path.join(RARITY_TEMPLATE_DIR, template_file)
        
        if not os.path.exists(template_path):
            print(f"警告: 稀有度模板不存在: {template_path}")
            continue
        
        # 读取模板
        template = cv2.imread(template_path)
        if template is None:
            print(f"无法读取稀有度模板: {template_path}")
            continue
        
        # 调整模板大小匹配稀有度区域
        template = cv2.resize(template, (rarity_img.shape[1], rarity_img.shape[0]))
        
        # 进行模板匹配
        result = cv2.matchTemplate(rarity_img, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        
        print(f"稀有度匹配 {rarity_name}: {max_val:.2f}")
        
        # 更新最佳匹配
        if max_val > best_score and max_val > RARITY_MATCH_THRESHOLD:
            best_score = max_val
            best_rarity = rarity_name
            best_match = template
    
    return best_rarity, best_score

def recognize_all_price_areas(screenshot_path, detect_own_prices=False):
    """
    从物品详情页截图中识别所有价格区域
    
    参数:
        screenshot_path: 物品详情页截图路径
        detect_own_prices: 是否检测本人价格（默认False）
        
    返回:
        成功时返回: found_areas, bid_count, listing_count, rarity_text
        失败时返回: [], 0, 0, ""
    """
    # 读取原始截图
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f"无法读取截图: {screenshot_path}")
        return [], 0, 0, ""
    
    # 存储所有找到的标签和价格区域
    found_areas = []
    
    # 检测是否有编辑按钮（本人价格）
    has_own_prices = detect_edit_button(img) if detect_own_prices else False
    
    # 识别额外区域
    bid_count_img = img[BID_COUNT_REGION[1]:BID_COUNT_REGION[1]+BID_COUNT_REGION[3], 
                     BID_COUNT_REGION[0]:BID_COUNT_REGION[0]+BID_COUNT_REGION[2]]
    listing_count_img = img[LISTING_COUNT_REGION[1]:LISTING_COUNT_REGION[1]+LISTING_COUNT_REGION[3], 
                         LISTING_COUNT_REGION[0]:LISTING_COUNT_REGION[0]+LISTING_COUNT_REGION[2]]
    rarity_img = img[RARITY_REGION[1]:RARITY_REGION[1]+RARITY_REGION[3], 
                  RARITY_REGION[0]:RARITY_REGION[0]+RARITY_REGION[2]]
    
    # 使用OCR识别出价和上架数量
    bid_count_text = recognize_price(bid_count_img)
    listing_count_text = recognize_price(listing_count_img)
    
    # 使用模板匹配识别稀有度
    rarity_text, rarity_score = recognize_rarity(rarity_img)
    
    # 转换为整数
    try:
        bid_count = int(bid_count_text.replace(',', '').strip()) if bid_count_text else 0
    except:
        bid_count = 0
        
    try:
        listing_count = int(listing_count_text.replace(',', '').strip()) if listing_count_text else 0
    except:
        listing_count = 0
    
    print(f"识别到的出价数量: {bid_count}")
    print(f"识别到的上架数量: {listing_count}")
    print(f"识别到的稀有度: {rarity_text} (匹配度: {rarity_score:.2f})")
    
    # 存储所有标签位置，用于找到本人价格
    all_label_positions = []
    
    # 遍历所有标签模板
    for template_name in LABEL_TEMPLATES:
        template_path = os.path.join(TEMPLATE_DIR, template_name)
        
        if not os.path.exists(template_path):
            print(f"警告: 标签模板不存在: {template_path}")
            continue
        
        # 读取标签模板
        template = cv2.imread(template_path)
        if template is None:
            print(f"无法读取标签模板: {template_path}")
            continue
        
        # 获取模板尺寸
        h, w = template.shape[:2]
        
        # 进行模板匹配
        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        
        # 找出所有匹配位置（大于阈值的位置）
        locations = np.where(result >= MATCH_THRESHOLD)
        
        # 转换为坐标列表
        matches = list(zip(*locations[::-1]))
        
        # 去除重叠的匹配
        filtered_matches = []
        for match in matches:
            # 检查与已有结果是否重叠
            match_rect = (match[0], match[1], w, h)
            is_overlapping = False
            
            for existing_match in filtered_matches:
                existing_rect = (existing_match[0], existing_match[1], w, h)
                if calculate_overlap(match_rect, existing_rect) > OVERLAP_THRESHOLD:
                    is_overlapping = True
                    break
            
            if not is_overlapping:
                # 添加置信度
                confidence = result[match[1], match[0]]
                filtered_matches.append((match[0], match[1], confidence))
        
        # 处理每个匹配位置
        for match_x, match_y, confidence in filtered_matches:
            # 计算标签中心点
            label_center_x = match_x + w // 2
            label_center_y = match_y + h // 2
            
            # 计算价格区域坐标
            price_x = label_center_x + PRICE_OFFSET_X
            price_y = label_center_y - PRICE_HEIGHT // 2  # 与标签中心垂直对齐
            
            # 确保坐标在合理范围内
            price_x = max(0, min(price_x, img.shape[1] - PRICE_WIDTH))
            price_y = max(0, min(price_y, img.shape[0] - PRICE_HEIGHT))
            
            # 定义价格区域
            price_region = (price_x, price_y, PRICE_WIDTH, PRICE_HEIGHT)
            label_region = (match_x, match_y, w, h)
            
            # 提取价格区域图像
            price_img = img[price_y:price_y+PRICE_HEIGHT, price_x:price_x+PRICE_WIDTH]
            
            # 获取标签类型名称（不含扩展名）
            label_type = os.path.splitext(template_name)[0]
            
            # 检查价格区域是否与已有区域重叠
            is_price_overlapping = False
            for _, existing_price_region, _, _, _ in found_areas:
                if calculate_overlap(price_region, existing_price_region) > OVERLAP_THRESHOLD:
                    is_price_overlapping = True
                    break
                    
            if not is_price_overlapping:
                # 添加到结果列表
                found_areas.append((price_img, price_region, label_type, label_region, confidence))
                
                # 如果需要检测本人价格，记录所有标签位置
                if detect_own_prices:
                    all_label_positions.append({
                        'y': match_y,
                        'label_type': label_type,
                        'index': len(found_areas) - 1  # 在found_areas中的索引
                    })
                
                print(f"发现标签: {label_type}, 置信度: {confidence:.2f}")
                print(f"标签位置: ({match_x}, {match_y}), 标签尺寸: {w}x{h}")
                print(f"价格区域: ({price_x}, {price_y}, {PRICE_WIDTH}, {PRICE_HEIGHT})")
                print("---")
    
    # 如果需要检测本人价格且检测到编辑按钮
    if detect_own_prices and has_own_prices and all_label_positions:
        # 找到y坐标最高（最小）的标签位置
        topmost_label = min(all_label_positions, key=lambda x: x['y'])
        topmost_index = topmost_label['index']
        
        # 修改对应条目的标签类型
        if topmost_index < len(found_areas):
            price_img, price_region, original_label_type, label_region, confidence = found_areas[topmost_index]
            # 修改为本人价格标签
            own_label_type = f"own_{original_label_type}"  # 例如：own_buying, own_selling
            found_areas[topmost_index] = (price_img, price_region, own_label_type, label_region, confidence)
            print(f"识别到本人价格: {own_label_type} (y坐标: {topmost_label['y']})")
    
    # 如果没有找到任何标签，使用固定区域方法
    if not found_areas:
        print("未找到任何标签，使用固定区域方法...")
        h, w = img.shape[:2]
        
        # 假定标签位置在屏幕左侧中央
        label_center_x = w // 4
        label_center_y = h // 2
        
        # 计算价格区域
        price_x = label_center_x + PRICE_OFFSET_X
        price_y = label_center_y - PRICE_HEIGHT // 2
        
        # 确保坐标在合理范围内
        price_x = max(0, min(price_x, w - PRICE_WIDTH))
        price_y = max(0, min(price_y, h - PRICE_HEIGHT))
        
        # 定义价格区域
        price_region = (price_x, price_y, PRICE_WIDTH, PRICE_HEIGHT)
        
        # 提取价格区域图像
        price_img = img[price_y:price_y+PRICE_HEIGHT, price_x:price_x+PRICE_WIDTH]
        
        print(f"使用固定区域方法识别价格区域: ({price_x}, {price_y}, {PRICE_WIDTH}, {PRICE_HEIGHT})")
        found_areas.append((price_img, price_region, "unknown", None, 0))
    
    return found_areas, bid_count, listing_count, rarity_text

def create_markup_image(img, found_areas, bid_count=0, listing_count=0, rarity=""):
    """
    在原图上标记所有找到的标签和价格区域
    
    参数:
        img: 原始图像
        found_areas: 所有找到的区域 [(price_img, price_region, label_type, label_region, confidence), ...]
        bid_count: 识别到的出价数量
        listing_count: 识别到的上架数量
        rarity: 识别到的稀有度
        
    返回:
        带标记的图像
    """
    # 复制原图
    img_with_markup = img.copy()
    
    # 标记颜色
    colors = {
        "buying": (0, 255, 0),      # 绿色
        "selling": (0, 0, 255),     # 红色
        "own_buying": (0, 255, 255),  # 黄色 - 本人求购价
        "own_selling": (255, 0, 255), # 紫色 - 本人售出价
        "unknown": (255, 255, 0)    # 青色
    }
    
    # 为每个找到的区域添加标记
    for _, price_region, label_type, label_region, confidence in found_areas:
        # 获取标记颜色
        color = colors.get(label_type, (255, 255, 255))
        
        # 标记价格区域
        price_x, price_y, price_w, price_h = price_region
        cv2.rectangle(img_with_markup, 
                     (price_x, price_y), 
                     (price_x + price_w, price_y + price_h), 
                     color, 2)
        
        # 如果有标签区域，标记标签区域并绘制连接线
        if label_region:
            label_x, label_y, label_w, label_h = label_region
            
            # 标记标签区域
            cv2.rectangle(img_with_markup, 
                         (label_x, label_y), 
                         (label_x + label_w, label_y + label_h), 
                         color, 2)
            
            # 计算标签中心点
            label_center_x = label_x + label_w // 2
            label_center_y = label_y + label_h // 2
            
            # 绘制从标签到价格区域的连线
            cv2.line(img_with_markup, 
                    (label_center_x, label_center_y), 
                    (price_x, label_center_y), 
                    color, 1)
            
            # 在标签上方标注标签类型和置信度
            label_text = f"{label_type} ({confidence:.2f})"
            cv2.putText(img_with_markup, 
                       label_text,
                       (label_x, label_y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    # 标记额外区域
    # 出价数量区域
    x, y, w, h = BID_COUNT_REGION
    cv2.rectangle(img_with_markup, (x, y), (x + w, y + h), (255, 0, 255), 2)
    cv2.putText(img_with_markup, f"出价数量: {bid_count}", (x, y - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
    
    # 上架数量区域
    x, y, w, h = LISTING_COUNT_REGION
    cv2.rectangle(img_with_markup, (x, y), (x + w, y + h), (255, 255, 0), 2)
    cv2.putText(img_with_markup, f"上架数量: {listing_count}", (x, y - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    
    # 稀有度区域
    x, y, w, h = RARITY_REGION
    cv2.rectangle(img_with_markup, (x, y), (x + w, y + h), (0, 255, 255), 2)
    cv2.putText(img_with_markup, f"稀有度: {rarity}", (x, y - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    # 标记编辑按钮区域（如果有本人价格）
    has_own_price = any('own_' in label_type for _, _, label_type, _, _ in found_areas)
    if has_own_price:
        x, y, w, h = EDIT_BUTTON_REGION
        cv2.rectangle(img_with_markup, (x, y), (x + w, y + h), (128, 0, 128), 2)
        cv2.putText(img_with_markup, "编辑按钮", (x, y - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 0, 128), 1)
    
    return img_with_markup

def save_price_image(price_img, screenshot_path, label_type=None, index=0, with_markup=False):
    """
    保存价格区域图像
    
    参数:
        price_img: 价格区域图像
        screenshot_path: 原始截图路径，用于生成输出文件名
        label_type: 标签类型（buying, lowest_price, selling 等）
        index: 索引号，用于区分同类型的多个区域
        with_markup: 是否在文件名中标记为带标记的图像
        
    返回:
        保存的文件路径
    """
    if price_img is None:
        print("无价格区域图像可保存")
        return None
    
    # 从原始截图路径中提取文件名（不含扩展名）
    base_filename = os.path.basename(screenshot_path)
    name_without_ext = os.path.splitext(base_filename)[0]
    
    # 生成输出文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label_suffix = f"_{label_type}" if label_type else ""
    index_suffix = f"_{index}" if index > 0 else ""
    markup_suffix = "_markup" if with_markup else ""
    output_filename = f"{name_without_ext}_price{label_suffix}{index_suffix}{markup_suffix}_{timestamp}.png"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    # 保存图像
    cv2.imwrite(output_path, price_img)
    print(f"已保存价格区域图像: {output_path}")
    return output_path

def recognize_price(price_img):
    """
    使用OCR识别价格区域图像中的价格
    
    参数:
        price_img: 价格区域图像
        
    返回:
        识别出的价格文本
    """
    try:
        # 导入OCR库
        try:
            from cnocr import CnOcr
        except ImportError:
            print("未安装cnocr库，正在尝试安装...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cnocr"])
            from cnocr import CnOcr
        
        # 保存价格区域图像到临时文件
        temp_path = f"./cache/temp_price_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        os.makedirs("./cache", exist_ok=True)
        cv2.imwrite(temp_path, price_img)
        
        # 初始化OCR模型
        ocr = CnOcr(rec_model_name='en_PP-OCRv3')  # 使用英文模型，适合识别数字
        
        # 识别价格
        result = ocr.ocr_for_single_line(temp_path)
        
        # 删除临时文件
        try:
            os.remove(temp_path)
        except:
            pass
        
        # 处理识别结果
        price_text = result["text"]
        
        # 将小数点替换为逗号
        price_text = price_text.replace('.', ',')
        
        # 清理结果，只保留数字、逗号和空格
        cleaned_price = ''.join(c for c in price_text if c.isdigit() or c == ',' or c == ' ')
        
        return cleaned_price
    except Exception as e:
        print(f"识别价格时出错: {str(e)}")
        return "识别失败"

def save_price_data(item_name, category_name, price_data, csv_file_path=None):
    """
    保存价格数据到CSV文件
    
    参数:
        item_name: 物品名称
        category_name: 物品分类
        price_data: 价格数据字典 {'buying': price, 'selling': price, ...}
        csv_file_path: 可选，指定CSV文件路径
        
    返回:
        是否成功保存
    """
    # 如果未提供文件路径，使用默认路径
    if not csv_file_path:
        csv_file_path = PRICE_DATA_FILE
    
    # 检查CSV文件是否存在，不存在则创建并写入表头
    file_exists = os.path.exists(csv_file_path)
    
    try:
        with open(csv_file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 获取当前时间
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
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
                        # 将逗号替换为空字符，然后转换为整数
                        clean_price = price.replace(',', '').replace(' ', '')
                        buying_prices.append(int(clean_price))
                    except:
                        print(f"无法解析购买价格: {price}")
                elif 'selling' in key:
                    try:
                        # 将逗号替换为空字符，然后转换为整数
                        clean_price = price.replace(',', '').replace(' ', '')
                        selling_prices.append(int(clean_price))
                    except:
                        print(f"无法解析出售价格: {price}")
            
            # 计算低买低卖溢价，确保使用整数
            spread = "N/A"
            if buying_prices and selling_prices:
                try:
                    max_buying = max(buying_prices)
                    min_selling = min(selling_prices)
                    # 修改计算方式：(最低出售价格*0.8-1) - (最高购买价格+1)
                    spread = int((min_selling * 0.8 - 1) - (max_buying + 1))  # 转换为整数
                except Exception as e:
                    print(f"计算低买低卖溢价时出错: {str(e)}")
            
            # 合并多个价格为一个字符串，用分号分隔，并添加逗号分隔符
            buying_price_str = '; '.join(format_price_with_commas(p) for p in buying_prices) if buying_prices else ''
            selling_price_str = '; '.join(format_price_with_commas(p) for p in selling_prices) if selling_prices else ''
            
            # 获取额外信息
            bid_count = price_data.get('bid_count', 0)
            listing_count = price_data.get('listing_count', 0)
            rarity = price_data.get('rarity', '')
            
            # 检查是否是报价追踪文件
            is_bid_tracker_file = csv_file_path and '报价追踪.csv' in csv_file_path
            
            # 根据文件类型决定表头和数据行格式
            if is_bid_tracker_file:
                # 报价追踪文件：始终使用包含所有本人价格列的固定格式
                if not file_exists:
                    writer.writerow(['物品名称', '物品分类', '购买价格', '出售价格', '本人购买价格', '本人售出价格', '低买低卖溢价', '时间戳', '出价数量', '上架数量', '稀有度'])
                
                # 数据行：所有列都有值，本人价格列如果没有就用空字符串
                writer.writerow([
                    item_name, 
                    category_name, 
                    buying_price_str, 
                    selling_price_str,
                    own_buying_price if own_buying_price else '',  # 本人购买价格，没有则为空
                    own_selling_price if own_selling_price else '',  # 本人售出价格，没有则为空
                    spread,
                    timestamp,
                    bid_count,
                    listing_count,
                    rarity
                ])
            elif own_buying_price or own_selling_price:
                # 普通文件且有本人价格时的动态格式
                if not file_exists:
                    if own_buying_price and own_selling_price:
                        writer.writerow(['物品名称', '物品分类', '购买价格', '出售价格', '本人购买价格', '本人售出价格', '低买低卖溢价', '时间戳', '出价数量', '上架数量', '稀有度'])
                    elif own_buying_price:
                        writer.writerow(['物品名称', '物品分类', '购买价格', '出售价格', '本人购买价格', '低买低卖溢价', '时间戳', '出价数量', '上架数量', '稀有度'])
                    elif own_selling_price:
                        writer.writerow(['物品名称', '物品分类', '购买价格', '出售价格', '本人售出价格', '低买低卖溢价', '时间戳', '出价数量', '上架数量', '稀有度'])
                
                # 数据行
                if own_buying_price and own_selling_price:
                    writer.writerow([item_name, category_name, buying_price_str, selling_price_str, own_buying_price, own_selling_price, spread, timestamp, bid_count, listing_count, rarity])
                elif own_buying_price:
                    writer.writerow([item_name, category_name, buying_price_str, selling_price_str, own_buying_price, spread, timestamp, bid_count, listing_count, rarity])
                elif own_selling_price:
                    writer.writerow([item_name, category_name, buying_price_str, selling_price_str, own_selling_price, spread, timestamp, bid_count, listing_count, rarity])
            else:
                # 普通文件且没有本人价格时的标准格式
                if not file_exists:
                    writer.writerow(['物品名称', '物品分类', '购买价格', '出售价格', '低买低卖溢价', '时间戳', '出价数量', '上架数量', '稀有度'])
                
                writer.writerow([item_name, category_name, buying_price_str, selling_price_str, spread, timestamp, bid_count, listing_count, rarity])
        
        print(f"价格数据已保存到: {csv_file_path}")
        return True
    except Exception as e:
        print(f"保存价格数据时出错: {str(e)}")
        return False

def get_rarity_from_history(item_name, category_name):
    """
    从历史CSV文件中查找物品的稀有度
    
    参数:
        item_name: 物品名称
        category_name: 物品分类
        
    返回:
        找到的稀有度，如果未找到则返回"未知"
    """
    try:
        # 获取当前目录下的所有CSV文件
        csv_files = [f for f in os.listdir("./market_data") if f.startswith("price_data_") and f.endswith(".csv")]
        
        # 按时间倒序排序，优先使用最新的数据
        csv_files.sort(reverse=True)
        
        for csv_file in csv_files:
            csv_path = os.path.join("./market_data", csv_file)
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['物品名称'] == item_name and row['物品分类'] == category_name:
                            rarity = row['稀有度']
                            if rarity and rarity != "未知":
                                print(f"从历史数据中找到稀有度: {rarity}")
                                return rarity
            except Exception as e:
                print(f"读取历史CSV文件时出错: {str(e)}")
                continue
        
        print("未在历史数据中找到稀有度")
        return "未知"
    except Exception as e:
        print(f"查找历史稀有度时出错: {str(e)}")
        return "未知"

def process_screenshot(screenshot_path, item_name="未知物品", category_name="未知分类", detect_own_prices=False):
    """
    处理一张物品详情页截图，提取并保存所有价格区域
    
    参数:
        screenshot_path: 物品详情页截图路径
        item_name: 物品名称
        category_name: 物品分类
        detect_own_prices: 是否检测本人价格（默认False）
        
    返回:
        价格区域图像路径列表, 带标记的原图路径, 价格数据字典
    """
    print(f"处理截图: {screenshot_path}")
    
    # 读取原始图像
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f"无法读取截图: {screenshot_path}")
        return [], None, {}
    
    # 识别所有价格区域和额外信息
    result = recognize_all_price_areas(screenshot_path, detect_own_prices)
    
    if not result or len(result) < 3:
        print("未找到任何价格区域")
        return [], None, {}
    
    found_areas, bid_count, listing_count, rarity_text = result
    
    if not found_areas:
        print("未找到任何价格区域")
        return [], None, {}
    
    # 如果稀有度识别失败，尝试从历史数据中获取
    if rarity_text == "未知":
        rarity_text = get_rarity_from_history(item_name, category_name)
    
    # 在原图上标记所有区域
    img_with_markup = create_markup_image(img, found_areas, bid_count, listing_count, rarity_text)
    
    # 保存带标记的原图
    markup_img_path = save_price_image(img_with_markup, screenshot_path, "all", 0, with_markup=True)
    
    # 保存每个价格区域图像并进行OCR识别
    price_img_paths = []
    label_counts = {}  # 用于同类型标签计数
    price_data = {
        'bid_count': bid_count,
        'listing_count': listing_count,
        'rarity': rarity_text
    }
    
    for price_img, _, label_type, _, _ in found_areas:
        # 获取该类型的索引
        if label_type in label_counts:
            label_counts[label_type] += 1
        else:
            label_counts[label_type] = 0
        
        # 保存价格区域图像
        price_img_path = save_price_image(price_img, screenshot_path, label_type, label_counts[label_type])
        price_img_paths.append(price_img_path)
        
        # 识别价格
        if label_type in ['buying', 'selling', 'own_buying', 'own_selling']:
            price = recognize_price(price_img)
            
            # 处理本人价格：替换对应的普通价格字段
            if label_type == 'own_buying':
                # 本人购买价格替换购买价格
                price_data['本人购买价格'] = price
                # 如果之前有普通购买价格，移除它
                if 'buying' in price_data:
                    del price_data['buying']
            elif label_type == 'own_selling':
                # 本人售出价格替换售出价格
                price_data['本人售出价格'] = price
                # 如果之前有普通售出价格，移除它
                if 'selling' in price_data:
                    del price_data['selling']
            else:
                # 普通价格处理
                if label_type in price_data:
                    price_data[f"{label_type}_{label_counts[label_type]}"] = price
                else:
                    price_data[label_type] = price
    
    # 计算并显示低买低卖溢价
    spread = "N/A"
    buying_prices = []
    selling_prices = []
    
    for key, price in price_data.items():
        if 'buying' in key:
            try:
                clean_price = price.replace(',', '').replace(' ', '')
                buying_prices.append(float(clean_price))
            except:
                pass
        elif 'selling' in key:
            try:
                clean_price = price.replace(',', '').replace(' ', '')
                selling_prices.append(float(clean_price))
            except:
                pass
    
    if buying_prices and selling_prices:
        try:
            max_buying = max(buying_prices)
            min_selling = min(selling_prices)
            # 修改计算方式：(最低出售价格*0.8-1) - (最高购买价格+1)
            spread = int((min_selling * 0.8 - 1) - (max_buying + 1))  # 转换为整数
            print(f"最高购买价格: {format_price_with_commas(max_buying)}")
            print(f"最低出售价格: {format_price_with_commas(min_selling)}")
            print(f"最低出售价格(打八折): {format_price_with_commas(int(min_selling * 0.8))}")
            print(f"低买低卖溢价: {format_price_with_commas(spread)}")
        except Exception as e:
            print(f"计算低买低卖溢价时出错: {str(e)}")
    
    # 保存价格数据到CSV（恢复自动保存功能）
    if price_data:
        save_price_data(item_name, category_name, price_data)
    
    return price_img_paths, markup_img_path, price_data

def process_dir(screenshots_dir, item_names=None):
    """
    处理目录中的所有截图
    
    参数:
        screenshots_dir: 截图目录路径
        item_names: 物品名称字典 {filename_pattern: (item_name, category_name)}
        
    返回:
        处理的图片数量, 识别的价格区域总数
    """
    # 确保目录存在
    if not os.path.exists(screenshots_dir):
        print(f"目录不存在: {screenshots_dir}")
        return 0, 0
    
    # 获取所有png文件
    screenshots = [os.path.join(screenshots_dir, f) for f in os.listdir(screenshots_dir) 
                  if f.lower().endswith('.png') and 'item_detail' in f.lower()]
    
    print(f"在目录 {screenshots_dir} 中找到 {len(screenshots)} 张物品详情页截图")
    
    file_count = 0
    area_count = 0
    for screenshot_path in screenshots:
        try:
            # 获取文件名
            filename = os.path.basename(screenshot_path)
            
            # 尝试从文件名匹配物品信息
            item_name = "未知物品"
            category_name = "未知分类"
            
            if item_names:
                for pattern, (name, category) in item_names.items():
                    if pattern in filename:
                        item_name = name
                        category_name = category
                        break
            
            price_img_paths, _, _ = process_screenshot(screenshot_path, item_name, category_name)
            if price_img_paths:
                file_count += 1
                area_count += len(price_img_paths)
        except Exception as e:
            print(f"处理截图时出错: {str(e)}")
    
    return file_count, area_count

# 添加从设备获取截图的函数
def capture_from_device(device_id=""):
    """
    直接从设备获取截图
    
    参数:
        device_id: 设备ID，为空时尝试自动获取
        
    返回:
        截图路径
    """
    try:
        # 导入ADB辅助模块
        sys.path.append("./")
        import RaphaelScriptHelper as rsh
        
        # 设置设备ID
        if not device_id:
            try:
                devices = rsh.ADBHelper.getDevicesList()
                if devices:
                    device_id = devices[0]
                    print(f"自动选择设备ID: {device_id}")
                else:
                    print("未检测到连接的安卓设备")
                    return None
            except Exception as e:
                print(f"获取设备列表时出错: {str(e)}")
                return None
        
        rsh.deviceID = device_id
        
        # 生成截图文件名和路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"{DEVICE_SCREENSHOT_DIR}device_screenshot_{timestamp}.png"
        
        # 使用ADB获取截图
        print(f"正在从设备 {device_id} 获取截图...")
        rsh.ADBHelper.screenCapture(device_id, screenshot_path)
        print(f"成功获取设备截图: {screenshot_path}")
        
        return screenshot_path
    except Exception as e:
        print(f"从设备获取截图时出错: {str(e)}")
        return None

# 添加格式化价格的辅助函数
def format_price_with_commas(price):
    """
    将价格格式化为带逗号的字符串
    
    参数:
        price: 价格数值
        
    返回:
        格式化后的价格字符串
    """
    price_str = str(price)
    parts = []
    # 从右到左，每3位添加一个逗号
    for i in range(len(price_str) - 1, -1, -3):
        start = max(0, i - 2)
        parts.append(price_str[start:i+1])
    
    # 逆序连接并返回
    return ','.join(reversed(parts))

def detect_edit_button(img):
    """
    检测页面中是否存在编辑按钮，用于判断是否有本人的价格条目
    
    参数:
        img: 原始图像
        
    返回:
        True表示检测到编辑按钮（有本人价格），False表示没有
    """
    try:
        # 提取编辑按钮区域
        x, y, w, h = EDIT_BUTTON_REGION
        edit_region = img[y:y+h, x:x+w]
        
        # 构建编辑按钮模板路径
        template_path = os.path.join(TEMPLATE_DIR, EDIT_BUTTON_TEMPLATE)
        
        # 检查模板文件是否存在
        if not os.path.exists(template_path):
            print(f"警告: 编辑按钮模板不存在: {template_path}")
            return False
        
        # 读取编辑按钮模板
        template = cv2.imread(template_path)
        if template is None:
            print(f"无法读取编辑按钮模板: {template_path}")
            return False
        
        # 调整模板大小匹配编辑按钮区域
        template = cv2.resize(template, (w, h))
        
        # 进行模板匹配
        result = cv2.matchTemplate(edit_region, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        
        print(f"编辑按钮匹配度: {max_val:.2f}")
        
        # 判断是否检测到编辑按钮
        is_detected = max_val > EDIT_BUTTON_THRESHOLD
        print(f"检测到编辑按钮: {is_detected}")
        
        return is_detected
    except Exception as e:
        print(f"检测编辑按钮时出错: {str(e)}")
        return False

def main():
    """
    主函数，作为独立脚本运行时调用
    """
    print("\n" + "="*50)
    print("     现代战舰市场物品价格区域识别")
    print("="*50 + "\n")
    
    # 默认物品信息
    default_item_name = "[韩]忠南"
    default_category_name = "舰艇"
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 检查是否提供了物品信息参数
        item_name = default_item_name
        category_name = default_category_name
        detect_own_prices = False  # 默认不检测本人价格
        
        # 解析物品信息参数
        for i, arg in enumerate(sys.argv):
            if arg == "--name" and i+1 < len(sys.argv):
                item_name = sys.argv[i+1]
            elif arg == "--category" and i+1 < len(sys.argv):
                category_name = sys.argv[i+1]
            elif arg == "--detect-own-prices":
                detect_own_prices = True
                print("启用本人价格检测功能")
        
        # 检查是否是特殊命令
        if sys.argv[1].lower() == "device":
            # 直接从设备获取截图并处理
            device_id = ""
            for i, arg in enumerate(sys.argv):
                if arg == "--device" and i+1 < len(sys.argv):
                    device_id = sys.argv[i+1]
            
            screenshot_path = capture_from_device(device_id)
            
            if screenshot_path:
                print(f"处理设备截图: {screenshot_path}")
                print(f"物品信息: {item_name} ({category_name})")
                price_img_paths, markup_img_path, price_data = process_screenshot(screenshot_path, item_name, category_name, detect_own_prices)
                if price_img_paths:
                    print(f"成功提取 {len(price_img_paths)} 个价格区域:")
                    for path in price_img_paths:
                        print(f"  - {path}")
                    if markup_img_path:
                        print(f"带标记的原图: {markup_img_path}")
                    
                    # 显示价格数据
                    print("\n价格信息:")
                    for label, price in price_data.items():
                        if label in ['bid_count', 'listing_count', 'rarity']:
                            continue
                        # 显示友好的标签名称
                        if label == "buying":
                            label_display = "购买价格"
                        elif label == "selling":
                            label_display = "出售价格"
                        elif label == "own_buying":
                            label_display = "本人求购价"
                        elif label == "own_selling":
                            label_display = "本人售出价"
                        else:
                            label_display = label
                        print(f"  {label_display}: {price}")
                else:
                    print("未能提取任何价格区域")
            else:
                print("获取设备截图失败")
            return
            
        # 处理路径参数
        path = sys.argv[1]
        if os.path.isfile(path):
            # 处理单个文件
            print(f"处理单个截图: {path}")
            print(f"物品信息: {item_name} ({category_name})")
            price_img_paths, markup_img_path, price_data = process_screenshot(path, item_name, category_name, detect_own_prices)
            if price_img_paths:
                print(f"成功提取 {len(price_img_paths)} 个价格区域:")
                for path in price_img_paths:
                    print(f"  - {path}")
                if markup_img_path:
                    print(f"带标记的原图: {markup_img_path}")
                
                # 显示价格数据
                print("\n价格信息:")
                for label, price in price_data.items():
                    if label in ['bid_count', 'listing_count', 'rarity']:
                        continue
                    # 显示友好的标签名称
                    if label == "buying":
                        label_display = "购买价格"
                    elif label == "selling":
                        label_display = "出售价格"
                    elif label == "own_buying":
                        label_display = "本人求购价"
                    elif label == "own_selling":
                        label_display = "本人售出价"
                    else:
                        label_display = label
                    print(f"  {label_display}: {price}")
            else:
                print("未能提取任何价格区域")
        elif os.path.isdir(path):
            # 处理整个目录
            print(f"处理目录中的截图: {path}")
            file_count, area_count = process_dir(path)
            print(f"成功处理了 {file_count} 张截图，共提取 {area_count} 个价格区域")
        else:
            print(f"无效的路径: {path}")
    else:
        # 默认行为：直接从设备获取截图
        print("未提供参数，将直接从设备获取截图")
        print(f"使用默认物品信息: {default_item_name} ({default_category_name})")
        screenshot_path = capture_from_device()
        
        if screenshot_path:
            price_img_paths, markup_img_path, price_data = process_screenshot(screenshot_path, default_item_name, default_category_name, False)
            if price_img_paths:
                print(f"成功提取 {len(price_img_paths)} 个价格区域:")
                for path in price_img_paths:
                    print(f"  - {path}")
                if markup_img_path:
                    print(f"带标记的原图: {markup_img_path}")
                
                # 显示价格数据
                print("\n价格信息:")
                for label, price in price_data.items():
                    if label in ['bid_count', 'listing_count', 'rarity']:
                        continue
                    label_display = "购买价格" if "buying" in label else "出售价格" if "selling" in label else label
                    print(f"  {label_display}: {price}")
            else:
                print("未能提取任何价格区域")
        else:
            # 如果获取设备截图失败，尝试处理缓存目录的截图
            print("获取设备截图失败，尝试处理缓存目录中的截图")
            default_dir = "./cache/market_screenshots/"
            if os.path.exists(default_dir):
                print(f"处理默认目录: {default_dir}")
                file_count, area_count = process_dir(default_dir)
                print(f"成功处理了 {file_count} 张截图，共提取 {area_count} 个价格区域")
            else:
                print(f"默认目录不存在: {default_dir}")
                print("请提供有效的截图路径作为参数，或使用'device'参数从设备获取截图")
    
    print("\n" + "="*50)
    print("处理完成")
    print("="*50 + "\n")

if __name__ == "__main__":
    # 作为独立脚本运行
    main() 