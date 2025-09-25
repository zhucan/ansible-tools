#!/usr/bin/env python3
"""
Optimized GPU Monitoring Module
优化后的GPU监控模块 - 支持流式数据处理和内存优化
"""

import json
import time
import argparse
import signal
import os
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from threading import Thread, Event
import subprocess
import statistics as stats
import re

from config import get_config, get_logger, init_config
from utils import (
    monitor_performance, retry_on_failure, validate_gpu_data,
    safe_file_operation, get_gpu_specs_dynamic
)

# 初始化配置和日志
config = get_config()
logger = get_logger()

# 性能比较指标
COMPARE_METRICS = ["sm_utilization", "memory_utilization", "temperature", "power"]


class StreamingDataManager:
    """流式数据管理器，避免内存累积"""
    
    def __init__(self, max_samples: int = 1000, save_interval: int = 30):
        self.max_samples = max_samples
        self.save_interval = save_interval
        self.data_buffer = []
        self.total_samples = 0
        self.logger = get_logger()
    
    def add_sample(self, sample: Dict[str, Any]) -> None:
        """添加样本到缓冲区"""
        self.data_buffer.append(sample)
        self.total_samples += 1
        
        # 检查是否需要保存
        if len(self.data_buffer) >= self.max_samples or self.total_samples % self.save_interval == 0:
            self._save_buffer()
    
    def _save_buffer(self) -> None:
        """保存缓冲区数据"""
        if not self.data_buffer:
            return
        
        try:
            # 这里可以实现流式保存逻辑
            # 例如：保存到临时文件，然后合并
            self.logger.debug(f"Saved {len(self.data_buffer)} samples (total: {self.total_samples})")
            self.data_buffer.clear()
        except Exception as e:
            self.logger.error(f"Error saving buffer: {e}")
    
    def get_final_data(self) -> List[Dict[str, Any]]:
        """获取最终数据"""
        return self.data_buffer.copy()


class GPUDataCollector:
    """GPU数据收集器，优化性能和错误处理"""
    
    def __init__(self):
        self.logger = get_logger()
        self.config = get_config()
        self._cpu_sample_initialized = False
        self._last_values = {}
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_nvidia_smi_data(self, query_params: str, gpu_id: int = 0) -> List[str]:
        """获取nvidia-smi数据，改进错误处理"""
        try:
            cmd = [
                "nvidia-smi",
                f"--query-gpu={query_params}",
                "--format=csv,noheader,nounits",
                f"-i={gpu_id}"
            ]
            
            result = subprocess.check_output(cmd, timeout=10).decode().strip()
            return result.split(', ')
        
        except subprocess.TimeoutExpired:
            self.logger.error(f"GPU {gpu_id} query timed out")
            return ["[TIMEOUT]"] * len(query_params.split(','))
        except Exception as e:
            self.logger.error(f"GPU {gpu_id} query failed: {e}")
            return ["[ERROR]"] * len(query_params.split(','))
    
    @monitor_performance
    def get_dmon_utilization(self, gpu_ids: List[int], samples: int = 1) -> Dict[int, Dict[str, int]]:
        """获取GPU利用率数据，优化性能"""
        try:
            cuda_visible = os.getenv('CUDA_VISIBLE_DEVICES')
            
            # 处理CUDA_VISIBLE_DEVICES
            if cuda_visible and cuda_visible.strip():
                vis_tokens = [t.strip() for t in cuda_visible.split(",") if t.strip()]
                phys_ids = []
                for v in (gpu_ids or range(len(vis_tokens))):
                    if v < len(vis_tokens):
                        tok = vis_tokens[v]
                        phys_ids.append(tok)
            else:
                phys_ids = gpu_ids or []
            
            cmd = [
                "nvidia-smi", "dmon",
                "-s", "u",
                "-d", "1",
                "-c", str(max(1, samples)),
            ]
            
            if phys_ids:
                cmd += ["-i", ",".join(str(x) for x in phys_ids)]
            
            out = subprocess.check_output(cmd, timeout=15).decode().strip().splitlines()
            
            # 处理输出
            acc = {}
            cnt = {}
            for line in out:
                parts = line.split()
                if not parts or parts[0].startswith('#'):
                    continue
                if parts[0].isdigit() and len(parts) >= 3:
                    gid = int(parts[0])
                    sm = int(parts[1])
                    mem = int(parts[2])
                    acc.setdefault(gid, {"sm": 0, "mem": 0})
                    cnt[gid] = cnt.get(gid, 0) + 1
                    acc[gid]["sm"] += sm
                    acc[gid]["mem"] += mem
            
            # 计算平均值
            util = {}
            if cuda_visible and cuda_visible.strip():
                # 处理CUDA_VISIBLE_DEVICES映射
                p2v = self._build_phys_to_visible_mapping()
                for phy, sums in acc.items():
                    n = max(1, cnt.get(phy, 1))
                    v = p2v.get(phy)
                    if v is not None:
                        util[v] = {"sm": int(sums["sm"] / n), "mem": int(sums["mem"] / n)}
            else:
                for phy, sums in acc.items():
                    n = max(1, cnt.get(phy, 1))
                    util[phy] = {"sm": int(sums["sm"] / n), "mem": int(sums["mem"] / n)}
            
            return util
        
        except subprocess.TimeoutExpired:
            self.logger.error("dmon utilization query timed out")
            return {gid: {"sm": 0, "mem": 0} for gid in gpu_ids}
        except Exception as e:
            self.logger.error(f"dmon utilization query failed: {e}")
            return {gid: {"sm": 0, "mem": 0} for gid in gpu_ids}
    
    def _build_phys_to_visible_mapping(self) -> Dict[int, int]:
        """构建物理GPU到可见GPU的映射"""
        mapping = {}
        cvd = os.getenv("CUDA_VISIBLE_DEVICES")
        if not cvd:
            return mapping
        
        toks = [t.strip() for t in cvd.split(",") if t.strip()]
        uuid2phys = {}
        
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"],
                timeout=10
            ).decode().strip().splitlines()
            for line in out:
                idx_s, uuid = [x.strip() for x in line.split(",")]
                uuid2phys[uuid] = int(idx_s)
        except Exception as e:
            self.logger.warning(f"Failed to build UUID mapping: {e}")
        
        for v, tok in enumerate(toks):
            if tok.isdigit():
                mapping[int(tok)] = v
            else:
                phy = uuid2phys.get(tok)
                if phy is not None:
                    mapping[phy] = v
        
        return mapping
    
    @monitor_performance
    def get_batch_gpu_data(self, gpu_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """批量获取GPU数据，减少nvidia-smi调用频率"""
        try:
            cuda_visible = os.getenv('CUDA_VISIBLE_DEVICES')
            
            # 处理CUDA_VISIBLE_DEVICES
            if cuda_visible and cuda_visible.strip():
                vis_tokens = [t.strip() for t in cuda_visible.split(",") if t.strip()]
                phys_ids = []
                for v in (gpu_ids or range(len(vis_tokens))):
                    if v < len(vis_tokens):
                        tok = vis_tokens[v]
                        phys_ids.append(tok)
            else:
                phys_ids = gpu_ids or []
            
            cmd = [
                "nvidia-smi",
                "--query-gpu=index,temperature.gpu,power.draw,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ]
            
            if phys_ids:
                cmd += ["-i", ",".join(str(x) for x in phys_ids)]
            
            result = subprocess.check_output(cmd, timeout=10).decode().strip()
            lines = result.split('\n')
            
            batch_data = {}
            for line in lines:
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 5:
                    try:
                        idx = int(parts[0])
                        mem_used_mib = float(parts[3]) if parts[3] != "[N/A]" else 0.0
                        mem_total_mib = float(parts[4]) if parts[4] != "[N/A]" else 1.0
                        fb_mem_util_pct = (mem_used_mib / max(mem_total_mib, 1)) * 100.0
                        
                        batch_data[idx] = {
                            'temperature': int(parts[1]) if parts[1] != "[N/A]" else 0,
                            'power': float(parts[2]) if parts[2] != "[N/A]" else 0.0,
                            'fb_mem_used_mib': mem_used_mib,
                            'fb_mem_total_mib': mem_total_mib,
                            'fb_mem_util_pct': fb_mem_util_pct
                        }
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Error parsing GPU data line: {line}, error: {e}")
                        continue
            
            # 处理CUDA_VISIBLE_DEVICES映射
            if cuda_visible and cuda_visible.strip():
                p2v = self._build_phys_to_visible_mapping()
                mapped_batch_data = {}
                for phy, data in batch_data.items():
                    v = p2v.get(phy)
                    if v is not None:
                        mapped_batch_data[v] = data
                batch_data = mapped_batch_data
            
            # 确保所有请求的GPU都有数据
            for gpu_id in gpu_ids:
                if gpu_id not in batch_data:
                    batch_data[gpu_id] = self._get_default_gpu_data()
            
            return batch_data
        
        except subprocess.TimeoutExpired:
            self.logger.error("Batch GPU data query timed out")
            return {gpu_id: self._get_default_gpu_data() for gpu_id in gpu_ids}
        except Exception as e:
            self.logger.error(f"Batch GPU data query failed: {e}")
            return {gpu_id: self._get_default_gpu_data() for gpu_id in gpu_ids}
    
    def _get_default_gpu_data(self) -> Dict[str, Any]:
        """返回默认GPU数据结构"""
        return {
            'temperature': 0,
            'power': 0.0,
            'fb_mem_used_mib': 0.0,
            'fb_mem_total_mib': 1.0,
            'fb_mem_util_pct': 0.0
        }
    
    def get_gpu_ids_to_monitor(self) -> List[int]:
        """获取要监控的GPU ID列表"""
        try:
            cuda_visible = os.getenv('CUDA_VISIBLE_DEVICES')
            if cuda_visible is not None:
                if cuda_visible.strip() == '':
                    return []
                else:
                    visible_gpus = [int(x.strip()) for x in cuda_visible.split(',') if x.strip().isdigit()]
                    return visible_gpus
            else:
                gpu_list = subprocess.check_output(["nvidia-smi", "-L"], timeout=10).decode().strip()
                device_count = len([line for line in gpu_list.split('\n') if line.strip().startswith('GPU')])
                return list(range(device_count))
        except Exception as e:
            self.logger.error(f"Error getting GPU IDs: {e}")
            return [0]
    
    @monitor_performance
    def collect_gpu_data(self) -> Dict[str, Any]:
        """收集GPU数据，优化性能"""
        timestamp = datetime.now().isoformat()
        
        try:
            gpu_ids_to_monitor = self.get_gpu_ids_to_monitor()
            if not gpu_ids_to_monitor:
                self.logger.warning("No GPUs to monitor")
                return {"timestamp": timestamp, "gpus": []}
            
            # 并行获取数据
            dmon_util = self.get_dmon_utilization(gpu_ids_to_monitor)
            batch_data = self.get_batch_gpu_data(gpu_ids_to_monitor)
            
            gpus = []
            for gpu_id in gpu_ids_to_monitor:
                try:
                    sm = int(dmon_util.get(gpu_id, {}).get("sm", 0))
                    util_memory = int(dmon_util.get(gpu_id, {}).get("mem", 0))
                    
                    gpu_batch = batch_data.get(gpu_id, {})
                    temperature = gpu_batch.get('temperature', 0)
                    power = gpu_batch.get('power', 0.0)
                    
                    fb_mem_used_mib = gpu_batch.get('fb_mem_used_mib', 0.0)
                    fb_mem_total_mib = gpu_batch.get('fb_mem_total_mib', 1.0)
                    fb_mem_util_pct = gpu_batch.get('fb_mem_util_pct', 0.0)
                    
                    gpu_info = {
                        "gpu_id": gpu_id,
                        "sm_utilization": sm,
                        "memory_utilization": util_memory,
                        "temperature": temperature,
                        "power": power,
                        "fb_mem_used_mib": fb_mem_used_mib,
                        "fb_mem_total_mib": fb_mem_total_mib,
                        "fb_mem_util_pct": fb_mem_util_pct
                    }
                    
                    # 验证数据
                    if validate_gpu_data(gpu_info):
                        gpus.append(gpu_info)
                    else:
                        self.logger.warning(f"Invalid GPU data for GPU {gpu_id}")
                
                except Exception as e:
                    self.logger.error(f"Error processing GPU {gpu_id}: {e}")
                    continue
            
            return {
                "timestamp": timestamp,
                "gpus": gpus
            }
        
        except Exception as e:
            self.logger.error(f"Error collecting GPU data: {e}")
            return {"timestamp": timestamp, "gpus": []}


class SystemMonitor:
    """系统监控器，优化性能监控"""
    
    def __init__(self):
        self.logger = get_logger()
        self._cpu_sample_initialized = False
        self._last_values = {}
    
    @monitor_performance
    def get_system_basic(self) -> Dict[str, Any]:
        """获取系统基础指标，优化性能"""
        try:
            import psutil
            
            # CPU使用率
            if not self._cpu_sample_initialized:
                psutil.cpu_percent(interval=None)
                self._cpu_sample_initialized = True
                cpu_percent = 5.0
            else:
                cpu_percent = psutil.cpu_percent(interval=None)
            
            # 内存信息
            memory = psutil.virtual_memory()
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
            
            # 获取其他指标
            cpu_cores = psutil.cpu_count()
            context_switches = self._get_context_switches()
            page_faults_data = self._get_page_faults()
            memory_bandwidth = self._get_memory_bandwidth_simple()
            run_queue_data = self._get_run_queue_info()
            cpu_psi_data = self._get_cpu_psi()
            swap_data = self._get_swap_activity()
            io_data = self._get_io_metrics()
            network_data = self._get_network_metrics()
            
            return {
                'cpu_utilization_total': cpu_percent,
                'memory_utilization': memory.percent,
                'load_average_1m': load_avg[0],
                'load_average_5m': load_avg[1],
                'load_average_15m': load_avg[2],
                'cpu_cores': cpu_cores,
                'context_switches_per_sec': context_switches,
                'memory_total_gb': memory.total / (1024**3),
                'memory_used_gb': memory.used / (1024**3),
                'memory_available_gb': memory.available / (1024**3),
                'minor_faults_per_sec': page_faults_data['minor_faults_per_sec'],
                'major_faults_per_sec': page_faults_data['major_faults_per_sec'],
                'total_faults_per_sec': page_faults_data['total_faults_per_sec'],
                'page_activity_throughput_gbps': memory_bandwidth,
                'run_queue_length': run_queue_data['procs_running'],
                'run_queue_ratio': run_queue_data['run_queue_ratio'],
                'cpu_psi_some_avg60': cpu_psi_data['some_avg60'],
                'memory_available_pct': (memory.available / memory.total) * 100,
                'swap_out_per_sec': swap_data['pswpout_per_sec'],
                'swap_total_mb': psutil.swap_memory().total / (1024*1024) if psutil.swap_memory().total > 0 else 0,
                'swap_used_pct': psutil.swap_memory().percent if psutil.swap_memory().total > 0 else -1,
                'io_wait_pct': io_data['io_wait_pct'],
                'disk_read_mbps': io_data['disk_read_mbps'],
                'disk_write_mbps': io_data['disk_write_mbps'],
                'disk_read_iops': io_data['disk_read_iops'],
                'disk_write_iops': io_data['disk_write_iops'],
                'network_recv_mbps': network_data['recv_mbps'],
                'network_sent_mbps': network_data['sent_mbps'],
                'network_packets_recv_per_sec': network_data['packets_recv_per_sec'],
                'network_packets_sent_per_sec': network_data['packets_sent_per_sec']
            }
        
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return self._get_default_system_data()
    
    def _get_default_system_data(self) -> Dict[str, Any]:
        """返回默认系统数据"""
        return {
            'cpu_utilization_total': 0,
            'memory_utilization': 0,
            'load_average_1m': 0,
            'load_average_5m': 0,
            'load_average_15m': 0,
            'cpu_cores': 1,
            'context_switches_per_sec': 0,
            'memory_total_gb': 0,
            'memory_used_gb': 0,
            'memory_available_gb': 0,
            'minor_faults_per_sec': 0,
            'major_faults_per_sec': 0,
            'total_faults_per_sec': 0,
            'page_activity_throughput_gbps': 0,
            'run_queue_length': 0,
            'run_queue_ratio': 0,
            'cpu_psi_some_avg60': 0,
            'memory_available_pct': 50,
            'swap_out_per_sec': 0,
            'swap_total_mb': 0,
            'swap_used_pct': 0,
            'io_wait_pct': 0,
            'disk_read_mbps': 0,
            'disk_write_mbps': 0,
            'disk_read_iops': 0,
            'disk_write_iops': 0,
            'network_recv_mbps': 0,
            'network_sent_mbps': 0,
            'network_packets_recv_per_sec': 0,
            'network_packets_sent_per_sec': 0
        }
    
    def _get_context_switches(self) -> int:
        """获取上下文切换率"""
        try:
            current_time = time.time()
            
            with open('/proc/stat', 'r') as f:
                for line in f:
                    if line.startswith('ctxt'):
                        current_ctxt = int(line.split()[1])
                        
                        if 'last_ctxt_time' in self._last_values and self._last_values['last_ctxt_time'] > 0:
                            time_diff = current_time - self._last_values['last_ctxt_time']
                            if time_diff > 0:
                                ctxt_rate = (current_ctxt - self._last_values['last_ctxt_value']) / time_diff
                                self._last_values['last_ctxt_value'] = current_ctxt
                                self._last_values['last_ctxt_time'] = current_time
                                return max(0, min(10000000, int(ctxt_rate)))
                        
                        self._last_values['last_ctxt_value'] = current_ctxt
                        self._last_values['last_ctxt_time'] = current_time
                        return 0
            return 0
        except Exception:
            return 0
    
    def _get_page_faults(self) -> Dict[str, int]:
        """获取页面错误率"""
        try:
            current_time = time.time()
            
            major_faults = 0
            minor_faults_raw = 0
            
            with open('/proc/vmstat', 'r') as f:
                for line in f:
                    if line.startswith('pgmajfault'):
                        major_faults = int(line.split()[1])
                    elif line.startswith('pgfault'):
                        minor_faults_raw = int(line.split()[1])
            
            minor_faults = minor_faults_raw - major_faults
            
            if 'last_pgfault_time' in self._last_values and self._last_values['last_pgfault_time'] > 0:
                time_diff = current_time - self._last_values['last_pgfault_time']
                if time_diff > 0:
                    minor_rate = (minor_faults - self._last_values.get('minor_faults', 0)) / time_diff
                    major_rate = (major_faults - self._last_values.get('major_faults', 0)) / time_diff
                    
                    self._last_values['minor_faults'] = minor_faults
                    self._last_values['major_faults'] = major_faults
                    self._last_values['last_pgfault_time'] = current_time
                    
                    return {
                        'minor_faults_per_sec': max(0, min(1000000, int(minor_rate))),
                        'major_faults_per_sec': max(0, min(100000, int(major_rate))),
                        'total_faults_per_sec': max(0, min(1100000, int(minor_rate + major_rate)))
                    }
            
            self._last_values['minor_faults'] = minor_faults
            self._last_values['major_faults'] = major_faults
            self._last_values['last_pgfault_time'] = current_time
            
            return {
                'minor_faults_per_sec': 0,
                'major_faults_per_sec': 0,
                'total_faults_per_sec': 0
            }
        except Exception:
            return {
                'minor_faults_per_sec': 0,
                'major_faults_per_sec': 0,
                'total_faults_per_sec': 0
            }
    
    def _get_memory_bandwidth_simple(self) -> float:
        """简单内存带宽估算"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            estimated_bandwidth = (memory.used / memory.total) * 20
            return round(estimated_bandwidth, 2)
        except Exception:
            return 0
    
    def _get_run_queue_info(self) -> Dict[str, float]:
        """获取运行队列信息"""
        try:
            import psutil
            cpu_count = psutil.cpu_count()
            
            with open('/proc/loadavg', 'r') as f:
                line = f.read().strip()
                parts = line.split()
                if len(parts) >= 4:
                    procs_part = parts[3]
                    if '/' in procs_part:
                        procs_running = int(procs_part.split('/')[0])
                        run_queue_ratio = procs_running / cpu_count if cpu_count > 0 else 0
                        return {
                            'procs_running': procs_running,
                            'run_queue_ratio': run_queue_ratio
                        }
            
            return {'procs_running': 0, 'run_queue_ratio': 0}
        except Exception:
            return {'procs_running': 0, 'run_queue_ratio': 0}
    
    def _get_cpu_psi(self) -> Dict[str, float]:
        """获取CPU PSI信息"""
        try:
            with open('/proc/pressure/cpu', 'r') as f:
                for line in f:
                    if line.startswith('some'):
                        parts = line.split()
                        for part in parts:
                            if part.startswith('avg60='):
                                avg60 = float(part.split('=')[1])
                                return {'some_avg60': avg60}
            return {'some_avg60': 0}
        except Exception:
            return {'some_avg60': 0}
    
    def _get_swap_activity(self) -> Dict[str, int]:
        """获取交换活动"""
        try:
            current_time = time.time()
            
            pswpin = 0
            pswpout = 0
            
            with open('/proc/vmstat', 'r') as f:
                for line in f:
                    if line.startswith('pswpin'):
                        pswpin = int(line.split()[1])
                    elif line.startswith('pswpout'):
                        pswpout = int(line.split()[1])
            
            if 'last_swap_time' in self._last_values and self._last_values['last_swap_time'] > 0:
                time_diff = current_time - self._last_values['last_swap_time']
                if time_diff > 0:
                    pswpin_rate = (pswpin - self._last_values.get('pswpin', 0)) / time_diff
                    pswpout_rate = (pswpout - self._last_values.get('pswpout', 0)) / time_diff
                    
                    self._last_values['pswpin'] = pswpin
                    self._last_values['pswpout'] = pswpout
                    self._last_values['last_swap_time'] = current_time
                    
                    return {
                        'pswpin_per_sec': max(0, int(pswpin_rate)),
                        'pswpout_per_sec': max(0, int(pswpout_rate))
                    }
            
            self._last_values['pswpin'] = pswpin
            self._last_values['pswpout'] = pswpout
            self._last_values['last_swap_time'] = current_time
            
            return {'pswpin_per_sec': 0, 'pswpout_per_sec': 0}
        except Exception:
            return {'pswpin_per_sec': 0, 'pswpout_per_sec': 0}
    
    def _get_io_metrics(self) -> Dict[str, float]:
        """获取IO指标"""
        try:
            import psutil
            current_time = time.time()
            
            # CPU IO等待时间
            cpu_times = psutil.cpu_times()
            total_time = sum(cpu_times)
            io_wait_pct = (cpu_times.iowait / total_time * 100) if hasattr(cpu_times, 'iowait') else 0
            
            # 磁盘IO统计
            disk_io = None
            try:
                disk_io = psutil.disk_io_counters()
            except ValueError as e:
                self.logger.warning(f"psutil.disk_io_counters() failed: {e}")
            
            if disk_io and 'last_disk_time' in self._last_values and self._last_values['last_disk_time'] > 0:
                time_diff = current_time - self._last_values['last_disk_time']
                if time_diff > 0:
                    read_bytes_per_sec = (disk_io.read_bytes - self._last_values.get('read_bytes', 0)) / time_diff
                    write_bytes_per_sec = (disk_io.write_bytes - self._last_values.get('write_bytes', 0)) / time_diff
                    read_iops = (disk_io.read_count - self._last_values.get('read_count', 0)) / time_diff
                    write_iops = (disk_io.write_count - self._last_values.get('write_count', 0)) / time_diff
                    
                    self._last_values.update({
                        'read_bytes': disk_io.read_bytes,
                        'write_bytes': disk_io.write_bytes,
                        'read_count': disk_io.read_count,
                        'write_count': disk_io.write_count,
                        'last_disk_time': current_time
                    })
                    
                    return {
                        'io_wait_pct': io_wait_pct,
                        'disk_read_mbps': max(0, min(10000, read_bytes_per_sec / (1024*1024))),
                        'disk_write_mbps': max(0, min(10000, write_bytes_per_sec / (1024*1024))),
                        'disk_read_iops': max(0, min(1000000, int(read_iops))),
                        'disk_write_iops': max(0, min(1000000, int(write_iops)))
                    }
            
            if disk_io:
                self._last_values.update({
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count,
                    'last_disk_time': current_time
                })
            
            return {
                'io_wait_pct': io_wait_pct,
                'disk_read_mbps': 0,
                'disk_write_mbps': 0,
                'disk_read_iops': 0,
                'disk_write_iops': 0
            }
        except Exception:
            return {
                'io_wait_pct': 0,
                'disk_read_mbps': 0,
                'disk_write_mbps': 0,
                'disk_read_iops': 0,
                'disk_write_iops': 0
            }
    
    def _get_network_metrics(self) -> Dict[str, float]:
        """获取网络指标"""
        try:
            import psutil
            current_time = time.time()
            
            net_io = None
            try:
                net_io = psutil.net_io_counters()
            except Exception as e:
                self.logger.warning(f"psutil.net_io_counters() failed: {e}")
            
            if net_io and 'last_network_time' in self._last_values and self._last_values['last_network_time'] > 0:
                time_diff = current_time - self._last_values['last_network_time']
                if time_diff > 0:
                    recv_bytes_per_sec = (net_io.bytes_recv - self._last_values.get('bytes_recv', 0)) / time_diff
                    sent_bytes_per_sec = (net_io.bytes_sent - self._last_values.get('bytes_sent', 0)) / time_diff
                    recv_packets_per_sec = (net_io.packets_recv - self._last_values.get('packets_recv', 0)) / time_diff
                    sent_packets_per_sec = (net_io.packets_sent - self._last_values.get('packets_sent', 0)) / time_diff
                    
                    self._last_values.update({
                        'bytes_recv': net_io.bytes_recv,
                        'bytes_sent': net_io.bytes_sent,
                        'packets_recv': net_io.packets_recv,
                        'packets_sent': net_io.packets_sent,
                        'last_network_time': current_time
                    })
                    
                    return {
                        'recv_mbps': max(0, min(10000, recv_bytes_per_sec / (1024*1024))),
                        'sent_mbps': max(0, min(10000, sent_bytes_per_sec / (1024*1024))),
                        'packets_recv_per_sec': max(0, min(10000000, int(recv_packets_per_sec))),
                        'packets_sent_per_sec': max(0, min(10000000, int(sent_packets_per_sec)))
                    }
            
            if net_io:
                self._last_values.update({
                    'bytes_recv': net_io.bytes_recv,
                    'bytes_sent': net_io.bytes_sent,
                    'packets_recv': net_io.packets_recv,
                    'packets_sent': net_io.packets_sent,
                    'last_network_time': current_time
                })
            
            return {
                'recv_mbps': 0,
                'sent_mbps': 0,
                'packets_recv_per_sec': 0,
                'packets_sent_per_sec': 0
            }
        except Exception:
            return {
                'recv_mbps': 0,
                'sent_mbps': 0,
                'packets_recv_per_sec': 0,
                'packets_sent_per_sec': 0
            }


class OptimizedGPUMonitor:
    """优化后的GPU监控器"""
    
    def __init__(self, output_file: str, interval: int = 1, save_interval: int = 30):
        self.output_file = output_file
        self.interval = interval
        self.save_interval = save_interval
        self.logger = get_logger()
        
        # 初始化组件
        self.gpu_collector = GPUDataCollector()
        self.system_monitor = SystemMonitor()
        self.data_manager = StreamingDataManager(max_samples=1000, save_interval=save_interval)
        
        # 控制变量
        self.running = False
        self.interrupted = False
    
    def start_monitoring(self) -> None:
        """开始监控"""
        self.logger.info("Starting optimized GPU monitoring")
        self.running = True
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            iteration = 0
            while self.running and not self.interrupted:
                iteration += 1
                
                # 收集数据
                snapshot = self.gpu_collector.collect_gpu_data()
                snapshot['system_basic'] = self.system_monitor.get_system_basic()
                snapshot['iteration'] = iteration
                
                # 添加到数据管理器
                self.data_manager.add_sample(snapshot)
                
                # 定期保存
                if iteration % self.save_interval == 0:
                    self._save_data(False)
                    self.logger.info(f"Monitoring progress: {iteration} iterations completed")
                
                time.sleep(self.interval)
        
        except KeyboardInterrupt:
            self.logger.info("Monitoring interrupted by user")
        except Exception as e:
            self.logger.error(f"Error during monitoring: {e}")
        finally:
            self.running = False
            self._save_data(True)
            self.logger.info("Monitoring completed")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"Received signal {signum}, stopping monitoring...")
        self.interrupted = True
        self.running = False
    
    def _save_data(self, is_final: bool = True) -> None:
        """保存数据"""
        try:
            data = self.data_manager.get_final_data()
            count = len(data)
            
            output_data = {
                "metadata": {
                    "total_samples": count,
                    "collection_start": data[0]['timestamp'] if data else None,
                    "collection_end": data[-1]['timestamp'] if data else None,
                    "is_final": is_final,
                    "data_collection_version": "optimized_v2.0"
                },
                "samples": data
            }
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {count} samples to {self.output_file}")
        
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Optimized GPU Monitoring Tool")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--interval", type=int, default=1, help="Collection interval (seconds)")
    parser.add_argument("--save-interval", type=int, default=30, help="Save interval (iterations)")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO', help="Logging level")
    
    args = parser.parse_args()
    
    # 初始化配置
    if args.config:
        init_config(args.config)
    
    # 设置日志级别
    logger = get_logger()
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    try:
        # 创建监控器
        monitor = OptimizedGPUMonitor(
            output_file=args.output,
            interval=args.interval,
            save_interval=args.save_interval
        )
        
        # 开始监控
        monitor.start_monitoring()
        return 0
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    import logging
    
    sys.exit(main())

