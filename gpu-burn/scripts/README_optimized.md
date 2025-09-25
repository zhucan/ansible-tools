# GPU Analysis Tool - Optimized Version

## 概述

这是GPU分析工具的优化版本，主要改进包括：

- ✅ **改进错误处理**: 细粒度的异常处理和重试机制
- ✅ **内存优化**: 流式数据处理，避免内存累积
- ✅ **代码重构**: 消除重复代码，提取公共函数
- ✅ **统一日志**: 完整的日志记录系统
- ✅ **配置管理**: 灵活的配置管理系统
- ✅ **性能优化**: 并行处理和性能监控

## 主要特性

### 1. 错误处理改进
- 细粒度的异常分类和处理
- 自动重试机制
- 优雅的错误恢复
- 详细的错误日志

### 2. 内存使用优化
- 流式数据处理
- 定期数据保存
- 内存使用限制
- 自动清理机制

### 3. 配置管理
- JSON配置文件支持
- 动态GPU规格检测
- 性能阈值配置
- 验证规则配置

### 4. 性能监控
- 函数执行时间监控
- 内存使用监控
- 性能瓶颈识别
- 优化建议

## 文件结构

```
scripts/
├── config.py                          # 配置管理模块
├── utils.py                           # 工具函数模块
├── gpu_analysis_core_optimized.py     # 优化后的核心分析模块
├── gpu_analysis_base_optimized.py     # 优化后的基础模块
├── monitor_gpu_optimized.py           # 优化后的监控模块
├── config_example.json                # 配置文件示例
└── README_optimized.md                # 本文档
```

## 使用方法

### 1. 基本使用

```bash
# 使用默认配置
python3 gpu_analysis_base_optimized.py --input /path/to/data --output /path/to/results

# 使用自定义配置
python3 gpu_analysis_base_optimized.py \
    --input /path/to/data \
    --output /path/to/results \
    --config config_example.json \
    --log-level DEBUG
```

### 2. 监控GPU

```bash
# 基本监控
python3 monitor_gpu_optimized.py --output /tmp/gpu_monitor.json

# 自定义间隔
python3 monitor_gpu_optimized.py \
    --output /tmp/gpu_monitor.json \
    --interval 2 \
    --save-interval 60 \
    --config config_example.json
```

### 3. 配置管理

```python
from config import init_config, get_config, get_logger

# 初始化配置
config = init_config('config_example.json')

# 获取配置
config = get_config()
print(f"Monitor interval: {config.monitor_interval}")

# 获取日志器
logger = get_logger()
logger.info("Application started")
```

## 配置选项

### 监控配置
- `monitor_interval`: 数据收集间隔（秒）
- `save_interval`: 数据保存间隔（迭代次数）
- `max_memory_samples`: 最大内存样本数

### GPU规格配置
- `max_power`: 最大功率（瓦特）
- `max_temp`: 最大温度（摄氏度）
- `boost_clock`: 加速时钟频率（MHz）
- `expected_gflops`: 预期GFLOPS性能

### 性能阈值
- `excellent_utilization`: 优秀利用率阈值（%）
- `good_utilization`: 良好利用率阈值（%）
- `high_temp_warning`: 高温警告阈值（°C）
- `critical_temp`: 临界温度阈值（°C）

### 验证配置
- `enable_validation`: 启用数据验证
- `max_utilization`: 最大利用率（%）
- `min_utilization`: 最小利用率（%）
- `max_temperature`: 最大温度（°C）
- `min_temperature`: 最小温度（°C）

### 错误处理配置
- `max_retries`: 最大重试次数
- `retry_delay`: 重试延迟（秒）
- `enable_fallback`: 启用回退机制
- `log_errors`: 记录错误日志

## 性能优化

### 1. 内存优化
- 流式数据处理，避免内存累积
- 定期保存数据，释放内存
- 内存使用限制和监控

### 2. 并行处理
- 批量GPU数据查询
- 异步数据处理
- 并发文件操作

### 3. 缓存机制
- 系统指标缓存
- GPU规格缓存
- 配置缓存

## 错误处理

### 1. 异常分类
- `FileNotFoundError`: 文件不存在
- `PermissionError`: 权限错误
- `TimeoutError`: 超时错误
- `ValueError`: 数据验证错误

### 2. 重试机制
- 自动重试失败的操作
- 指数退避策略
- 最大重试次数限制

### 3. 回退机制
- 默认值回退
- 简化模式回退
- 错误恢复策略

## 日志记录

### 1. 日志级别
- `DEBUG`: 详细调试信息
- `INFO`: 一般信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息

### 2. 日志格式
```
2024-01-01 12:00:00 - gpu_analysis - INFO - Processing machine: gpu-node-1
```

### 3. 日志输出
- 控制台输出
- 文件输出（可选）
- 结构化日志

## 测试

### 1. 单元测试
```python
import unittest
from utils import validate_gpu_data

class TestGPUValidation(unittest.TestCase):
    def test_valid_gpu_data(self):
        data = {
            'gpu_id': 0,
            'sm_utilization': 95.0,
            'memory_utilization': 80.0,
            'temperature': 75.0,
            'power': 300.0
        }
        self.assertTrue(validate_gpu_data(data))
```

### 2. 集成测试
```python
def test_end_to_end_analysis():
    # 创建测试数据
    # 运行分析
    # 验证结果
    pass
```

## 故障排除

### 1. 常见问题

**问题**: GPU数据收集失败
**解决**: 检查nvidia-smi是否可用，CUDA_VISIBLE_DEVICES设置是否正确

**问题**: 内存使用过高
**解决**: 减少max_memory_samples，增加save_interval

**问题**: 配置文件错误
**解决**: 检查JSON格式，使用config_example.json作为模板

### 2. 调试模式

```bash
# 启用调试日志
python3 monitor_gpu_optimized.py \
    --output /tmp/gpu_monitor.json \
    --log-level DEBUG \
    --config config_example.json
```

### 3. 性能分析

```python
# 启用性能监控
from utils import monitor_performance

@monitor_performance
def your_function():
    # 函数执行时间会被记录
    pass
```

## 贡献指南

### 1. 代码规范
- 使用类型提示
- 添加文档字符串
- 遵循PEP 8规范

### 2. 测试要求
- 单元测试覆盖率 > 80%
- 集成测试覆盖主要功能
- 性能测试验证优化效果

### 3. 提交规范
- 清晰的提交信息
- 相关的测试用例
- 更新的文档

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

如有问题或建议，请提交Issue或联系维护者。

