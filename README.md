# SDEV

串口控制器工具包

## 安装

```bash
pip install sdev
```

## 使用方法

```python
from sdev import SerialController

# 创建串口控制器实例
controller = SerialController(serial_port="/dev/ttyUSB0", baudrate=115200)

# 连接串口
if controller.connect():
    print("连接成功")
    
    # 执行命令
    result = controller.execute_command("ls")
    print(result)
    
    # 断开连接
    controller.disconnect()
else:
    print("连接失败")
```

## 功能特性

- 支持串口通信
- 命令执行和响应处理
- 自动ANSI转义码清理
- 连接状态管理

## 依赖

- Python >= 3.7
- pyserial >= 3.5
- loguru >= 0.6.0 