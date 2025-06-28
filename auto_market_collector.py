#!/usr/bin/env python3
"""
自动化市场数据采集脚本
根据当天数据情况自动决定运行策略：
1. 无普查数据时：执行完整市场普查
2. 有普查数据时：根据筛选条件生成抽查清单并执行抽查
"""

import os
import glob
import json
import csv
import subprocess
import sys
from datetime import datetime
import re

# 配置参数
MARKET_DATA_DIR = "./market_data/"
TEMP_DIR = "./temp/"
FILTER_CONFIG_FILE = f"{MARKET_DATA_DIR}筛选预设.json"

# 确保目录存在
os.makedirs(MARKET_DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def get_today_string():
    """获取今天的日期字符串 YYYYMMDD"""
    return datetime.now().strftime("%Y%m%d")

def get_current_timestamp():
    """获取当前时间戳 YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def find_today_survey_files():
    """查找当天的市场普查文件"""
    today = get_today_string()
    pattern = f"{MARKET_DATA_DIR}市场普查_{today}_*.csv"
    files = glob.glob(pattern)
    return sorted(files)  # 按文件名排序，最新的在后面

def find_today_filter_files():
    """查找当天的普查预筛选文件"""
    today = get_today_string()
    pattern = f"{TEMP_DIR}普查预筛选_{today}_*.json"
    files = glob.glob(pattern)
    return sorted(files)  # 按文件名排序，最新的在后面

def load_filter_config():
    """加载筛选配置"""
    try:
        with open(FILTER_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"加载筛选配置: 最大购买价格 {config.get('max_buy_price', 2000)}")
        return config
    except Exception as e:
        print(f"加载筛选配置失败: {str(e)}")
        # 返回默认配置
        return {
            "max_buy_price": 2000,
            "min_spread": 45,
            "min_profit_rate": 9.0,
            "min_bid_count": 3
        }

def parse_price_string(price_str):
    """解析价格字符串，返回最低价格"""
    if not price_str or price_str.strip() == '':
        return None
    
    try:
        # 移除引号
        price_str = price_str.strip('"')
        # 分割多个价格
        prices = [p.strip() for p in price_str.split(';')]
        # 转换为数字并找最小值
        numeric_prices = []
        for p in prices:
            if p:
                # 移除逗号分隔符
                clean_price = p.replace(',', '')
                try:
                    numeric_prices.append(float(clean_price))
                except ValueError:
                    continue
        
        return min(numeric_prices) if numeric_prices else None
    except Exception as e:
        print(f"解析价格字符串失败: {price_str}, 错误: {str(e)}")
        return None

def parse_spread_value(spread_str):
    """解析低买低卖溢价值"""
    if not spread_str or spread_str.strip() == '':
        return None
    
    try:
        # 移除逗号分隔符并转换为数字
        clean_spread = spread_str.replace(',', '').strip()
        return float(clean_spread)
    except ValueError:
        return None
    except Exception as e:
        print(f"解析溢价值失败: {spread_str}, 错误: {str(e)}")
        return None

def filter_survey_data(survey_file, filter_config):
    """根据筛选条件过滤市场普查数据"""
    filtered_items = []
    max_buy_price = filter_config.get('max_buy_price', 2000)
    
    # 统计信息
    total_items = 0
    price_filtered_count = 0
    spread_filtered_count = 0
    final_filtered_count = 0
    
    try:
        with open(survey_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_items += 1
                
                # 解析购买价格
                buy_price_str = row.get('购买价格', '')
                min_buy_price = parse_price_string(buy_price_str)
                
                # 解析低买低卖溢价
                spread_str = row.get('低买低卖溢价', '')
                spread_value = parse_spread_value(spread_str)
                
                # 价格筛选条件
                price_condition = min_buy_price is not None and min_buy_price <= max_buy_price
                if price_condition:
                    price_filtered_count += 1
                
                # 溢价筛选条件（非负数）
                spread_condition = spread_value is not None and spread_value >= 0
                if spread_condition:
                    spread_filtered_count += 1
                
                # 同时满足两个条件
                if price_condition and spread_condition:
                    final_filtered_count += 1
                    filtered_items.append({
                        "name": row.get('物品名称', ''),
                        "category": row.get('物品分类', ''),
                        "buy_price": min_buy_price,
                        "spread": spread_value
                    })
        
        # 显示详细统计信息
        print(f"\n筛选统计信息:")
        print(f"  总物品数量: {total_items}")
        print(f"  购买价格 ≤ {max_buy_price} 的物品: {price_filtered_count}")
        print(f"  低买低卖溢价 ≥ 0 的物品: {spread_filtered_count}")
        print(f"  同时满足两个条件的物品: {final_filtered_count}")
        print(f"  最终筛选出的物品数量: {len(filtered_items)}")
        
        return filtered_items
    
    except Exception as e:
        print(f"筛选数据时出错: {str(e)}")
        return []

def save_filter_preset(items, timestamp, filter_config=None):
    """保存筛选预设文件"""
    preset_file = f"{TEMP_DIR}普查预筛选_{timestamp}.json"
    
    # 简化的预设数据格式，只保留必要字段
    preset_data = {
        "name": f"筛选预设_{timestamp}",
        "items": [
            {
                "name": item["name"],
                "category": item["category"]
            }
            for item in items
        ]
    }
    
    try:
        with open(preset_file, 'w', encoding='utf-8') as f:
            json.dump(preset_data, f, ensure_ascii=False, indent=2)
        print(f"已保存筛选预设文件: {preset_file}")
        return preset_file
    except Exception as e:
        print(f"保存筛选预设文件失败: {str(e)}")
        return None

def run_market_script(command_args):
    """运行市场采集脚本"""
    cmd = ["py", "ModernWarshipMarket.py"] + command_args
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print("脚本执行成功")
            return True
        else:
            print(f"脚本执行失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"执行脚本时出错: {str(e)}")
        return False

def main():
    """主函数"""
    print("="*60)
    print("        自动化市场数据采集脚本")
    print("="*60)
    
    today = get_today_string()
    current_timestamp = get_current_timestamp()
    
    # 检查当天是否已有市场普查文件
    survey_files = find_today_survey_files()
    
    if not survey_files:
        # 情况1: 当天没有市场普查文件，执行完整普查
        print(f"未找到当天({today})的市场普查文件，开始执行完整市场普查...")
        
        output_filename = f"市场普查_{current_timestamp}"
        command_args = [
            "--start_category", "0",
            "--start_item", "0",
            "--output", output_filename
        ]
        
        success = run_market_script(command_args)
        if success:
            print(f"完整市场普查执行完成，输出文件: {output_filename}.csv")
        else:
            print("完整市场普查执行失败")
            return False
    
    else:
        # 情况2: 当天已有市场普查文件
        latest_survey = survey_files[-1]  # 取最新的普查文件
        print(f"发现当天市场普查文件: {os.path.basename(latest_survey)}")
        
        # 检查是否已有普查预筛选文件
        filter_files = find_today_filter_files()
        
        if not filter_files:
            # 情况2a: 没有预筛选文件，需要生成
            print("未找到普查预筛选文件，开始生成筛选清单...")
            
            # 加载筛选配置
            filter_config = load_filter_config()
            
            # 筛选数据
            filtered_items = filter_survey_data(latest_survey, filter_config)
            
            if not filtered_items:
                print("筛选结果为空，无法生成抽查清单")
                return False
            
            # 显示筛选结果示例
            print(f"\n筛选结果示例（前10个）:")
            for i, item in enumerate(filtered_items[:10]):
                print(f"  {i+1}. {item['name']} ({item['category']}) - 购买价格: {item['buy_price']}, 溢价: {item['spread']}")
            if len(filtered_items) > 10:
                print(f"  ... 还有 {len(filtered_items) - 10} 个物品")
            
            # 保存筛选预设
            preset_file = save_filter_preset(filtered_items, current_timestamp, filter_config)
            if not preset_file:
                print("保存筛选预设失败")
                return False
        
        else:
            # 情况2b: 已有预筛选文件，直接使用最新的
            preset_file = filter_files[-1]
            print(f"发现现有普查预筛选文件: {os.path.basename(preset_file)}")
        
        # 使用预设文件执行小抽查
        print("开始执行小抽查...")
        
        output_filename = f"小抽查_{current_timestamp}"
        command_args = [
            "--preset", preset_file,
            "--price_output", output_filename
        ]
        
        success = run_market_script(command_args)
        if success:
            print(f"小抽查执行完成，输出文件: {output_filename}.csv")
        else:
            print("小抽查执行失败")
            return False
    
    print("\n" + "="*60)
    print("        自动化采集完成")
    print("="*60)
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n脚本被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n脚本执行出错: {str(e)}")
        sys.exit(1) 