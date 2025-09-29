"""
SDEV - 串口控制器工具包

支持MC6670和MC6357演示板的串口通信和控制。
"""

from .serial_controller import SerialController, Demoboard

__version__ = "0.1.3"
__author__ = "klrc"
__email__ = "144069824@qq.com"

__all__ = ["SerialController", "Demoboard"] 