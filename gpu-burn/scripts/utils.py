#!/usr/bin/env python3
"""
GPU Analysis Utility Functions
统一工具函数模块
"""

import os
import re
import time
import logging
import subprocess
from typing import List, Dict, Any, Optional, Tuple, Union
from functools import wraps
from pathlib import Path

from config import get_logger, get_config


def monitor_performance(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger()
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            logger.debug(f"{func.__name__} took {end_time - start_time:.2f} seconds")
            return result
        except Exception as e:
            end_time = time.time()
            logger.error(f"{func.__name__} failed after {end_time - start_time:.2f} seconds: {e}")
            raise
    
    return wrapper


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger()
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}, retrying in {delay}s")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
            
            raise last_exception
        
        return wrapper
    return decorator


def validate_gpu_data(gpu_data: Dict[str, Any]) -> bool:
    """验证GPU数据的完整性和有效性"""
    logger = get_logger()
    config = get_config()
    
    if not config.validation_config.get('enable_validation', True):
        return True
    
    required_fields = ['gpu_id', 'sm_utilization', 'memory_utilization', 'temperature', 'power']
    
    # 检查必需字段
    for field in required_fields:
        if field not in gpu_data:
            logger.error(f"Missing required field: {field}")
            return False
    
    # 验证数值范围
    validation_rules = {
        'sm_utilization': (config.validation_config.get('min_utilization', 0.0), 
                          config.validation_config.get('max_utilization', 100.0)),
        'memory_utilization': (config.validation_config.get('min_utilization', 0.0), 
                              config.validation_config.get('max_utilization', 100.0)),
        'temperature': (config.validation_config.get('min_temperature', 0.0), 
                       config.validation_config.get('max_temperature', 100.0)),
        'power': (config.validation_config.get('min_power', 0.0), 
                 config.validation_config.get('max_power', 1000.0))
    }
    
    for field, (min_val, max_val) in validation_rules.items():
        value = gpu_data.get(field, 0)
        if not isinstance(value, (int, float)):
            logger.error(f"Invalid type for {field}: {type(value)}")
            return False
        
        if not min_val <= value <= max_val:
            logger.warning(f"{field} value {value} is outside expected range [{min_val}, {max_val}]")
    
    return True


def validate_file_path(file_path: str, must_exist: bool = True, must_be_readable: bool = True) -> bool:
    """验证文件路径的安全性"""
    logger = get_logger()
    
    try:
        path = Path(file_path).resolve()
        
        # 检查路径遍历攻击
        if '..' in str(path):
            logger.error(f"Path traversal detected: {file_path}")
            return False
        
        # 检查文件是否存在
        if must_exist and not path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False
        
        # 检查读取权限
        if must_be_readable and path.exists() and not os.access(str(path), os.R_OK):
            logger.error(f"No read permission for: {file_path}")
            return False
        
        return True
    
    except Exception as e:
        logger.error(f"Error validating path {file_path}: {e}")
        return False


def safe_file_operation(operation_name: str):
    """安全文件操作装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger()
            try:
                return func(*args, **kwargs)
            except FileNotFoundError as e:
                logger.error(f"{operation_name} failed - file not found: {e}")
                return None
            except PermissionError as e:
                logger.error(f"{operation_name} failed - permission denied: {e}")
                return None
            except OSError as e:
                logger.error(f"{operation_name} failed - OS error: {e}")
                return None
            except Exception as e:
                logger.error(f"{operation_name} failed - unexpected error: {e}")
                return None
        
        return wrapper
    return decorator


@safe_file_operation("File reading")
def read_file_safely(file_path: str, encoding: str = 'utf-8') -> Optional[str]:
    """安全读取文件"""
    if not validate_file_path(file_path, must_exist=True, must_be_readable=True):
        return None
    
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        get_logger().error(f"Error reading file {file_path}: {e}")
        return None


@safe_file_operation("File writing")
def write_file_safely(file_path: str, content: str, encoding: str = 'utf-8') -> bool:
    """安全写入文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        get_logger().error(f"Error writing file {file_path}: {e}")
        return False


def parse_hosts_argument(hosts_args: Optional[List[str]]) -> Optional[set]:
    """解析主机参数，改进错误处理"""
    logger = get_logger()
    
    if not hosts_args:
        return None
    
    try:
        specified = []
        for item in hosts_args:
            if not item or not isinstance(item, str):
                logger.warning(f"Invalid host argument: {item}")
                continue
            
            # 分割并清理主机名
            hosts = [h.strip() for h in item.split(',') if h.strip()]
            specified.extend(hosts)
        
        if not specified:
            logger.warning("No valid hosts found in arguments")
            return None
        
        # 验证主机名格式
        valid_hosts = set()
        for host in specified:
            if is_valid_hostname(host):
                valid_hosts.add(host)
            else:
                logger.warning(f"Invalid hostname format: {host}")
        
        return valid_hosts if valid_hosts else None
    
    except Exception as e:
        logger.error(f"Error parsing hosts argument: {e}")
        return None


def is_valid_hostname(hostname: str) -> bool:
    """验证主机名格式"""
    if not hostname or len(hostname) > 253:
        return False
    
    # 简单的IP地址或主机名验证
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    
    return bool(re.match(ip_pattern, hostname) or re.match(hostname_pattern, hostname))


def discover_and_filter_machines(input_dir: str, hosts_filter: Optional[set] = None) -> List[str]:
    """发现和过滤机器，改进错误处理"""
    logger = get_logger()
    
    try:
        if not validate_file_path(input_dir, must_exist=True, must_be_readable=True):
            return []
        
        # 获取子目录
        subdirs = []
        for item in os.listdir(input_dir):
            item_path = os.path.join(input_dir, item)
            if os.path.isdir(item_path):
                subdirs.append(item)
        
        if not subdirs:
            logger.error("No machine directories found")
            return []
        
        # 应用主机过滤
        if hosts_filter is not None:
            before = set(subdirs)
            subdirs = [d for d in subdirs if d in hosts_filter]
            missing = sorted(hosts_filter - before)
            
            if missing:
                logger.warning(f"Specified hosts not found: {missing}")
        
        if not subdirs:
            logger.error("No machines found after filtering")
            return []
        
        logger.info(f"Found {len(subdirs)} machines: {sorted(subdirs)}")
        return sorted(subdirs)
    
    except Exception as e:
        logger.error(f"Error discovering machines: {e}")
        return []


def get_gpu_specs_dynamic() -> Dict[str, Union[int, float, str]]:
    """动态获取GPU规格，改进错误处理"""
    logger = get_logger()
    config = get_config()
    
    try:
        # 获取GPU名称
        gpu_name_cmd = ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader", "-i=0"]
        gpu_name = subprocess.check_output(gpu_name_cmd, timeout=10).decode().strip()
        
        # 获取功率限制
        power_cmd = ["nvidia-smi", "--query-gpu=power.max_limit", "--format=csv,noheader,nounits", "-i=0"]
        max_power = float(subprocess.check_output(power_cmd, timeout=10).decode().strip())
        
        # 获取温度限制
        try:
            temp_cmd = ["nvidia-smi", "--query-gpu=temperature.gpu.tlimit", "--format=csv,noheader,nounits", "-i=0"]
            max_temp = float(subprocess.check_output(temp_cmd, timeout=10).decode().strip())
        except Exception:
            max_temp = config.gpu_specs.get('max_temp', 83)
        
        # 获取时钟频率
        try:
            clock_cmd = ["nvidia-smi", "--query-gpu=clocks.max.graphics", "--format=csv,noheader,nounits", "-i=0"]
            boost_clock = float(subprocess.check_output(clock_cmd, timeout=10).decode().strip())
        except Exception:
            boost_clock = config.gpu_specs.get('boost_clock', 2620)
        
        detected_specs = {
            'max_power': max_power,
            'max_temp': max_temp,
            'boost_clock': boost_clock,
            'expected_gflops': config.gpu_specs.get('expected_gflops', 0),
            'gpu_name': gpu_name
        }
        
        logger.info(f"Detected GPU specs for {gpu_name}: {detected_specs}")
        return detected_specs
    
    except subprocess.TimeoutExpired:
        logger.error("GPU specs detection timed out")
        return config.gpu_specs
    except Exception as e:
        logger.error(f"Could not detect GPU specs dynamically: {e}")
        return config.gpu_specs


def create_directory_safely(dir_path: str, mode: int = 0o755) -> bool:
    """安全创建目录"""
    logger = get_logger()
    
    try:
        os.makedirs(dir_path, mode=mode, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {dir_path}: {e}")
        return False


def cleanup_old_files(directory: str, pattern: str, max_age_hours: int = 24) -> int:
    """清理旧文件"""
    logger = get_logger()
    cleaned_count = 0
    
    try:
        import glob
        from datetime import datetime, timedelta
        
        current_time = datetime.now()
        max_age = timedelta(hours=max_age_hours)
        
        for file_path in glob.glob(os.path.join(directory, pattern)):
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if current_time - file_time > max_age:
                    os.remove(file_path)
                    cleaned_count += 1
                    logger.debug(f"Cleaned old file: {file_path}")
            except Exception as e:
                logger.warning(f"Error cleaning file {file_path}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned {cleaned_count} old files from {directory}")
        
        return cleaned_count
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return 0

