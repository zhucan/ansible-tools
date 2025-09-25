#!/usr/bin/env python3
"""
Optimized GPU Analysis Base Module
优化后的GPU分析基础模块
"""

import os
import argparse
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from config import get_config, get_logger, init_config
from utils import parse_hosts_argument, discover_and_filter_machines, validate_file_path
from gpu_analysis_core_optimized import (
    load_phase_data, analyze_single_gpu_baseline, analyze_all_gpu_stress,
    create_common_argument_parser
)

# 初始化配置和日志
config = get_config()
logger = get_logger()


class MachineDataLoader:
    """机器数据加载器，支持流式处理"""
    
    def __init__(self, input_dir: str, max_memory_samples: int = 1000):
        self.input_dir = input_dir
        self.max_memory_samples = max_memory_samples
        self.logger = get_logger()
    
    def load_machine_data_streaming(self, machine_name: str) -> Optional[Dict[str, Any]]:
        """流式加载机器数据，避免内存累积"""
        try:
            machine_path = os.path.join(self.input_dir, machine_name)
            phase1_dir = os.path.join(machine_path, "phase1_single_gpu")
            phase2_dir = os.path.join(machine_path, "phase2_all_gpu")
            
            # 验证目录存在
            if not validate_file_path(phase1_dir, must_exist=True, must_be_readable=True):
                self.logger.error(f"Phase1 directory not accessible: {phase1_dir}")
                return None
            
            if not validate_file_path(phase2_dir, must_exist=True, must_be_readable=True):
                self.logger.error(f"Phase2 directory not accessible: {phase2_dir}")
                return None
            
            # 加载阶段数据
            phase1_data = load_phase_data(phase1_dir, "Phase 1")
            phase2_data = load_phase_data(phase2_dir, "Phase 2")
            
            # 检查数据是否为空
            if not phase1_data.get('monitoring_data') and not phase2_data.get('monitoring_data'):
                self.logger.warning(f"No monitoring data found for machine {machine_name}")
                return None
            
            # 分析数据
            baseline_stats = analyze_single_gpu_baseline(phase1_data)
            node_summary = analyze_all_gpu_stress(phase2_data, baseline_stats)
            
            return {
                'phase1_data': phase1_data,
                'phase2_data': phase2_data,
                'baseline_stats': baseline_stats,
                'node_summary': node_summary,
            }
        
        except Exception as e:
            self.logger.error(f"Error loading machine data for {machine_name}: {e}")
            return None
    
    def load_machine_data(self, machine_name: str) -> Optional[Dict[str, Any]]:
        """加载机器数据（兼容性方法）"""
        return self.load_machine_data_streaming(machine_name)


def load_machine_data(input_dir: str, machine_name: str) -> Optional[Dict[str, Any]]:
    """加载机器数据（兼容性函数）"""
    loader = MachineDataLoader(input_dir)
    return loader.load_machine_data(machine_name)


class GPUAnalysisManager:
    """GPU分析管理器"""
    
    def __init__(self, input_dir: str, output_dir: str, config_path: Optional[str] = None):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.config_path = config_path
        self.logger = get_logger()
        
        # 初始化配置
        if config_path:
            init_config(config_path)
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
    
    def run_analysis(self, hosts_filter: Optional[List[str]] = None, analysis_mode: str = 'both') -> bool:
        """运行分析"""
        try:
            # 发现和过滤机器
            machines = discover_and_filter_machines(self.input_dir, hosts_filter)
            if not machines:
                self.logger.error("No machines found to analyze")
                return False
            
            self.logger.info(f"Found {len(machines)} machines to analyze: {machines}")
            
            # 处理每台机器
            results = {}
            for machine_name in machines:
                try:
                    self.logger.info(f"Processing machine: {machine_name}")
                    
                    # 加载数据
                    data = load_machine_data(self.input_dir, machine_name)
                    if not data:
                        self.logger.warning(f"No data available for machine {machine_name}")
                        continue
                    
                    results[machine_name] = data
                    self.logger.info(f"Successfully processed machine {machine_name}")
                
                except Exception as e:
                    self.logger.error(f"Error processing machine {machine_name}: {e}")
                    continue
            
            if not results:
                self.logger.error("No valid results to process")
                return False
            
            # 生成报告
            self._generate_reports(results, analysis_mode)
            return True
        
        except Exception as e:
            self.logger.error(f"Error in analysis: {e}")
            return False
    
    def _generate_reports(self, results: Dict[str, Any], analysis_mode: str) -> None:
        """生成报告"""
        try:
            if analysis_mode in ['timeline', 'both']:
                self._generate_timeline_reports(results)
            
            if analysis_mode in ['summary', 'both']:
                self._generate_summary_reports(results)
            
            self.logger.info(f"Reports generated successfully in {self.output_dir}")
        
        except Exception as e:
            self.logger.error(f"Error generating reports: {e}")
            raise
    
    def _generate_timeline_reports(self, results: Dict[str, Any]) -> None:
        """生成时间线报告"""
        try:
            from gpu_visualization_base import create_multi_machine_visualizations
            
            # 准备数据
            results_by_machine = {}
            for machine_name, data in results.items():
                try:
                    from gpu_visualization_base import extract_time_series_data
                    ts = extract_time_series_data(data['phase2_data'])
                    
                    results_by_machine[machine_name] = {
                        'timeseries': ts,
                        'node_summary': data['node_summary'],
                        'phase2_data': data['phase2_data'],
                    }
                except Exception as e:
                    self.logger.warning(f"Error preparing data for {machine_name}: {e}")
                    continue
            
            if results_by_machine:
                create_multi_machine_visualizations(results_by_machine, self.output_dir, 'timeline')
        
        except Exception as e:
            self.logger.error(f"Error generating timeline reports: {e}")
            raise
    
    def _generate_summary_reports(self, results: Dict[str, Any]) -> None:
        """生成摘要报告"""
        try:
            summary_file = os.path.join(self.output_dir, 'analysis_summary.json')
            
            # 创建摘要数据
            summary_data = {
                'analysis_timestamp': str(pd.Timestamp.now()),
                'total_machines': len(results),
                'machines': {}
            }
            
            for machine_name, data in results.items():
                try:
                    baseline_stats = data.get('baseline_stats', {})
                    node_summary = data.get('node_summary', {})
                    
                    summary_data['machines'][machine_name] = {
                        'baseline_stats': baseline_stats,
                        'node_summary': node_summary,
                        'gpu_count': len(baseline_stats),
                        'total_gflops': node_summary.get('total_gflops', 0),
                        'max_temperature': node_summary.get('max_temp', 0)
                    }
                
                except Exception as e:
                    self.logger.warning(f"Error creating summary for {machine_name}: {e}")
                    continue
            
            # 保存摘要
            import json
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Summary report saved to {summary_file}")
        
        except Exception as e:
            self.logger.error(f"Error generating summary reports: {e}")
            raise


def main():
    """主函数"""
    parser = create_common_argument_parser(
        "Optimized GPU Analysis Tool - Enhanced error handling and memory management"
    )
    args = parser.parse_args()
    
    # 初始化配置
    if args.config:
        init_config(args.config)
    
    # 设置日志级别
    logger = get_logger()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    try:
        # 创建分析管理器
        manager = GPUAnalysisManager(args.input, args.output, args.config)
        
        # 解析主机过滤
        hosts_filter = parse_hosts_argument(args.hosts)
        
        # 运行分析
        success = manager.run_analysis(hosts_filter, args.analysis)
        
        if success:
            logger.info("Analysis completed successfully")
            return 0
        else:
            logger.error("Analysis failed")
            return 1
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    import logging
    import pandas as pd
    
    sys.exit(main())

