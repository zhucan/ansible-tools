# GPU分析项目 - Ansible自动化部署指南

## 🎯 概述

本文档详细说明如何使用Ansible自动化部署和运行GPU分析项目。通过Ansible，你可以轻松地将GPU监控和分析工具部署到多台服务器上。

## 📁 项目结构

```
gpu-burn/
├── scripts/                    # GPU分析脚本
│   ├── monitor_gpu_optimized.py
│   ├── config.py
│   ├── utils.py
│   └── ...
└── ansible/                    # Ansible自动化配置
    ├── inventory.yml           # 主机清单
    ├── playbook.yml           # 部署脚本
    ├── requirements.txt       # Python依赖
    ├── ansible.cfg           # Ansible配置
    ├── deploy.sh             # 部署脚本
    ├── templates/            # 配置模板
    │   ├── config.json.j2
    │   └── gpu-monitor.service.j2
    ├── example_usage.sh      # 使用示例
    └── README.md            # 详细文档
```

## 🚀 快速开始

### 1. 环境准备

确保你的控制机器（运行Ansible的机器）已安装：

```bash
# 安装Ansible
# Ubuntu/Debian
sudo apt update && sudo apt install ansible

# CentOS/RHEL
sudo yum install ansible

# macOS
brew install ansible

# 或使用pip
pip install ansible
```

### 2. 配置SSH密钥

确保可以无密码SSH连接到目标主机：

```bash
# 生成SSH密钥（如果还没有）
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# 复制密钥到目标主机
ssh-copy-id user@target-host
```

### 3. 配置主机清单

编辑 `ansible/inventory.yml` 文件：

```yaml
all:
  children:
    gpu_nodes:
      hosts:
        gpu-node-1:
          ansible_host: 192.168.1.100    # 替换为实际IP
          ansible_user: ubuntu            # 替换为实际用户
          ansible_ssh_private_key_file: ~/.ssh/id_rsa
          gpu_count: 2
          gpu_type: "RTX 3080"
        gpu-node-2:
          ansible_host: 192.168.1.101
          ansible_user: ubuntu
          ansible_ssh_private_key_file: ~/.ssh/id_rsa
          gpu_count: 4
          gpu_type: "RTX 4090"
```

### 4. 运行部署

```bash
# 进入ansible目录
cd gpu-burn/ansible

# 基本部署
./deploy.sh

# 详细输出
./deploy.sh -v

# 试运行（不实际部署）
./deploy.sh -d
```

## 📋 详细配置

### 主机清单配置

`inventory.yml` 文件定义了目标主机和变量：

```yaml
all:
  children:
    gpu_nodes:
      hosts:
        # 主机配置
        gpu-node-1:
          ansible_host: 192.168.1.100
          ansible_user: ubuntu
          ansible_ssh_private_key_file: ~/.ssh/id_rsa
          gpu_count: 2                    # GPU数量
          gpu_type: "RTX 3080"           # GPU类型
      vars:
        # 全局变量
        project_path: "/opt/gpu-analysis"
        python_version: "3.9"
        monitor_interval: 1              # 监控间隔（秒）
        save_interval: 30                # 保存间隔
        max_memory_samples: 1000          # 最大内存样本
```

### 支持的GPU类型

系统自动识别并配置以下GPU类型：

| GPU类型 | 最大功率 | 最大温度 | 加速频率 | 预期GFLOPS |
|---------|----------|----------|----------|------------|
| RTX 3080 | 320W | 83°C | 1710MHz | 29,700 |
| RTX 4090 | 450W | 83°C | 2520MHz | 83,000 |
| RTX 3060 | 170W | 83°C | 1777MHz | 12,800 |
| 默认 | 360W | 83°C | 2620MHz | 0 |

### 性能阈值配置

可以通过inventory文件自定义性能阈值：

```yaml
vars:
  # 性能阈值
  excellent_utilization: 95.0    # 优秀利用率阈值
  good_utilization: 90.0         # 良好利用率阈值
  high_temp_warning: 80.0        # 高温警告阈值
  critical_temp: 83.0            # 临界温度阈值
  optimal_power_ratio: 0.9      # 最佳功率比例
```

## 🛠️ 部署流程

Ansible playbook会按以下步骤执行：

### 1. 系统检查
- ✅ 验证操作系统兼容性（Ubuntu, CentOS, RHEL, Debian）
- ✅ 检查Python版本（>= 3.6）
- ✅ 验证NVIDIA驱动安装

### 2. 环境准备
- 📦 安装系统依赖包
- 🐍 创建Python虚拟环境
- 📁 创建项目目录结构

### 3. 项目部署
- 📋 复制项目文件到目标主机
- 🔧 安装Python依赖包
- ⚙️ 生成配置文件

### 4. 服务配置
- 🔄 创建systemd服务
- 🚀 启用自动启动
- ▶️ 启动GPU监控服务

### 5. 验证部署
- ✅ 检查文件完整性
- 🔍 验证服务状态
- 📝 创建管理脚本

## 📊 部署后管理

### 服务管理命令

```bash
# 启动GPU监控服务
sudo systemctl start gpu-monitor

# 停止GPU监控服务
sudo systemctl stop gpu-monitor

# 重启GPU监控服务
sudo systemctl restart gpu-monitor

# 查看服务状态
sudo systemctl status gpu-monitor

# 查看实时日志
sudo journalctl -u gpu-monitor -f

# 启用开机自启
sudo systemctl enable gpu-monitor
```

### 数据文件位置

```
/opt/gpu-analysis/
├── config/
│   └── config.json              # 配置文件
├── data/
│   └── gpu_monitor.json          # 监控数据
├── logs/
│   └── gpu_analysis.log          # 日志文件
├── scripts/                      # 项目脚本
├── venv/                         # Python虚拟环境
├── start_monitor.sh              # 启动脚本
├── stop_monitor.sh               # 停止脚本
└── check_status.sh               # 状态检查脚本
```

### 快速管理脚本

部署后会自动创建以下管理脚本：

```bash
# 手动启动监控
/opt/gpu-analysis/start_monitor.sh

# 停止监控服务
/opt/gpu-analysis/stop_monitor.sh

# 检查服务状态和数据
/opt/gpu-analysis/check_status.sh
```

## 📈 监控数据查看

### 实时监控

```bash
# 查看实时数据
watch -n 1 'cat /opt/gpu-analysis/data/gpu_monitor.json'

# 查看服务状态
sudo systemctl status gpu-monitor

# 查看实时日志
sudo journalctl -u gpu-monitor -f
```

### 数据分析

```bash
# 查看JSON数据
cat /opt/gpu-analysis/data/gpu_monitor.json | jq '.'

# 分析GPU利用率
cat /opt/gpu-analysis/data/gpu_monitor.json | jq '.gpu_data[].sm_utilization'

# 分析温度数据
cat /opt/gpu-analysis/data/gpu_monitor.json | jq '.gpu_data[].temperature'
```

## 🔧 故障排除

### 常见问题及解决方案

#### 1. SSH连接失败
```bash
# 检查SSH连接
ssh -v user@target-host

# 检查SSH密钥
ssh-add -l

# 重新生成密钥
ssh-keygen -t rsa -b 4096
ssh-copy-id user@target-host
```

#### 2. Python依赖安装失败
```bash
# 手动安装依赖
pip3 install -r requirements.txt

# 使用虚拟环境
source /opt/gpu-analysis/venv/bin/activate
pip install -r requirements.txt
```

#### 3. NVIDIA驱动问题
```bash
# 检查NVIDIA驱动
nvidia-smi

# 安装NVIDIA驱动（Ubuntu）
sudo apt update
sudo apt install nvidia-driver-525

# 重启系统
sudo reboot
```

#### 4. 权限问题
```bash
# 检查用户权限
groups $USER

# 添加用户到sudo组
sudo usermod -aG sudo $USER
```

#### 5. 服务启动失败
```bash
# 查看详细错误
sudo journalctl -u gpu-monitor --no-pager

# 手动测试脚本
cd /opt/gpu-analysis/scripts
python3 monitor_gpu_optimized.py --help
```

### 调试模式

使用详细输出模式查看执行过程：

```bash
# 详细输出部署
./deploy.sh -v

# 试运行模式
./deploy.sh -d

# 检查模式
./deploy.sh -c
```

## 🔄 更新和维护

### 更新部署

```bash
# 重新运行部署（会更新文件）
./deploy.sh

# 只更新特定组件
ansible-playbook -i inventory.yml playbook.yml --tags update
```

### 备份数据

```bash
# 备份监控数据
tar -czf gpu_data_backup_$(date +%Y%m%d).tar.gz /opt/gpu-analysis/data/

# 备份配置文件
cp /opt/gpu-analysis/config/config.json config_backup.json
```

### 清理部署

```bash
# 停止服务
sudo systemctl stop gpu-monitor
sudo systemctl disable gpu-monitor

# 删除服务文件
sudo rm /etc/systemd/system/gpu-monitor.service
sudo systemctl daemon-reload

# 删除项目文件
sudo rm -rf /opt/gpu-analysis
```

## 📝 自定义配置

### 修改GPU规格

编辑 `playbook.yml` 中的 `gpu_specs` 变量：

```yaml
gpu_specs:
  "RTX 3080":
    max_power: 320
    max_temp: 83
    boost_clock: 1710
    expected_gflops: 29700
  "自定义GPU":
    max_power: 400
    max_temp: 85
    boost_clock: 2000
    expected_gflops: 50000
```

### 修改监控参数

在inventory文件中设置变量：

```yaml
vars:
  monitor_interval: 2        # 2秒间隔
  save_interval: 60        # 60次迭代保存
  max_memory_samples: 2000 # 最大2000个样本
  log_level: "DEBUG"       # 调试日志级别
```

### 添加新的目标主机

在inventory文件中添加新主机：

```yaml
gpu_nodes:
  hosts:
    gpu-node-4:
      ansible_host: 192.168.1.103
      ansible_user: ubuntu
      gpu_count: 1
      gpu_type: "RTX 3060"
```

## 🎯 最佳实践

### 1. 安全配置
- 使用SSH密钥认证
- 限制SSH访问权限
- 定期更新系统和依赖

### 2. 性能优化
- 根据GPU类型调整监控间隔
- 合理设置内存样本数量
- 定期清理日志文件

### 3. 监控和维护
- 设置日志轮转
- 监控磁盘空间使用
- 定期检查服务状态

### 4. 备份策略
- 定期备份配置文件
- 备份监控数据
- 保存部署脚本版本

## 📞 支持和帮助

如果遇到问题，可以：

1. 查看详细日志：`sudo journalctl -u gpu-monitor -f`
2. 检查配置文件：`cat /opt/gpu-analysis/config/config.json`
3. 运行状态检查：`/opt/gpu-analysis/check_status.sh`
4. 查看项目文档：`ansible/README.md`

## 📄 许可证

本项目采用MIT许可证，详见LICENSE文件。
