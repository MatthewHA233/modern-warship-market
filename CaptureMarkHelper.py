# 标点截取工具 Author By Hanmin 2022.01
# 请参考使用文档使用本工具

import cv2, tkinter, os
import tkinter.simpledialog
import ADBHelper

# 修改以下参数来运行

# 原图缩放比例，用于展示在窗口里
scale = 0.6

# 截图保存路径，以/结束
save_file_path = "./templates/"

# py变量字典文件
pos_img_dict = "./templates/modern_warship/ResourceDictionary.py"

# 动作类型 1=截图  2=标点  3=标线（取起终点组成向量） 4=标记区域
action = 2

# 图片来源替换输入你的did
ADBHelper.screenCapture("Y57XRWSS8PH6W84L", "home_screen.png")
img_file = "./home_screen.png"


# ===================================================
# 以下部分可以不改动

# 检查并创建保存目录
if not os.path.exists(save_file_path):
    try:
        os.makedirs(save_file_path)
        print(f"已创建目录: {save_file_path}")
    except Exception as e:
        print(f"创建目录失败: {e}")
        save_file_path = "./"  # 如果创建失败则使用当前目录
        print(f"将使用当前目录作为保存路径: {save_file_path}")

# 检查并创建变量字典文件的目录
dict_dir = os.path.dirname(pos_img_dict)
if not os.path.exists(dict_dir) and dict_dir:
    try:
        os.makedirs(dict_dir)
        print(f"已创建目录: {dict_dir}")
    except Exception as e:
        print(f"创建字典文件目录失败: {e}")
        pos_img_dict = "./testDict.py"  # 如果创建失败则使用当前目录
        print(f"将使用当前目录的testDict.py文件: {pos_img_dict}")

def isVarExist(varName):
    if os.path.exists(pos_img_dict):
        with open(pos_img_dict, 'r', encoding='utf-8') as f:
            str = f.read()
            if varName in str:
                return True
            else:
                return False
    else:
        return False


# type=动作类型 1=截图  2=标点  3=标线（取起终点组成向量） 4=标记区域
def createVar(varName, value, type):
    try:
        # 确保变量字典文件所在目录存在
        dict_dir = os.path.dirname(pos_img_dict)
        if dict_dir and not os.path.exists(dict_dir):
            os.makedirs(dict_dir)
            print(f"已创建目录: {dict_dir}")
        
        # 写入变量
        with open(pos_img_dict, 'a+', encoding='utf-8') as f:
            if type == 1:
                f.write(varName + " = \"" + value + "\"\n")
            elif type == 2:
                f.write(varName + " = " + str(value) + "\n")
            elif type == 3:
                f.write(varName + " = " + str(value) + "\n")
            elif type == 4:
                f.write(varName + " = " + str(value) + "\n")
        print(f"变量 {varName} 已写入文件: {pos_img_dict}")
    except Exception as e:
        print(f"写入变量到文件时发生错误: {e}")
        # 尝试写入到当前目录的备用文件
        try:
            backup_file = "./testDict.py"
            with open(backup_file, 'a+', encoding='utf-8') as f:
                if type == 1:
                    f.write(varName + " = \"" + value + "\"\n")
                elif type == 2:
                    f.write(varName + " = " + str(value) + "\n")
                elif type == 3:
                    f.write(varName + " = " + str(value) + "\n")
                elif type == 4:
                    f.write(varName + " = " + str(value) + "\n")
            print(f"变量 {varName} 已写入备用文件: {backup_file}")
        except Exception as e2:
            print(f"写入备用文件时也发生错误: {e2}")
            raise e2

def draw_Rect(event, x, y, flags, param):
    global drawing, startPos, stopPos
    if event == cv2.EVENT_LBUTTONDOWN:  # 响应鼠标按下
        drawing = True
        startPos = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE:  # 响应鼠标移动
        if drawing == True:
            img = img_source.copy()
            cv2.rectangle(img, startPos, (x, y), (0, 255, 0), 2)
            cv2.imshow('image', img)
    elif event == cv2.EVENT_LBUTTONUP:  # 响应鼠标松开
        drawing = False
        stopPos = (x, y)
    elif event == cv2.EVENT_RBUTTONUP:
        if startPos == (0, 0) and stopPos == (0, 0):
            return
        x0, y0 = startPos
        x1, y1 = stopPos
        cropped = img_source[y0:y1, x0:x1]  # 裁剪坐标为[y0:y1, x0:x1]
        res = tkinter.simpledialog.askstring(title="输入", prompt="请输入图片变量名：（存储路径为" + save_file_path + "）",
                                             initialvalue="")
        if res is not None:
            if isVarExist(res):
                tkinter.simpledialog.messagebox.showerror("错误", "该变量名已存在，请更换一个或手动去文件中删除！")
            else:
                # 确保保存路径存在
                try:
                    save_path = save_file_path + res + ".png"
                    # 再次检查目录是否存在
                    save_dir = os.path.dirname(save_path)
                    if save_dir and not os.path.exists(save_dir):
                        os.makedirs(save_dir)
                        print(f"已创建目录: {save_dir}")
                    
                    # 保存图片并验证
                    cv2.imwrite(save_path, cropped)
                    if os.path.exists(save_path):
                        createVar(res, save_path, 1)
                        tkinter.simpledialog.messagebox.showinfo("提示", f"创建完成！图片已保存至: {save_path}")
                    else:
                        # 保存失败，尝试保存到当前目录
                        fallback_path = "./" + res + ".png"
                        cv2.imwrite(fallback_path, cropped)
                        createVar(res, fallback_path, 1)
                        tkinter.simpledialog.messagebox.showinfo("提示", f"保存到指定路径失败，已保存至当前目录: {fallback_path}")
                except Exception as e:
                    # 发生异常，打印错误并尝试保存到当前目录
                    print(f"保存图片时发生错误: {e}")
                    try:
                        fallback_path = "./" + res + ".png"
                        cv2.imwrite(fallback_path, cropped)
                        createVar(res, fallback_path, 1)
                        tkinter.simpledialog.messagebox.showinfo("提示", f"保存到指定路径失败，已保存至当前目录: {fallback_path}")
                    except Exception as e2:
                        tkinter.simpledialog.messagebox.showerror("错误", f"保存图片失败: {e2}")
    elif event == cv2.EVENT_MBUTTONUP:
        if startPos == (0, 0) and stopPos == (0, 0):
            return
        x0, y0 = startPos
        x1, y1 = stopPos
        cropped = img_source[y0:y1, x0:x1]  # 裁剪坐标为[y0:y1, x0:x1]
        cv2.imshow('cropImage', cropped)
        cv2.waitKey(0)


def draw_Point(event, x, y, flags, param):
    global drawing, startPos, stopPos
    if event == cv2.EVENT_LBUTTONDOWN:  # 响应鼠标按下
        drawing = True
        startPos = (x, y)
        img = img_source.copy()
        cv2.circle(img, startPos, 2, (0, 255, 0), 2)
        cv2.putText(img, "Point:" + str(startPos), (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 3)
        print("Point:" + str(startPos))
        cv2.imshow('image', img)
    elif event == cv2.EVENT_RBUTTONUP:
        if startPos == (0, 0):
            return
        res = tkinter.simpledialog.askstring(title="输入", prompt="请输入坐标 " + str(startPos) + " 变量名：", initialvalue="")
        if res is not None:
            if isVarExist(res):
                tkinter.simpledialog.messagebox.showerror("错误", "该变量名已存在，请更换一个或手动去文件中删除！")
            else:
                createVar(res, startPos, 2)
                tkinter.simpledialog.messagebox.showinfo("提示", "创建完成！")


def draw_Line(event, x, y, flags, param):
    global drawing, startPos, stopPos
    if event == cv2.EVENT_LBUTTONDOWN:  # 响应鼠标按下
        drawing = True
        startPos = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE:  # 响应鼠标移动
        if drawing == True:
            img = img_source.copy()
            cv2.line(img, startPos, (x, y), (0, 255, 0), 2)
            cv2.imshow('image', img)
    elif event == cv2.EVENT_LBUTTONUP:  # 响应鼠标松开
        drawing = False
        stopPos = (x, y)
        print("startPoint:" + str(startPos) + " stopPoint:" + str(stopPos))
    elif event == cv2.EVENT_RBUTTONUP:
        if startPos == (0, 0) and stopPos == (0, 0):
            return
        res = tkinter.simpledialog.askstring(title="输入", prompt="请输入开始坐标 " + str(startPos) + " 到结束坐标 " + str(
            stopPos) + " 组成向量的变量名：", initialvalue="")
        if res is not None:
            if isVarExist(res):
                tkinter.simpledialog.messagebox.showerror("错误", "该变量名已存在，请更换一个或手动去文件中删除！")
            else:
                createVar(res, (startPos, stopPos), 3)
                tkinter.simpledialog.messagebox.showinfo("提示", "创建完成！")


def draw_Rect_Pos(event, x, y, flags, param):
    global drawing, startPos, stopPos
    if event == cv2.EVENT_LBUTTONDOWN:  # 响应鼠标按下
        drawing = True
        startPos = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE:  # 响应鼠标移动
        if drawing == True:
            img = img_source.copy()
            cv2.rectangle(img, startPos, (x, y), (0, 255, 0), 2)
            cv2.imshow('image', img)
    elif event == cv2.EVENT_LBUTTONUP:  # 响应鼠标松开
        drawing = False
        stopPos = (x, y)
        print("startPoint:" + str(startPos) + " stopPoint:" + str(stopPos))
    elif event == cv2.EVENT_RBUTTONUP:
        if startPos == (0, 0) and stopPos == (0, 0):
            return
        x0, y0 = startPos
        x1, y1 = stopPos
        res = tkinter.simpledialog.askstring(title="输入", prompt="请输入矩形范围变量名：",
                                             initialvalue="")
        if res is not None:
            if isVarExist(res):
                tkinter.simpledialog.messagebox.showerror("错误", "该变量名已存在，请更换一个或手动去文件中删除！")
            else:
                try:
                    createVar(res, (startPos, stopPos), 4)
                    tkinter.simpledialog.messagebox.showinfo("提示", f"创建完成！矩形区域：{startPos} 到 {stopPos}")
                except Exception as e:
                    print(f"创建矩形区域变量时发生错误: {e}")
                    tkinter.simpledialog.messagebox.showerror("错误", f"创建变量失败: {e}")
    elif event == cv2.EVENT_MBUTTONUP:
        if startPos == (0, 0) and stopPos == (0, 0):
            return
        x0, y0 = startPos
        x1, y1 = stopPos
        cropped = img_source[y0:y1, x0:x1]  # 裁剪坐标为[y0:y1, x0:x1]
        cv2.imshow('cropImage', cropped)
        cv2.waitKey(0)

drawing = False
startPos = (0, 0)
stopPos = (0, 0)

# 初始化前检查并创建目录
if not os.path.exists(save_file_path):
    try:
        os.makedirs(save_file_path)
        print(f"已创建模板目录: {save_file_path}")
    except Exception as e:
        print(f"创建模板目录失败: {e}")
        # 如果创建失败，不修改路径，但给出警告

# 截图保存到templates目录
try:
    screen_path = save_file_path + "home_screen.png"
    ADBHelper.screenCapture("Y57XRWSS8PH6W84L", screen_path)
    if os.path.exists(screen_path):
        img_file = screen_path
        print(f"截图已保存到: {img_file}")
    else:
        print(f"截图保存到 {screen_path} 失败，使用原始路径")
except Exception as e:
    print(f"截图时发生错误: {e}")

# 如果指定路径的图片不存在，则使用默认路径
if not os.path.exists(img_file):
    img_file = "./home_screen.png"
    print(f"使用默认路径的截图: {img_file}")

img_source = cv2.imread(img_file)
img = img_source.copy()

root = tkinter.Tk()
root.title('dialog')
root.resizable(0, 0)
root.withdraw()

h_src, w_src, tongdao = img.shape
w = int(w_src * scale)
h = int(h_src * scale)
cv2.namedWindow('image', cv2.WINDOW_NORMAL)
cv2.resizeWindow("image", w, h)
if action == 1:
    cv2.setMouseCallback('image', draw_Rect)
elif action == 2:
    cv2.setMouseCallback('image', draw_Point)
elif action == 3:
    cv2.setMouseCallback('image', draw_Line)
elif action == 4:
    cv2.setMouseCallback('image', draw_Rect_Pos)

cv2.imshow('image', img)
cv2.waitKey(0)
cv2.destroyAllWindows()

root.destroy()
