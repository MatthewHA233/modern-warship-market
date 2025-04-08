import ADBHelper
import time
import sys

#######################
# 脚本配置 - 修改这里 #
#######################

# 设备ID，留空则自动检测
DEVICE_ID = ""

# 操作类型 (1-8)
# 1: 物品列表向下滑动
# 2: 物品列表向上滑动
# 3: 分类栏向下滑动
# 4: 分类栏向上滑动
# 5: 价格区域向下滑动
# 6: 价格区域向上滑动
# 7: 测试点击阻力点
# 8: 物品识别补偿移动
OPERATION_TYPE = 8

# 滑动次数
SLIDE_TIMES = 1

# 自动模式 - 设置为True则使用上面的配置，False则使用终端交互
AUTO_MODE = False

#######################
# 以下为脚本常量设置 #
#######################

# 滑动预设值（起点坐标，终点坐标）
# 向下滑动: 从下往上滑
# 向上滑动: 从上往下滑

# 市场物品列表滑动
MARKET_DOWN = ((1400, 900), (1400, 400))  # 物品列表向下滑（显示下面的内容）
MARKET_UP = ((1400, 350), (1400, 900))    # 物品列表向上滑（显示上面的内容）

# 补偿移动 - 用于物品识别失败后的重试
COMPENSATION_MOVE_DOWN = ((1400, 600), (1400, 200))  # 短距离下滑
COMPENSATION_MOVE_DOWN_LONG = ((1400, 1000), (1400, 200))  # 更长距离下滑，用于第二次补偿尝试
COMPENSATION_MOVE_UP = ((1400, 200), (1400, 600))    # 短距离上滑

# 物品分类栏滑动
CATEGORY_DOWN = ((320, 700), (320, 400))  # 分类栏向下滑
CATEGORY_UP = ((320, 400), (320, 700))    # 分类栏向上滑

# 价格区域滑动
PRICE_DOWN = ((1400, 800), (1400, 580))     # 价格区域向下滑
PRICE_UP = ((1400, 400), (1400, 1000))       # 价格区域向上滑

# 阻力点 - 用于阻止滚动惯性
FRICTION_POINT = (2320, 617)  # 市场物品阻力点坐标

# 滑动参数设置
DEFAULT_DURATION = 100  # 默认滑动时间(毫秒)，减少为100毫秒使滑动更快
AFTER_SLIDE_DELAY = 0.05  # 滑动后的默认等待时间(秒)
FRICTION_DELAY = 0.05  # 点击阻力点后的等待时间(秒)

#######################
# 脚本函数 #
#######################

def set_device_id(device_id):
    """设置设备ID"""
    global DEVICE_ID
    DEVICE_ID = device_id
    print(f"设备ID已设置为: {DEVICE_ID}")

def click_friction_point():
    """点击阻力点以阻止滚动惯性"""
    if not DEVICE_ID:
        devices = ADBHelper.getDevicesList()
        if devices:
            set_device_id(devices[0])
        else:
            print("错误: 未检测到设备，请手动设置设备ID")
            return False
    
    print(f"点击阻力点: {FRICTION_POINT}")
    ADBHelper.touch(DEVICE_ID, FRICTION_POINT)
    time.sleep(FRICTION_DELAY)
    return True

def slide(start_pos, end_pos, duration=DEFAULT_DURATION, after_delay=AFTER_SLIDE_DELAY):
    """执行滑动操作"""
    if not DEVICE_ID:
        devices = ADBHelper.getDevicesList()
        if devices:
            set_device_id(devices[0])
        else:
            print("错误: 未检测到设备，请手动设置设备ID")
            return False
    
    print(f"滑动: 从 {start_pos} 到 {end_pos}")
    result = ADBHelper.slide(DEVICE_ID, start_pos, end_pos, duration)
    
    # 滑动后等待指定时间，确保滑动动画完成
    if result and after_delay > 0:
        print(f"滑动后等待: {after_delay}秒")
        time.sleep(after_delay)
    
    return result

def market_down(times=1, after_delay=AFTER_SLIDE_DELAY):
    """市场物品列表向下滑动"""
    for i in range(times):
        print(f"物品列表向下滑动 ({i+1}/{times})")
        slide(MARKET_DOWN[0], MARKET_DOWN[1], DEFAULT_DURATION, 
              after_delay if i == times-1 else 0.2)  # 最后一次滑动使用完整延时
        
        # 点击阻力点阻止滚动惯性
        click_friction_point()
        
        if i < times - 1:
            time.sleep(0.04)  # 连续滑动间隔减少到0.04秒

def market_up(times=1, after_delay=AFTER_SLIDE_DELAY):
    """市场物品列表向上滑动"""
    for i in range(times):
        print(f"物品列表向上滑动 ({i+1}/{times})")
        slide(MARKET_UP[0], MARKET_UP[1], DEFAULT_DURATION,
              after_delay if i == times-1 else 0.2)
        
        # 点击阻力点阻止滚动惯性
        click_friction_point()
        
        if i < times - 1:
            time.sleep(0.1)  # 连续滑动间隔减少到0.1秒

def compensation_move(times=1, after_delay=AFTER_SLIDE_DELAY, attempt_number=1, normal_scroll_times=0):
    """
    物品识别失败后的补偿移动
    
    参数:
    times - 保留此参数以兼容旧代码，但不再使用
    after_delay - 滑动后的延迟时间
    attempt_number - 当前是第几次补偿尝试 (1-5)，超过5会循环回到第1次尝试
    normal_scroll_times - 该物品的正常滑动次数
    """
    # 计算实际尝试号码(1-5循环)
    actual_attempt = ((attempt_number - 1) % 5) + 1
    
    if actual_attempt == 1:
        # 第一次补偿尝试: 上滑一次
        print(f"补偿移动 (尝试 {actual_attempt}/5) - 上滑一次")
        slide(COMPENSATION_MOVE_UP[0], COMPENSATION_MOVE_UP[1], DEFAULT_DURATION, after_delay)
        click_friction_point()
    elif actual_attempt == 2:
        # 第二次补偿尝试: 更长距离下滑一次
        print(f"补偿移动 (尝试 {actual_attempt}/5) - 更长距离下滑")
        slide(COMPENSATION_MOVE_DOWN_LONG[0], COMPENSATION_MOVE_DOWN_LONG[1], DEFAULT_DURATION, after_delay)
        click_friction_point()
    elif actual_attempt == 3:
        # 第三次补偿尝试: 标准距离下滑一次
        print(f"补偿移动 (尝试 {actual_attempt}/5) - 标准下滑")
        slide(COMPENSATION_MOVE_DOWN[0], COMPENSATION_MOVE_DOWN[1], DEFAULT_DURATION, after_delay)
        click_friction_point()
    elif actual_attempt == 4:
        # 第四次补偿尝试: 连续向上正常滑动多次
        # 比正常的寻找滑动多2次
        up_times = normal_scroll_times + 2
        if up_times < 2:  # 确保至少滑动2次
            up_times = 2
            
        print(f"补偿移动 (尝试 {actual_attempt}/5) - 连续向上滑动{up_times}次 (比正常滑动多2次)")
        
        for i in range(up_times):
            print(f"  - 向上滑动 ({i+1}/{up_times})")
            # 使用正常的向上滑动，不是补偿滑动
            slide(MARKET_UP[0], MARKET_UP[1], DEFAULT_DURATION, 
                  after_delay if i == up_times-1 else 0.2)  # 最后一次滑动使用完整延时
            
            # 每次滑动后点击阻力点
            click_friction_point()
            
            if i < up_times - 1:
                time.sleep(0.1)  # 连续滑动间隔减少到0.1秒
    else:  # actual_attempt == 5
        # 第五次补偿尝试: 模拟日常找物品时的下滑操作
        down_times = normal_scroll_times
        if down_times < 1:  # 确保至少滑动1次
            down_times = 1
            
        print(f"补偿移动 (尝试 {actual_attempt}/5) - 模拟正常下滑{down_times}次")
        
        for i in range(down_times):
            print(f"  - 向下滑动 ({i+1}/{down_times})")
            # 使用正常的向下滑动
            slide(MARKET_DOWN[0], MARKET_DOWN[1], DEFAULT_DURATION, 
                  after_delay if i == down_times-1 else 0.2)  # 最后一次滑动使用完整延时
            
            # 每次滑动后点击阻力点
            click_friction_point()
            
            if i < down_times - 1:
                time.sleep(0.1)  # 连续滑动间隔减少到0.1秒

def category_down(times=1, after_delay=AFTER_SLIDE_DELAY):
    """分类栏向下滑动"""
    for i in range(times):
        print(f"分类栏向下滑动 ({i+1}/{times})")
        slide(CATEGORY_DOWN[0], CATEGORY_DOWN[1], DEFAULT_DURATION,
              after_delay if i == times-1 else 0.2)
        if i < times - 1:
            time.sleep(0.2)  # 连续滑动间隔减少到0.2秒

def category_up(times=1, after_delay=AFTER_SLIDE_DELAY):
    """分类栏向上滑动"""
    for i in range(times):
        print(f"分类栏向上滑动 ({i+1}/{times})")
        slide(CATEGORY_UP[0], CATEGORY_UP[1], DEFAULT_DURATION,
              after_delay if i == times-1 else 0.2)
        if i < times - 1:
            time.sleep(0.2)  # 连续滑动间隔减少到0.2秒

def price_down(times=1, after_delay=AFTER_SLIDE_DELAY):
    """价格区域向下滑动"""
    for i in range(times):
        print(f"价格区域向下滑动 ({i+1}/{times})")
        slide(PRICE_DOWN[0], PRICE_DOWN[1], DEFAULT_DURATION,
              after_delay if i == times-1 else 0.2)
        if i < times - 1:
            time.sleep(0.2)  # 连续滑动间隔减少到0.2秒

def price_up(times=1, after_delay=AFTER_SLIDE_DELAY):
    """价格区域向上滑动"""
    for i in range(times):
        print(f"价格区域向上滑动 ({i+1}/{times})")
        slide(PRICE_UP[0], PRICE_UP[1], DEFAULT_DURATION,
              after_delay if i == times-1 else 0.2)
        if i < times - 1:
            time.sleep(0.2)  # 连续滑动间隔减少到0.2秒

def execute_operation(operation_type, times):
    """执行指定类型的操作"""
    if operation_type == 1:
        print(f"执行: 物品列表向下滑动 {times} 次")
        market_down(times)
    elif operation_type == 2:
        print(f"执行: 物品列表向上滑动 {times} 次")
        market_up(times)
    elif operation_type == 3:
        print(f"执行: 分类栏向下滑动 {times} 次")
        category_down(times)
    elif operation_type == 4:
        print(f"执行: 分类栏向上滑动 {times} 次")
        category_up(times)
    elif operation_type == 5:
        print(f"执行: 价格区域向下滑动 {times} 次")
        price_down(times)
    elif operation_type == 6:
        print(f"执行: 价格区域向上滑动 {times} 次")
        price_up(times)
    elif operation_type == 7:
        print("执行: 测试点击阻力点")
        click_friction_point()
    elif operation_type == 8:
        print(f"执行: 物品识别补偿移动 {times} 次")
        compensation_move(times)
    else:
        print(f"无效的操作类型: {operation_type}")

def interactive_mode():
    """交互模式"""
    print("\n请选择操作:")
    print("1-6: 选择滑动操作 (所有滑动操作都会点击阻力点)")
    print("  1. 物品列表向下滑动 (包含阻力点点击)")
    print("  2. 物品列表向上滑动 (包含阻力点点击)")
    print("  3. 分类栏向下滑动 (包含阻力点点击)")
    print("  4. 分类栏向上滑动 (包含阻力点点击)")
    print("  5. 价格区域向下滑动 (包含阻力点点击)")
    print("  6. 价格区域向上滑动 (包含阻力点点击)")
    print("7. 测试点击阻力点")
    print("8. 测试补偿移动(包含阻力点点击)")
    print("q. 退出")
    
    choice = input("请输入选项: ")
    
    if choice.lower() == 'q':
        print("退出程序")
        return False
    
    if choice == '8':
        # 进入补偿移动测试子菜单
        while True:
            print("\n补偿移动测试 (每次滑动后都会点击阻力点):")
            print("1. 测试第一次补偿移动 (上滑+阻力点)")
            print("2. 测试第二次补偿移动 (长距离下滑+阻力点)")
            print("3. 测试第三次补偿移动 (标准下滑+阻力点)")
            print("4. 测试第四次补偿移动 (连续向上滑动+阻力点)")
            print("5. 测试第五次补偿移动 (模拟正常下滑+阻力点)")
            print("6. 测试补偿移动完整循环 (1-5次)")
            print("q. 返回主菜单")
            
            sub_choice = input("请选择补偿移动类型: ")
            
            if sub_choice.lower() == 'q':
                break
                
            try:
                if sub_choice == '5':
                    # 测试第五次补偿移动
                    compensation_move(1, AFTER_SLIDE_DELAY, 5, 2)  # 使用normal_scroll_times=2作为测试
                elif sub_choice == '6':
                    # 测试完整循环
                    print("执行补偿移动完整循环 (1-5次)...")
                    for i in range(1, 6):
                        compensation_move(1, AFTER_SLIDE_DELAY, i, 2)  # 使用normal_scroll_times=2作为测试
                        if i < 5:
                            time.sleep(0.5)  # 每次尝试之间的间隔
                else:
                    attempt_number = int(sub_choice)
                    if 1 <= attempt_number <= 4:
                        compensation_move(1, AFTER_SLIDE_DELAY, attempt_number)
                    else:
                        print("无效选项，请输入1-6或q")
            except ValueError:
                print("输入无效，请输入1-6或q")
        return True
    
    try:
        operation_type = int(choice)
        if operation_type == 7:
            execute_operation(operation_type, 1)
        elif 1 <= operation_type <= 6:
            times = int(input("滑动/移动次数: ") or "1")
            execute_operation(operation_type, times)
        else:
            print("无效选项")
    except ValueError:
        print("输入无效")
    
    return True

if __name__ == "__main__":
    print("现代战舰滑动工具")
    print("请确保设备已通过ADB连接")
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 如果提供了命令行参数，优先使用命令行参数
        try:
            cmd_operation_type = int(sys.argv[1])
            cmd_times = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            execute_operation(cmd_operation_type, cmd_times)
            sys.exit(0)
        except (ValueError, IndexError):
            print("命令行参数无效，格式: python SimpleScroll.py [操作类型1-8] [滑动次数]")
            sys.exit(1)
    
    # 尝试自动设置设备ID
    if not DEVICE_ID:
        devices = ADBHelper.getDevicesList()
        if devices:
            if len(devices) == 1:
                set_device_id(devices[0])
            else:
                print(f"检测到多个设备: {devices}")
                if AUTO_MODE:
                    print(f"自动模式下选择第一个设备: {devices[0]}")
                    set_device_id(devices[0])
                else:
                    idx = input(f"请选择设备索引(0-{len(devices)-1}): ")
                    try:
                        device_idx = int(idx)
                        if 0 <= device_idx < len(devices):
                            set_device_id(devices[device_idx])
                        else:
                            print("无效的设备索引")
                    except:
                        print("输入无效，请手动设置设备ID")
        else:
            print("未检测到设备，请手动设置设备ID")
            if AUTO_MODE:
                print("无法以自动模式继续，退出")
                sys.exit(1)
    
    # 根据模式决定是否使用配置值或交互
    if AUTO_MODE:
        print(f"以自动模式运行，操作类型: {OPERATION_TYPE}，滑动次数: {SLIDE_TIMES}")
        execute_operation(OPERATION_TYPE, SLIDE_TIMES)
    else:
        # 交互式菜单循环
        running = True
        while running:
            running = interactive_mode() 