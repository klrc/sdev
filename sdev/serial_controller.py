import serial
import time
import sys
import threading
import queue
import re
from loguru import logger

CTRL_C = chr(0x03)

class SerialController:
    """异步串口控制器，使用后台线程读取串口数据"""
    
    def __init__(self, serial_port="/dev/ttyUSB0", baudrate=115200, log_level="DEBUG", mcp_mode=False):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_connected = False
        self.mcp_mode = mcp_mode  # MCP模式下禁用终端输出
        
        # 异步处理相关
        self.read_thread = None
        self.output_queue = queue.Queue()
        self.stop_reading = False
        self.last_message = None
        
        # 设置调试模式
        logger.remove()
        if not mcp_mode:  # MCP模式下禁用日志输出
            logger.add(sys.stdout, level=log_level, colorize=True)

    def _remove_ansi_codes(self, text):
        """移除文本中的ANSI转义码"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _serial_reader(self):
        """后台线程：持续读取串口数据到队列"""
        while not self.stop_reading and self.serial_conn and self.serial_conn.is_open:
            try:
                line = self.serial_conn.readline()
                if line:
                    try:
                        decoded_line = line.decode('utf-8').strip()
                        if decoded_line:
                            self.output_queue.put(decoded_line)
                            self.last_message = decoded_line
                    except UnicodeDecodeError:
                        continue
            except Exception as e:
                logger.debug(f"串口读取异常: {e}")
                break

    def connect(self):
        """连接串口并启动后台读取线程"""
        if self.is_connected:
            return True
            
        try:
            self.serial_conn = serial.Serial(self.serial_port, self.baudrate, timeout=0.1)
            
            if not self.serial_conn.is_open:
                raise Exception(f"无法打开串口 {self.serial_port}")
            
            # 启动后台读取线程
            self.stop_reading = False
            self.read_thread = threading.Thread(target=self._serial_reader, daemon=True)
            self.read_thread.start()
            
            self.is_connected = True
            logger.success(f"串口连接成功: {self.serial_port}@{self.baudrate}")
            return True
            
        except Exception as e:
            logger.error(f"串口连接失败: {e}")
            return False

    def disconnect(self):
        """断开串口连接并停止后台线程"""
        if not self.is_connected:
            return

        # 执行退出清理命令，多次发送确保中断任何运行中的程序
        self.execute_command(CTRL_C, " #")

        if not self.mcp_mode:
            print() # 强制换行
        try:
            # 停止后台读取线程
            self.stop_reading = True
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=1)
            
            # 关闭串口
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                
            self.is_connected = False
            logger.success("串口连接已断开")
            
        except Exception as e:
            logger.error(f"断开连接时出错: {e}")

    def get_queue_size(self):
        """获取当前队列中的数据数量"""
        return self.output_queue.qsize()

    def clear_queue(self):
        """清空输出队列"""
        cleared_count = 0
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        
        if cleared_count > 0:
            logger.debug(f"清空队列，丢弃 {cleared_count} 条消息")

    def send(self, command):
        """发送命令到串口"""
        if not self.is_connected or not self.serial_conn:
            logger.error("串口未连接")
            return False
        
        try:
            self.serial_conn.write((command + "\n").encode('utf-8'))
            self.serial_conn.flush()
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False

    def reap(self, pattern=None, timeout_seconds=None, highlight_cmd=False):
        """从队列读取数据直到找到指定pattern或超时"""
        if not self.is_connected:
            logger.error("串口未连接")
            return None
        
        start_time = time.time()
        is_first_line = True
        
        logger.debug(f"等待pattern: {pattern}, 队列当前大小: {self.get_queue_size()}")
        
        while timeout_seconds is None or time.time() - start_time < timeout_seconds:
            try:
                # 非阻塞获取队列数据
                line = self.output_queue.get(timeout=0.1)
                
                if not self.mcp_mode:  # 仅在非MCP模式下输出到终端
                    if is_first_line:
                        if highlight_cmd: # 粉色高亮 输入命令回显
                            print(f"\033[95m{line}\033[0m")
                        is_first_line = False
                    elif pattern and pattern in line: # 绿色高亮 命令匹配pattern
                        clean_line = self._remove_ansi_codes(line)  
                        highlighted_line = clean_line.replace(pattern, f"\033[32m{pattern}\033[90m")
                        highlighted_line = f"\033[90m{highlighted_line}\033[0m"
                        print(highlighted_line, end=" ")
                    else: # 浅灰色 其他回显
                        clean_line = self._remove_ansi_codes(line)
                        print(f"\033[90m{clean_line}\033[0m")

                yield line  # 允许外部迭代获取数据

                # 检查pattern匹配（无论是否MCP模式都要检查）
                if pattern and pattern in line:
                    logger.debug(f"找到pattern: {pattern}")
                    if not self.mcp_mode and not pattern.endswith(" #"): # 不常见的pattern匹配符，大概率需要输出换行
                        print()
                    return
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.debug(f"队列读取异常: {e}")
                continue
        
        # 超时处理
        if pattern:
            logger.debug(f"等待pattern超时: {pattern}, 最终队列大小: {self.get_queue_size()}")
            raise TimeoutError(f"等待pattern '{pattern}' 超时")
        

    def wait_for(self, pattern, timeout_seconds=None, highlight_cmd=False, as_generator=False):
        if as_generator:
            return self.reap(pattern, timeout_seconds, highlight_cmd)
        else:
            try:
                result = []
                for line in self.reap(pattern, timeout_seconds, highlight_cmd):
                    result.append(line)
            except TimeoutError:
                logger.error(f"获取命令结果超时")
                return None                
            return result
            

    def execute_command(self, command, pattern=" #", timeout=None, as_generator=False):
        """
        执行命令 - 统一的命令执行接口
        
        Args:
            command: 要执行的命令
            pattern: 等待的完成标志 (默认: " #" 命令提示符)
            timeout: 超时时间(秒)
            
        Returns:
            命令输出结果列表，失败返回None
        """
        logger.debug(f"执行命令: {command}, 队列大小: {self.get_queue_size()}")
        
        # 清空队列中的残留数据（主要是提示符）
        self.clear_queue()
        
        # 发送命令
        if not self.send(command):
            return None
        
        # 等待响应
        result = self.wait_for(pattern, timeout, highlight_cmd=True, as_generator=as_generator)            
        return result


class Demoboard(SerialController):
    """
    抽象的演示板控制器基类
    定义了通用的初始化和配置流程，具体的芯片配置由子类实现
    """

    cli_prompt = " #"
    cli_startup_done_flag = "Processing /etc/profile... Done"
    
    def __init__(self, serial_port, baudrate=115200, log_level="INFO", mcp_mode=False):
        """
        初始化开发板控制器
        
        Args:
            serial_port: 串口地址 (默认: /dev/ttyUSB0)
            baudrate: 波特率 (默认: 115200)
            log_level: 日志级别 (默认: INFO)
            auto_mount_nfs: 是否自动挂载NFS (默认: True)
            auto_loadko: 是否自动加载驱动 (默认: True)
            mcp_mode: 是否为MCP模式 (默认: False)
        """
        super().__init__(serial_port, baudrate, log_level, mcp_mode)
        
        # 连接串口
        self.connect()

        # 确保命令行状态
        result = self.execute_command(CTRL_C, self.cli_prompt, 1, as_generator=False)
        if result is None:
            self.wait_for(self.cli_startup_done_flag)

        # 校正回显
        print()
        self.wait_for(self.cli_prompt)
    
    def close(self):
        """关闭连接"""
        self.disconnect()
    
    def __enter__(self):
        """上下文管理器支持"""
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """上下文管理器退出"""
        self.close()


if __name__ == "__main__":
    with Demoboard("/dev/ttyUSB0") as board:
        board.execute_command("pwd")
        board.execute_command("lsmod | grep nnp")
