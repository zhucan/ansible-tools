#!/usr/bin/env python3
"""
Optimized GPU Analysis Core Module
优化后的GPU分析核心模块
"""

import json
import pandas as pd
import numpy as np
import os
import glob
import re
import subprocess
import argparse
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime

from config import get_config, get_logger
from utils import (
    monitor_performance, retry_on_failure, validate_gpu_data, 
    read_file_safely, get_gpu_specs_dynamic, safe_file_operation,
    validate_file_path
)

# 初始化配置和日志
config = get_config()
logger = get_logger()

# 动态获取GPU规格
GPU_SPECS = get_gpu_specs_dynamic()


class GPUDataValidator:
    """GPU数据验证器"""
    
    @staticmethod
    def validate_gflops_data(gflops_data: Dict[str, Any]) -> bool:
        """验证GFLOPS数据"""
        if not isinstance(gflops_data, dict):
            logger.error("GFLOPS data must be a dictionary")
            return False
        
        required_fields = ['total_gflops', 'gpu_count']
        for field in required_fields:
            if field not in gflops_data:
                logger.error(f"Missing required field in GFLOPS data: {field}")
                return False
        
        if not isinstance(gflops_data['total_gflops'], (int, float)):
            logger.error("total_gflops must be a number")
            return False
        
        if not isinstance(gflops_data['gpu_count'], int):
            logger.error("gpu_count must be an integer")
            return False
        
        if gflops_data['total_gflops'] < 0:
            logger.warning("Negative GFLOPS value detected")
        
        return True
    
    @staticmethod
    def validate_monitoring_data(monitoring_data: List[Dict[str, Any]]) -> bool:
        """验证监控数据"""
        if not isinstance(monitoring_data, list):
            logger.error("Monitoring data must be a list")
            return False
        
        if not monitoring_data:
            logger.warning("Empty monitoring data")
            return True
        
        # 验证第一个样本的结构
        sample = monitoring_data[0]
        required_fields = ['timestamp', 'gpus']
        
        for field in required_fields:
            if field not in sample:
                logger.error(f"Missing required field in monitoring data: {field}")
                return False
        
        # 验证GPU数据
        for gpu in sample.get('gpus', []):
            if not validate_gpu_data(gpu):
                return False
        
        return True


@safe_file_operation("GPU burn log parsing")
@retry_on_failure(max_retries=3, delay=1.0)
def parse_gpu_burn_logs(log_file_path: str) -> Tuple[float, int]:
    """解析GPU burn日志，改进错误处理"""
    logger = get_logger()
    
    try:
        # 验证文件路径
        if not validate_file_path(log_file_path, must_exist=True, must_be_readable=True):
            return 0.0, 0
        
        # 读取文件内容
        content = read_file_safely(log_file_path)
        if not content:
            logger.error(f"Could not read log file: {log_file_path}")
            return 0.0, 0
        
        # 检查文件是否为空
        if not content.strip():
            logger.warning(f"Empty log file: {log_file_path}")
            return 0.0, 0
        
        # 检查进程终止信息
        if "Killing processes with SIGTERM" in content:
            logger.warning(f"GPU-burn was terminated in {log_file_path}")
        elif "Killing processes with SIGKILL" in content:
            logger.warning(f"GPU-burn was force killed in {log_file_path}")
        
        # 解析GFLOPS数据
        gflops_matches = re.findall(r'\((\d+)\s+Gflop/s\)', content)
        
        if not gflops_matches:
            logger.warning(f"No GFLOPS data found in {log_file_path}")
            return 0.0, 0
        
        # 处理多GPU情况
        lines = content.split('\n')
        for line in reversed(lines):
            if 'Gflop/s' in line:
                line_gflops = re.findall(r'\((\d+)\s+Gflop/s\)', line)
                gpu_count = len(line_gflops)
                
                if gpu_count == 0:
                    continue
                elif gpu_count == 1:
                    total_gflops = float(line_gflops[0])
                else:
                    # 多GPU情况，计算总和
                    individual_values = [float(gf) for gf in line_gflops]
                    total_gflops = sum(individual_values)
                
                logger.info(f"Parsed {total_gflops:.2f} GFLOPS from {gpu_count} GPU(s)")
                return total_gflops, gpu_count
        
        logger.warning(f"No valid GFLOPS data found in {log_file_path}")
        return 0.0, 0
    
    except Exception as e:
        logger.error(f"Error parsing GPU burn logs from {log_file_path}: {e}")
        return 0.0, 0


@monitor_performance
def load_phase_data(phase_dir: str, phase_name: str) -> Dict[str, Any]:
    """加载阶段数据，改进错误处理和内存管理"""
    logger = get_logger()
    
    try:
        # 验证目录路径
        if not validate_file_path(phase_dir, must_exist=True, must_be_readable=True):
            logger.error(f"Invalid phase directory: {phase_dir}")
            return {'monitoring_data': [], 'gflops_data': {}}
        
        # 查找数据文件
        json_files = glob.glob(os.path.join(phase_dir, "*.json"))
        log_files = glob.glob(os.path.join(phase_dir, "*.log"))
        yaml_files = glob.glob(os.path.join(phase_dir, "*.yaml"))
        
        logger.info(f"Loading {phase_name}: {len(json_files)} JSON, {len(log_files)} log, {len(yaml_files)} YAML files")
        
        # 加载监控数据
        monitoring_data = []
        
        if "phase1_single_gpu" in phase_dir:
            monitoring_data = _load_single_gpu_monitoring_data(json_files)
        else:
            monitoring_data = _load_all_gpu_monitoring_data(json_files)
        
        # 验证监控数据
        if not GPUDataValidator.validate_monitoring_data(monitoring_data):
            logger.warning(f"Invalid monitoring data in {phase_name}")
            monitoring_data = []
        
        # 加载GFLOPS数据
        gflops_data = _load_gflops_data(log_files)
        
        return {
            'monitoring_data': monitoring_data,
            'gflops_data': gflops_data
        }
    
    except Exception as e:
        logger.error(f"Error loading phase data from {phase_dir}: {e}")
        return {'monitoring_data': [], 'gflops_data': {}}


def _load_single_gpu_monitoring_data(json_files: List[str]) -> List[Dict[str, Any]]:
    """加载单GPU监控数据"""
    monitoring_data = []
    
    for json_file in json_files:
        try:
            filename = os.path.basename(json_file)
            if not (filename.startswith('gpu') and '_monitor_' in filename):
                continue
            
            # 提取GPU ID
            gpu_id_match = re.search(r'gpu(\d+)_', filename)
            if not gpu_id_match:
                logger.warning(f"Cannot extract GPU ID from filename {filename}")
                continue
            
            target_gpu_id = int(gpu_id_match.group(1))
            
            # 读取文件数据
            file_data = read_file_safely(json_file)
            if not file_data:
                continue
            
            try:
                data = json.loads(file_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {json_file}: {e}")
                continue
            
            # 处理数据格式
            if isinstance(data, dict) and 'samples' in data:
                samples = data['samples']
            else:
                samples = data if isinstance(data, list) else []
            
            # 过滤特定GPU的数据
            filtered_samples = []
            for sample in samples:
                if not isinstance(sample, dict) or 'gpus' not in sample:
                    continue
                
                filtered_gpus = []
                for gpu in sample.get('gpus', []):
                    if isinstance(gpu, dict) and gpu.get('gpu_id') == target_gpu_id:
                        filtered_gpus.append(gpu)
                
                if filtered_gpus:
                    sample_copy = sample.copy()
                    sample_copy['gpus'] = filtered_gpus
                    filtered_samples.append(sample_copy)
            
            monitoring_data.extend(filtered_samples)
            logger.info(f"Loaded {len(filtered_samples)} samples for GPU{target_gpu_id} from {filename}")
        
        except Exception as e:
            logger.error(f"Error loading single GPU data from {json_file}: {e}")
    
    return monitoring_data


def _load_all_gpu_monitoring_data(json_files: List[str]) -> List[Dict[str, Any]]:
    """加载所有GPU监控数据"""
    monitoring_data = []
    
    for json_file in json_files:
        try:
            file_data = read_file_safely(json_file)
            if not file_data:
                continue
            
            try:
                data = json.loads(file_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {json_file}: {e}")
                continue
            
            if isinstance(data, dict) and 'samples' in data:
                monitoring_data.extend(data['samples'])
            elif isinstance(data, list):
                monitoring_data.extend(data)
        
        except Exception as e:
            logger.error(f"Error loading all GPU data from {json_file}: {e}")
    
    return monitoring_data


def _load_gflops_data(log_files: List[str]) -> Dict[str, Dict[str, Union[float, int]]]:
    """加载GFLOPS数据"""
    gflops_data = {}
    
    for log_file in log_files:
        log_name = os.path.basename(log_file)
        
        # 只处理GPU burn日志
        if 'gpu_burn' not in log_name and 'all_gpu_burn' not in log_name:
            continue
        
        try:
            total_gflops, gpu_count = parse_gpu_burn_logs(log_file)
            if total_gflops > 0:
                gflops_data[log_name] = {
                    'total_gflops': total_gflops,
                    'gpu_count': gpu_count
                }
                logger.info(f"Loaded GFLOPS data from {log_name}: {total_gflops:.2f} GFLOPS, {gpu_count} GPU(s)")
        
        except Exception as e:
            logger.error(f"Error loading GFLOPS data from {log_file}: {e}")
    
    return gflops_data


@monitor_performance
def analyze_single_gpu_baseline(phase1_data: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """分析单GPU基线数据，改进错误处理"""
    logger = get_logger()
    
    try:
        monitoring_data = phase1_data.get('monitoring_data', [])
        gflops_data = phase1_data.get('gflops_data', {})
        
        if not monitoring_data:
            logger.warning("No monitoring data available for baseline analysis")
            return {}
        
        # 验证数据
        if not GPUDataValidator.validate_monitoring_data(monitoring_data):
            logger.error("Invalid monitoring data for baseline analysis")
            return {}
        
        # 处理GPU记录
        gpu_records = []
        for sample in monitoring_data:
            try:
                timestamp = pd.to_datetime(sample['timestamp'])
                for gpu in sample.get('gpus', []):
                    if not validate_gpu_data(gpu):
                        continue
                    
                    record = {
                        'timestamp': timestamp,
                        'gpu_id': gpu['gpu_id'],
                        'utilization': float(gpu.get('sm_utilization', 0)),
                        'memory_utilization': float(gpu.get('memory_utilization', 0)),
                        'temperature': float(gpu.get('temperature', 0)),
                        'power': float(gpu.get('power', 0)),
                        'fb_mem_util_pct': float(gpu.get('fb_mem_util_pct', 0.0)),
                    }
                    gpu_records.append(record)
            
            except Exception as e:
                logger.warning(f"Error processing sample: {e}")
                continue
        
        if not gpu_records:
            logger.warning("No valid GPU records found for baseline analysis")
            return {}
        
        # 创建DataFrame并分析
        df = pd.DataFrame(gpu_records)
        baseline_stats = {}
        
        for gpu_id in df['gpu_id'].unique():
            try:
                gpu_df = df[df['gpu_id'] == gpu_id]
                if gpu_df.empty:
                    continue
                
                # 查找对应的GFLOPS数据
                gpu_gflops = 0
                for log_name, gflops_info in gflops_data.items():
                    if f'gpu{gpu_id}' in log_name:
                        gpu_gflops = gflops_info.get('total_gflops', 0)
                        break
                
                # 计算统计信息
                baseline_stats[f'GPU{gpu_id}'] = {
                    'avg_utilization': float(gpu_df['utilization'].mean()),
                    'avg_memory_utilization': float(gpu_df['memory_utilization'].mean()),
                    'avg_temperature': float(gpu_df['temperature'].mean()),
                    'max_temperature': float(gpu_df['temperature'].max()),
                    'avg_power': float(gpu_df['power'].mean()),
                    'gflops': gpu_gflops,
                    'sample_count': len(gpu_df)
                }
                
                logger.info(f"GPU{gpu_id} baseline: {baseline_stats[f'GPU{gpu_id}']['avg_utilization']:.1f}% util, "
                          f"{baseline_stats[f'GPU{gpu_id}']['avg_temperature']:.1f}°C, "
                          f"{baseline_stats[f'GPU{gpu_id}']['avg_power']:.1f}W")
            
            except Exception as e:
                logger.error(f"Error analyzing GPU{gpu_id} baseline: {e}")
                continue
        
        return baseline_stats
    
    except Exception as e:
        logger.error(f"Error in baseline analysis: {e}")
        return {}


@monitor_performance
def analyze_all_gpu_stress(phase2_data: Dict[str, Any], baseline_stats: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    """分析所有GPU压力测试数据"""
    logger = get_logger()
    
    try:
        monitoring_data = phase2_data.get('monitoring_data', [])
        gflops_data = phase2_data.get('gflops_data', {})
        
        if not monitoring_data:
            logger.warning("No monitoring data available for stress analysis")
            return {}
        
        # 验证数据
        if not GPUDataValidator.validate_monitoring_data(monitoring_data):
            logger.error("Invalid monitoring data for stress analysis")
            return {}
        
        # 处理GPU记录
        gpu_records = []
        for sample in monitoring_data:
            try:
                timestamp = pd.to_datetime(sample['timestamp'])
                for gpu in sample.get('gpus', []):
                    if not validate_gpu_data(gpu):
                        continue
                    
                    record = {
                        'timestamp': timestamp,
                        'gpu_id': gpu['gpu_id'],
                        'utilization': float(gpu.get('sm_utilization', 0)),
                        'memory_utilization': float(gpu.get('memory_utilization', 0)),
                        'temperature': float(gpu.get('temperature', 0)),
                        'power': float(gpu.get('power', 0)),
                        'fb_mem_util_pct': float(gpu.get('fb_mem_util_pct', 0.0)),
                    }
                    gpu_records.append(record)
            
            except Exception as e:
                logger.warning(f"Error processing stress sample: {e}")
                continue
        
        if not gpu_records:
            logger.warning("No valid GPU records found for stress analysis")
            return {}
        
        # 创建DataFrame并分析
        df = pd.DataFrame(gpu_records)
        
        # 获取系统总GFLOPS
        total_system_gflops = 0
        total_gpu_count = 0
        for log_name, gflops_info in gflops_data.items():
            if 'all_gpu' in log_name:
                total_system_gflops = gflops_info.get('total_gflops', 0)
                total_gpu_count = gflops_info.get('gpu_count', 0)
                break
        
        # 计算系统统计
        system_stats = df.groupby('timestamp').agg({
            'temperature': ['mean', 'max', 'min'],
            'power': 'sum'
        }).reset_index()
        
        # 计算完整统计信息
        full_stats = {
            'total_samples': len(df),
            'max_temp_observed': float(df['temperature'].max()) if not df.empty else 0,
            'data_available': len(df) > 0,
            'avg_utilization': float(df['utilization'].mean()) if not df.empty else 0,
            'avg_power_per_gpu': float(df['power'].mean()) if not df.empty else 0
        }
        
        # 创建节点摘要
        node_summary = {
            'total_gflops': total_system_gflops,
            'total_gpu_count': total_gpu_count,
            'avg_total_power': float(system_stats[('power', 'sum')].mean()) if not system_stats.empty else 0,
            'max_temp': float(system_stats[('temperature', 'max')].max()) if not system_stats.empty else 0,
            'temp_delta': float(system_stats[('temperature', 'max')].max() - system_stats[('temperature', 'min')].min()) if not system_stats.empty else 0,
            'full_stats': full_stats
        }
        
        logger.info(f"Stress analysis complete: {total_system_gflops:.2f} GFLOPS, "
                  f"{total_gpu_count} GPUs, {full_stats['max_temp_observed']:.1f}°C max temp")
        
        return node_summary
    
    except Exception as e:
        logger.error(f"Error in stress analysis: {e}")
        return {}


def create_common_argument_parser(description: str) -> argparse.ArgumentParser:
    """创建通用参数解析器"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input", required=True, help="Input data root directory")
    parser.add_argument("--output", required=True, help="Output directory for figures")
    parser.add_argument(
        "--hosts",
        nargs='*',
        help=(
            "Optional filter: specify host directory names to include.\n"
            "Space- or comma-separated. If omitted, include all subdirectories."
        ),
    )
    parser.add_argument(
        "--analysis",
        choices=['timeline'],
        default='timeline',
        help="Analysis mode: timeline=full timeline plots"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--log-level",
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help="Logging level"
    )
    return parser


def run_hosts_comparison(input_dir: str, output_dir: str, hosts_filter: Optional[List[str]] = None, analysis_mode: str = 'both') -> None:
    """运行主机对比分析"""
    logger = get_logger()
    
    try:
        from gpu_analysis_base import discover_and_filter_machines, load_machine_data
        from gpu_visualization_base import extract_time_series_data, create_multi_machine_visualizations
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 发现和过滤机器
        machines = discover_and_filter_machines(input_dir, hosts_filter)
        if not machines:
            logger.error("No machines found to analyze")
            return
        
        logger.info(f"Processing {len(machines)} machines: {machines}")
        
        # 处理每台机器
        results_by_machine = {}
        for machine_name in machines:
            try:
                logger.info(f"Processing machine: {machine_name}")
                data = load_machine_data(input_dir, machine_name)
                
                if not data:
                    logger.warning(f"No data available for machine {machine_name}")
                    continue
                
                # 提取时间序列数据
                ts = extract_time_series_data(data['phase2_data'])
                if ts is None:
                    logger.warning(f"No time series data for machine {machine_name}")
                    continue
                
                results_by_machine[machine_name] = {
                    'timeseries': ts,
                    'node_summary': data['node_summary'],
                    'phase2_data': data['phase2_data'],
                }
                
                logger.info(f"Successfully processed machine {machine_name}")
            
            except Exception as e:
                logger.error(f"Error processing machine {machine_name}: {e}")
                continue
        
        if not results_by_machine:
            logger.error("No valid machine results to plot")
            return
        
        # 创建可视化
        create_multi_machine_visualizations(results_by_machine, output_dir, analysis_mode)
        logger.info(f"Analysis complete. Results saved to {output_dir}")
    
    except Exception as e:
        logger.error(f"Error in hosts comparison: {e}")
        raise


def run_intra_node_comparison(input_dir: str, output_dir: str, hosts_filter: Optional[List[str]] = None, analysis_mode: str = 'both') -> None:
    """运行节点内对比分析"""
    logger = get_logger()
    
    try:
        from gpu_analysis_base import discover_and_filter_machines, load_machine_data
        from gpu_visualization_base import create_intra_node_single_gpu_comparison
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 发现和过滤机器
        machines = discover_and_filter_machines(input_dir, hosts_filter)
        if not machines:
            logger.error("No machines found to analyze")
            return
        
        logger.info(f"Processing {len(machines)} machines for intra-node comparison")
        
        # 处理每台机器
        for machine_name in machines:
            try:
                logger.info(f"Processing machine: {machine_name}")
                data = load_machine_data(input_dir, machine_name)
                
                if not data:
                    logger.warning(f"No data available for machine {machine_name}")
                    continue
                
                # 创建节点内对比
                create_intra_node_single_gpu_comparison(
                    data['phase1_data'], 
                    data['baseline_stats'], 
                    output_dir, 
                    machine_name, 
                    analysis_mode
                )
                
                logger.info(f"Successfully processed machine {machine_name}")
            
            except Exception as e:
                logger.error(f"Error processing machine {machine_name}: {e}")
                continue
        
        logger.info(f"Intra-node comparison complete. Results saved to {output_dir}")
    
    except Exception as e:
        logger.error(f"Error in intra-node comparison: {e}")
        raise

