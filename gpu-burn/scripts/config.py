#!/usr/bin/env python3
"""
GPU Analysis Configuration Management
统一配置管理模块
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
from pathlib import Path


@dataclass
class GPUAnalysisConfig:
    """GPU分析配置类"""
    # 监控配置
    monitor_interval: int = 1
    save_interval: int = 30
    max_memory_samples: int = 1000
    
    # GPU规格配置
    gpu_specs: Dict[str, Union[int, float, str]] = field(default_factory=lambda: {
        'max_power': 360,
        'max_temp': 83,
        'boost_clock': 2620,
        'expected_gflops': 0,
        'gpu_name': 'Unknown GPU'
    })
    
    # 性能阈值
    performance_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'excellent_utilization': 95.0,
        'good_utilization': 90.0,
        'high_temp_warning': 80.0,
        'critical_temp': 83.0,
        'optimal_power_ratio': 0.9
    })
    
    # 日志配置
    log_level: str = 'INFO'
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_file: Optional[str] = None
    
    # 数据验证配置
    validation_config: Dict[str, Union[bool, int, float]] = field(default_factory=lambda: {
        'enable_validation': True,
        'max_utilization': 100.0,
        'min_utilization': 0.0,
        'max_temperature': 100.0,
        'min_temperature': 0.0,
        'max_power': 1000.0,
        'min_power': 0.0
    })
    
    # 错误处理配置
    error_handling: Dict[str, Union[bool, int]] = field(default_factory=lambda: {
        'max_retries': 3,
        'retry_delay': 1,
        'enable_fallback': True,
        'log_errors': True
    })
    
    @classmethod
    def from_file(cls, config_path: str) -> 'GPUAnalysisConfig':
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            print(f"Config file not found: {config_path}, using defaults")
            return cls()
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
            return cls()
    
    def save_to_file(self, config_path: str) -> None:
        """保存配置到文件"""
        try:
            config_data = {
                'monitor_interval': self.monitor_interval,
                'save_interval': self.save_interval,
                'max_memory_samples': self.max_memory_samples,
                'gpu_specs': self.gpu_specs,
                'performance_thresholds': self.performance_thresholds,
                'log_level': self.log_level,
                'log_format': self.log_format,
                'log_file': self.log_file,
                'validation_config': self.validation_config,
                'error_handling': self.error_handling
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def setup_logging(self) -> logging.Logger:
        """设置日志系统"""
        logger = logging.getLogger('gpu_analysis')
        logger.setLevel(getattr(logging, self.log_level.upper()))
        
        # 清除现有处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 创建格式化器
        formatter = logging.Formatter(self.log_format)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器（如果指定）
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger


# 全局配置实例
_config: Optional[GPUAnalysisConfig] = None
_logger: Optional[logging.Logger] = None


def get_config() -> GPUAnalysisConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = GPUAnalysisConfig()
    return _config


def set_config(config: GPUAnalysisConfig) -> None:
    """设置全局配置实例"""
    global _config
    _config = config


def get_logger() -> logging.Logger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        config = get_config()
        _logger = config.setup_logging()
    return _logger


def init_config(config_path: Optional[str] = None) -> GPUAnalysisConfig:
    """初始化配置"""
    if config_path and os.path.exists(config_path):
        config = GPUAnalysisConfig.from_file(config_path)
    else:
        config = GPUAnalysisConfig()
    
    set_config(config)
    get_logger()  # 初始化日志
    
    return config

