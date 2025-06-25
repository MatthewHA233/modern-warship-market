# 游戏操作配置文件

# 移动控制坐标
MOVEMENT_CONTROLS = {
    'up': (442, 702),      # 上 - 点按
    'down': (442, 917),    # 下 - 点按  
    'left': (237, 807),    # 左 - 长按
    'right': (680, 813)    # 右 - 长按
}

# 武器发射坐标
WEAPON_CONTROLS = {
    '1': (2049, 717),   # 1号武器
    '2': (1977, 842),   # 2号武器
    '3': (2050, 982),   # 3号武器
    '4': (2240, 987)    # 4号武器
}

# 特殊功能坐标
SPECIAL_CONTROLS = {
    'heal': (1125, 973),    # 回血 - Q键
    'decoy': (1269, 982)    # 热诱弹 - E键
}

# 视角控制参数
VIEW_CONTROL = {
    'slow_speed': 200,      # 慢速视角移动速度(毫秒)
    'fast_speed': 100,      # 快速视角移动速度(毫秒)
    'swipe_distance': 300   # 滑动距离(像素)
}

# 按键映射
KEY_MAPPING = {
    # 移动控制
    'w': 'up',
    's': 'down', 
    'a': 'left',
    'd': 'right',
    
    # 武器控制
    '1': '1',
    '2': '2',
    '3': '3', 
    '4': '4',
    
    # 特殊功能
    'q': 'heal',
    'e': 'decoy',
    
    # 视角控制模式
    'z': 'view_slow',
    'x': 'view_fast',
    
    # 视角方向控制
    'up': 'view_up',
    'down': 'view_down',
    'left': 'view_left',
    'right': 'view_right'
}

# 操作类型定义
ACTION_TYPES = {
    'tap': 'tap',           # 点按
    'long_press': 'long_press',  # 长按
    'swipe': 'swipe',       # 滑动
    'view_control': 'view_control'  # 视角控制
}

# 默认参数
DEFAULT_PARAMS = {
    'tap_duration': 50,         # 默认点按持续时间(毫秒)
    'long_press_duration': 500, # 默认长按持续时间(毫秒)
    'swipe_duration': 300,      # 默认滑动持续时间(毫秒)
    'view_swipe_distance': 300, # 视角滑动距离
    'quick_tap_threshold': 150  # 快速点击阈值(毫秒)，低于此值认为是快速点击
}

# 屏幕中心点(用于视角控制的起始点)
SCREEN_CENTER = (1280, 720)  # 假设2560x1440分辨率的中心点

# ADB操作超时设置
ADB_TIMEOUT = {
    'tap': 1.0,        # 点按操作超时(秒)
    'long_press': 2.0, # 长按操作超时(秒)
    'swipe': 1.5,      # 滑动操作超时(秒)
    'continuous': 0.5  # 连续操作超时(秒)
} 