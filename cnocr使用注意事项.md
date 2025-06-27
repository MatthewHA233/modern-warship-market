# CNOCR 使用注意事项

## 关键发现：导入顺序问题

在使用 CNOCR 库时，发现了一个重要的问题：**导入顺序会影响 CNOCR 的正常工作**。

## 问题现象

当按照以下顺序导入模块时，CNOCR 会失败：
```python
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication
import cnocr  # 在其他模块之后导入会失败
```

## 解决方案

**必须将 CNOCR 的导入放在最前面**：
```python
import cnocr  # 必须放在最前面
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication
```

## 测试验证

### 错误的导入顺序
```bash
py -c "import cv2; import numpy as np; from PyQt5.QtWidgets import QApplication; import cnocr; print('所有模块导入成功')"
```
这样会导致 CNOCR 导入失败。

### 正确的导入顺序
```bash
py -c "import cnocr; import cv2; import numpy as np; from PyQt5.QtWidgets import QApplication; print('修改导入顺序后成功')"
```
这样可以正常工作。

## 推荐做法

1. **总是将 CNOCR 放在导入列表的最前面**
2. **在使用多个图像处理库时，优先导入 CNOCR**
3. **避免在运行时动态导入 CNOCR**

## 可能的原因

这个问题可能与以下因素有关：
- OpenCV 和 CNOCR 的底层依赖冲突
- PyQt5 的 GUI 初始化可能影响 CNOCR 的模型加载
- 不同库对 GPU/CUDA 资源的竞争

## 项目中的实际应用

在代肝脚本项目中，通过调整导入顺序解决了 CNOCR 无法正常工作的问题：

```python
# 修改前（有问题）
import cv2
import numpy as np
from PyQt5.QtWidgets import *
import cnocr

# 修改后（正常工作）
import cnocr  # 放在最前面
import cv2
import numpy as np
from PyQt5.QtWidgets import *
```

## 注意事项

- 这个问题具有环境相关性，在不同的系统配置下可能表现不同
- 如果遇到类似的库冲突问题，优先尝试调整导入顺序
- 建议在项目开始时就确定正确的导入顺序，避免后期调试困难 