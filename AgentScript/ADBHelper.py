import subprocess
import time
import re

# 记录活跃的长按操作
_active_long_presses = {}

def getDevicesList():
    """获取连接的设备列表"""
    try:
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # 跳过第一行标题
            devices = []
            for line in lines:
                if '\tdevice' in line:
                    device_id = line.split('\t')[0]
                    devices.append(device_id)
            return devices
        return []
    except Exception as e:
        print(f"获取设备列表失败: {str(e)}")
        return []

def touch(device_id, pos):
    """模拟点击"""
    try:
        x, y = pos
        cmd = f"adb -s {device_id} shell input tap {x} {y}"
        subprocess.run(cmd, shell=True, capture_output=True, timeout=2)
        return True
    except Exception as e:
        print(f"点击失败: {str(e)}")
        return False

def startLongPress(device_id, pos):
    """开始长按 - 记录开始时间"""
    try:
        x, y = pos
        key = f"{device_id}_{x}_{y}"
        
        # 如果已经有相同位置的长按在进行，先结束它
        if key in _active_long_presses:
            endLongPress(device_id, pos)
        
        # 记录长按开始时间
        _active_long_presses[key] = time.time()
        
        print(f"ADB开始长按: {pos}")
        return True
    except Exception as e:
        print(f"开始长按失败: {str(e)}")
        return False

def endLongPress(device_id, pos):
    """结束长按 - 执行对应时长的长按操作"""
    try:
        x, y = pos
        key = f"{device_id}_{x}_{y}"
        
        if key not in _active_long_presses:
            return True  # 没有对应的长按在进行
        
        # 计算长按持续时间
        start_time = _active_long_presses[key]
        duration = time.time() - start_time
        duration_ms = max(100, int(duration * 1000))  # 最少100ms
        
        # 清理记录
        del _active_long_presses[key]
        
        # 执行对应时长的长按操作
        cmd = f"adb -s {device_id} shell input swipe {x} {y} {x} {y} {duration_ms}"
        subprocess.run(cmd, shell=True, capture_output=True, timeout=max(2, duration + 1))
        
        print(f"ADB执行长按: {pos}, 持续时间: {duration*1000:.0f}ms")
        return True
    except Exception as e:
        print(f"结束长按失败: {str(e)}")
        return False

def slide(device_id, start_pos, end_pos, duration):
    """模拟滑动"""
    try:
        x1, y1 = start_pos
        x2, y2 = end_pos
        cmd = f"adb -s {device_id} shell input swipe {x1} {y1} {x2} {y2} {duration}"
        subprocess.run(cmd, shell=True, capture_output=True, timeout=max(2, duration/1000 + 1))
        return True
    except Exception as e:
        print(f"滑动失败: {str(e)}")
        return False

def screenCapture(device_id, save_path):
    """截屏"""
    try:
        # 先截屏到设备
        cmd1 = f"adb -s {device_id} shell screencap -p /sdcard/screen.png"
        subprocess.run(cmd1, shell=True, capture_output=True)
        
        # 再拉取到本地
        cmd2 = f"adb -s {device_id} pull /sdcard/screen.png {save_path}"
        result = subprocess.run(cmd2, shell=True, capture_output=True)
        
        return result.returncode == 0
    except Exception as e:
        print(f"截屏失败: {str(e)}")
        return False

def isDeviceConnected(device_id):
    """检查设备是否连接"""
    devices = getDevicesList()
    return device_id in devices

def clearOperationHistory():
    """清空操作历史记录"""
    global _active_long_presses
    _active_long_presses.clear()
    print("已清空ADB操作历史记录")

def getActiveLongPresses():
    """获取当前活跃的长按操作"""
    return dict(_active_long_presses) 