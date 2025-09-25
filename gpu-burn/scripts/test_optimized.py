#!/usr/bin/env python3
"""
Test Script for Optimized GPU Analysis Tool
优化后的GPU分析工具测试脚本
"""

import unittest
import tempfile
import os
import json
import time
from unittest.mock import patch, MagicMock

# 导入优化后的模块
from config import GPUAnalysisConfig, init_config, get_config, get_logger
from utils import (
    validate_gpu_data, validate_file_path, parse_hosts_argument,
    discover_and_filter_machines, get_gpu_specs_dynamic
)
from gpu_analysis_core_optimized import (
    GPUDataValidator, parse_gpu_burn_logs, load_phase_data,
    analyze_single_gpu_baseline, analyze_all_gpu_stress
)


class TestConfigManagement(unittest.TestCase):
    """测试配置管理"""
    
    def test_config_creation(self):
        """测试配置创建"""
        config = GPUAnalysisConfig()
        self.assertEqual(config.monitor_interval, 1)
        self.assertEqual(config.save_interval, 30)
        self.assertIn('max_power', config.gpu_specs)
    
    def test_config_from_file(self):
        """测试从文件加载配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                'monitor_interval': 2,
                'save_interval': 60,
                'log_level': 'DEBUG'
            }
            json.dump(config_data, f)
            f.flush()
            
            config = GPUAnalysisConfig.from_file(f.name)
            self.assertEqual(config.monitor_interval, 2)
            self.assertEqual(config.save_interval, 60)
            self.assertEqual(config.log_level, 'DEBUG')
            
            os.unlink(f.name)
    
    def test_config_save(self):
        """测试配置保存"""
        config = GPUAnalysisConfig()
        config.monitor_interval = 5
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config.save_to_file(f.name)
            
            # 重新加载验证
            loaded_config = GPUAnalysisConfig.from_file(f.name)
            self.assertEqual(loaded_config.monitor_interval, 5)
            
            os.unlink(f.name)


class TestDataValidation(unittest.TestCase):
    """测试数据验证"""
    
    def test_valid_gpu_data(self):
        """测试有效GPU数据"""
        valid_data = {
            'gpu_id': 0,
            'sm_utilization': 95.0,
            'memory_utilization': 80.0,
            'temperature': 75.0,
            'power': 300.0
        }
        self.assertTrue(validate_gpu_data(valid_data))
    
    def test_invalid_gpu_data(self):
        """测试无效GPU数据"""
        # 缺少必需字段
        invalid_data = {
            'gpu_id': 0,
            'sm_utilization': 95.0
            # 缺少其他字段
        }
        self.assertFalse(validate_gpu_data(invalid_data))
    
    def test_gpu_data_validation_ranges(self):
        """测试GPU数据范围验证"""
        # 超出范围的利用率
        invalid_utilization = {
            'gpu_id': 0,
            'sm_utilization': 150.0,  # 超出100%
            'memory_utilization': 80.0,
            'temperature': 75.0,
            'power': 300.0
        }
        # 注意：当前实现会记录警告但返回True
        self.assertTrue(validate_gpu_data(invalid_utilization))


class TestFileOperations(unittest.TestCase):
    """测试文件操作"""
    
    def test_validate_file_path(self):
        """测试文件路径验证"""
        # 测试存在的文件
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            
            self.assertTrue(validate_file_path(f.name, must_exist=True, must_be_readable=True))
            os.unlink(f.name)
    
    def test_validate_nonexistent_file(self):
        """测试不存在的文件"""
        self.assertFalse(validate_file_path("/nonexistent/file.txt", must_exist=True))
    
    def test_validate_path_traversal(self):
        """测试路径遍历攻击防护"""
        self.assertFalse(validate_file_path("../../../etc/passwd"))


class TestHostParsing(unittest.TestCase):
    """测试主机解析"""
    
    def test_parse_hosts_argument(self):
        """测试主机参数解析"""
        # 正常情况
        hosts = ["host1,host2", "host3"]
        result = parse_hosts_argument(hosts)
        expected = {"host1", "host2", "host3"}
        self.assertEqual(result, expected)
    
    def test_parse_empty_hosts(self):
        """测试空主机列表"""
        result = parse_hosts_argument([])
        self.assertIsNone(result)
    
    def test_parse_invalid_hosts(self):
        """测试无效主机名"""
        hosts = ["valid-host", "invalid..host", "another-valid"]
        result = parse_hosts_argument(hosts)
        # 应该只包含有效的主机名
        self.assertIn("valid-host", result)
        self.assertIn("another-valid", result)
        self.assertNotIn("invalid..host", result)


class TestGPUDataValidator(unittest.TestCase):
    """测试GPU数据验证器"""
    
    def test_validate_gflops_data(self):
        """测试GFLOPS数据验证"""
        validator = GPUDataValidator()
        
        # 有效数据
        valid_data = {
            'total_gflops': 1000.0,
            'gpu_count': 2
        }
        self.assertTrue(validator.validate_gflops_data(valid_data))
        
        # 无效数据
        invalid_data = {
            'total_gflops': 1000.0
            # 缺少gpu_count
        }
        self.assertFalse(validator.validate_gflops_data(invalid_data))
    
    def test_validate_monitoring_data(self):
        """测试监控数据验证"""
        validator = GPUDataValidator()
        
        # 有效数据
        valid_data = [
            {
                'timestamp': '2024-01-01T12:00:00',
                'gpus': [
                    {
                        'gpu_id': 0,
                        'sm_utilization': 95.0,
                        'memory_utilization': 80.0,
                        'temperature': 75.0,
                        'power': 300.0
                    }
                ]
            }
        ]
        self.assertTrue(validator.validate_monitoring_data(valid_data))
        
        # 无效数据
        invalid_data = [
            {
                'timestamp': '2024-01-01T12:00:00'
                # 缺少gpus字段
            }
        ]
        self.assertFalse(validator.validate_monitoring_data(invalid_data))


class TestPerformanceOptimization(unittest.TestCase):
    """测试性能优化"""
    
    def test_monitor_performance_decorator(self):
        """测试性能监控装饰器"""
        from utils import monitor_performance
        
        @monitor_performance
        def test_function():
            time.sleep(0.01)  # 模拟工作
            return "test"
        
        result = test_function()
        self.assertEqual(result, "test")
    
    def test_retry_on_failure_decorator(self):
        """测试重试装饰器"""
        from utils import retry_on_failure
        
        call_count = 0
        
        @retry_on_failure(max_retries=3, delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            return "success"
        
        result = failing_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)


class TestMemoryOptimization(unittest.TestCase):
    """测试内存优化"""
    
    def test_streaming_data_manager(self):
        """测试流式数据管理器"""
        from monitor_gpu_optimized import StreamingDataManager
        
        manager = StreamingDataManager(max_samples=5, save_interval=3)
        
        # 添加样本
        for i in range(10):
            sample = {'id': i, 'data': f'sample_{i}'}
            manager.add_sample(sample)
        
        # 检查最终数据
        final_data = manager.get_final_data()
        self.assertLessEqual(len(final_data), 5)  # 应该被限制在max_samples内


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_end_to_end_analysis(self):
        """端到端分析测试"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试数据目录结构
            machine_dir = os.path.join(temp_dir, "test-machine")
            phase1_dir = os.path.join(machine_dir, "phase1_single_gpu")
            phase2_dir = os.path.join(machine_dir, "phase2_all_gpu")
            
            os.makedirs(phase1_dir)
            os.makedirs(phase2_dir)
            
            # 创建测试数据文件
            test_data = {
                'samples': [
                    {
                        'timestamp': '2024-01-01T12:00:00',
                        'gpus': [
                            {
                                'gpu_id': 0,
                                'sm_utilization': 95.0,
                                'memory_utilization': 80.0,
                                'temperature': 75.0,
                                'power': 300.0
                            }
                        ]
                    }
                ]
            }
            
            with open(os.path.join(phase1_dir, "gpu0_monitor_test.json"), 'w') as f:
                json.dump(test_data, f)
            
            with open(os.path.join(phase2_dir, "all_gpu_monitor_test.json"), 'w') as f:
                json.dump(test_data, f)
            
            # 测试数据加载
            phase1_data = load_phase_data(phase1_dir, "Phase 1")
            self.assertIn('monitoring_data', phase1_data)
            self.assertIn('gflops_data', phase1_data)
            
            # 测试分析
            baseline_stats = analyze_single_gpu_baseline(phase1_data)
            self.assertIsInstance(baseline_stats, dict)


def run_performance_test():
    """运行性能测试"""
    print("Running performance tests...")
    
    # 测试配置加载性能
    start_time = time.time()
    config = GPUAnalysisConfig()
    config_time = time.time() - start_time
    print(f"Config creation time: {config_time:.4f}s")
    
    # 测试数据验证性能
    start_time = time.time()
    for i in range(1000):
        data = {
            'gpu_id': i % 4,
            'sm_utilization': 95.0,
            'memory_utilization': 80.0,
            'temperature': 75.0,
            'power': 300.0
        }
        validate_gpu_data(data)
    validation_time = time.time() - start_time
    print(f"1000 data validations time: {validation_time:.4f}s")
    
    # 测试文件操作性能
    start_time = time.time()
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        f.flush()
        
        for i in range(100):
            validate_file_path(f.name)
        
        os.unlink(f.name)
    file_time = time.time() - start_time
    print(f"100 file validations time: {file_time:.4f}s")


if __name__ == "__main__":
    # 运行单元测试
    print("Running unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # 运行性能测试
    print("\n" + "="*50)
    run_performance_test()
    
    print("\n" + "="*50)
    print("All tests completed!")

