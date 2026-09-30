import logging
import sys
from logging.handlers import RotatingFileHandler
import os
import shutil
from datetime import datetime, timedelta
import threading
import time
from configs.server_config import CLEAR_DAYS

# 日志保存路径
CURRENT_PROJECT_DIR = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
TERMINAL_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f"{CURRENT_PROJECT_DIR}_terminal_logs")

TERMINAL_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
TERMINAL_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def cleanup_old_logs(base_dir):
    """清理指定天数之前的日志文件夹"""
    if not os.path.exists(base_dir):
        return
    
    cutoff_date = datetime.now() - timedelta(days=CLEAR_DAYS)
    
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            try:
                # 尝试解析文件夹名为日期
                folder_date = datetime.strptime(item, "%Y-%m-%d")
                if folder_date < cutoff_date:
                    print(f"清理旧日志文件夹: {item_path}")
                    shutil.rmtree(item_path)
            except ValueError:
                # 如果文件夹名不是日期格式，跳过
                continue

def start_cleanup_scheduler(base_dir, check_interval=3600):
    """启动日志清理调度器"""
    def cleanup_worker():
        while True:
            try:
                cleanup_old_logs(base_dir)
            except Exception as e:
                print(f"日志清理出错: {e}")
            time.sleep(check_interval)  # 每小时检查一次
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    return cleanup_thread

def setup_terminal_logger():
    """设置终端日志记录器"""
    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # 创建按日期分类的日志目录
    date_log_dir = os.path.join(TERMINAL_LOG_DIR, current_date)
    os.makedirs(date_log_dir, exist_ok=True)
    
    # 启动日志清理调度器
    start_cleanup_scheduler(TERMINAL_LOG_DIR)
    
    # 创建终端日志记录器
    terminal_logger = logging.getLogger('terminal')
    terminal_logger.setLevel(logging.DEBUG)
    
    # 清除现有处理器
    terminal_logger.handlers.clear()
    
    # 创建不同级别的日志文件处理器
    levels = {
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING, 
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG
    }
    
    for level_name, level_value in levels.items():
        # 创建按级别分类的日志文件（在日期文件夹内）
        log_file = os.path.join(date_log_dir, f"terminal_{level_name.lower()}.log")
        handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        handler.setLevel(level_value)
        
        # 创建过滤器，只记录特定级别的日志
        class LevelFilter(logging.Filter):
            def __init__(self, level):
                self.level = level
            def filter(self, record):
                return record.levelno == self.level
        
        handler.addFilter(LevelFilter(level_value))
        
        formatter = logging.Formatter(TERMINAL_LOG_FORMAT, TERMINAL_DATE_FORMAT)
        handler.setFormatter(formatter)
        terminal_logger.addHandler(handler)
    
    # 创建包含所有级别的综合日志文件（在日期文件夹内）
    all_log_file = os.path.join(date_log_dir, "terminal_all.log")
    all_handler = RotatingFileHandler(
        all_log_file,
        maxBytes=20*1024*1024,  # 20MB
        backupCount=10,
        encoding='utf-8'
    )
    all_handler.setLevel(logging.DEBUG)
    all_formatter = logging.Formatter(TERMINAL_LOG_FORMAT, TERMINAL_DATE_FORMAT)
    all_handler.setFormatter(all_formatter)
    terminal_logger.addHandler(all_handler)
    
    return terminal_logger


def monitor_and_restore_redirection():
    """监控并自动恢复终端重定向"""
    import time
    import threading
    
    def monitor_worker():
        terminal_logger = setup_terminal_logger()
        original_stdout = sys.__stdout__
        original_stderr = sys.__stderr__
        
        while True:
            try:
                # 检查是否被重置
                if (not isinstance(sys.stdout, TerminalLogHandler) or 
                    not isinstance(sys.stderr, TerminalLogHandler)):
                    
                    
                    # 重新设置重定向
                    sys.stdout = TerminalLogHandler(terminal_logger, logging.INFO, original_stdout)
                    sys.stderr = TerminalLogHandler(terminal_logger, logging.ERROR, original_stderr)
                    
                    
                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                print(f"监控线程出错: {e}")
                time.sleep(10)
    
    monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
    monitor_thread.start()
    return monitor_thread

class TerminalLogHandler:
    """终端日志处理器，重定向stdout和stderr到日志文件"""
    
    def __init__(self, logger, level=logging.INFO, original_stream=None):
        self.logger = logger
        self.level = level
        self.original_stream = original_stream
        self.buffer = ""
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self._is_terminal_log_handler = True  # 添加标识
    
    def write(self, message):
        # 同时输出到原始终端
        if self.original_stream:
            self.original_stream.write(message)
            self.original_stream.flush()
        
        # 检查日期是否变更，如果变更则重新初始化logger
        new_date = datetime.now().strftime("%Y-%m-%d")
        if new_date != self.current_date:
            self.current_date = new_date
            # 重新设置logger以使用新的日期文件夹
            self.logger = setup_terminal_logger()
        
        # 记录到日志文件
        if message.strip():  # 忽略空行
            # 根据消息内容判断日志级别
            log_level = self._determine_log_level(message)
            
            # 使用原来的 self.logger 记录到按级别分类的日志文件
            # 创建一个临时的 logger 来避免终端重复输出
            temp_logger = logging.getLogger('terminal_temp')
            temp_logger.handlers.clear()  # 清除现有处理器
            temp_logger.setLevel(logging.DEBUG)
            temp_logger.propagate = False  # 防止传播到根logger
            
            # 复制原 logger 的所有处理器
            for handler in self.logger.handlers:
                temp_logger.addHandler(handler)
            
            # 使用临时 logger 记录日志
            temp_logger.log(log_level, message.strip())
    
    def flush(self):
        if self.original_stream:
            self.original_stream.flush()
    
    def isatty(self):
        """检查是否为终端设备"""
        if self.original_stream and hasattr(self.original_stream, 'isatty'):
            return self.original_stream.isatty()
        return False
    
    def fileno(self):
        """返回文件描述符"""
        if self.original_stream and hasattr(self.original_stream, 'fileno'):
            try:
                return self.original_stream.fileno()
            except (AttributeError, OSError):
                pass
        return None
    
    def readable(self):
        """检查是否可读"""
        return False
    
    def writable(self):
        """检查是否可写"""
        return True
    
    def seekable(self):
        """检查是否可寻址"""
        return False
    
    def encoding(self):
        """返回编码"""
        if self.original_stream and hasattr(self.original_stream, 'encoding'):
            return self.original_stream.encoding
        return 'utf-8'
    
    @property
    def mode(self):
        """返回文件模式"""
        return 'w'
    
    @property
    def name(self):
        """返回文件名"""
        if self.original_stream and hasattr(self.original_stream, 'name'):
            return self.original_stream.name
        return '<terminal_log_handler>'
    
    def _determine_log_level(self, message):
        """根据消息内容判断日志级别"""
        message_lower = message.lower()
        
        # 错误关键词
        error_keywords = ['error', 'exception', 'traceback', 'failed', 'fail', '错误', '异常', '失败']
        if any(keyword in message_lower for keyword in error_keywords):
            return logging.ERROR
        
        # 警告关键词
        warning_keywords = ['warning', 'warn', 'deprecated', '警告', '弃用']
        if any(keyword in message_lower for keyword in warning_keywords):
            return logging.WARNING
        
        # 调试关键词
        debug_keywords = ['debug', 'trace', '调试', '跟踪']
        if any(keyword in message_lower for keyword in debug_keywords):
            return logging.DEBUG
        
        # 默认为INFO级别
        return logging.INFO
