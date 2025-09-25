# GPU分析项目 - Ansible自动化部署

这个目录包含了使用Ansible自动化部署GPU分析项目的所有配置文件和脚本。

## 📁 文件结构

```
ansible/
├── inventory.yml              # 主机清单文件
├── playbook.yml              # 主要部署playbook
├── requirements.txt          # Python依赖包
├── ansible.cfg               # Ansible配置文件
├── deploy.sh                 # 部署脚本
├── templates/                # 配置模板目录
│   └── config.json.j2        # 配置文件模板
└── README.md                 # 本文档
```

## 🚀 快速开始

### 1. 环境准备

确保已安装以下软件：
- Ansible >= 2.9
- Python >= 3.6
- SSH客户端
- 目标主机已配置SSH密钥认证

### 2. 配置主机清单

编辑 `inventory.yml` 文件，配置你的目标主机：

```yaml
all:
  children:
    gpu_nodes:
      hosts:
        gpu-node-1:
          ansible_host: 192.168.1.100
          ansible_user: ubuntu
          gpu_count: 2
          gpu_type: "RTX 3080"
```

### 3. 运行部署

```bash
# 基本部署
./deploy.sh

# 详细输出
./deploy.sh -v

# 试运行模式
./deploy.sh -d

# 部署到特定组
./deploy.sh -g gpu_nodes
```

## 📋 详细说明

### 主机清单配置 (inventory.yml)

主机清单文件定义了目标主机和变量：

```yaml
gpu_nodes:
  hosts:
    gpu-node-1:
      ansible_host: 192.168.1.100    # 主机IP
      ansible_user: ubuntu            # SSH用户
      gpu_count: 2                    # GPU数量
      gpu_type: "RTX 3080"           # GPU类型
  vars:
    project_path: "/opt/gpu-analysis"  # 项目路径
    python_version: "3.9"             # Python版本
```

### 支持的GPU类型

系统支持以下GPU类型，会自动配置相应的规格参数：

- **RTX 3080**: 320W, 83°C, 1710MHz
- **RTX 4090**: 450W, 83°C, 2520MHz  
- **RTX 3060**: 170W, 83°C, 1777MHz
- **默认**: 360W, 83°C, 2620MHz

### 配置参数

可以通过inventory文件或命令行参数自定义以下配置：

#### 监控配置
- `monitor_interval`: 数据收集间隔（秒）
- `save_interval`: 数据保存间隔（迭代次数）
- `max_memory_samples`: 最大内存样本数

#### 性能阈值
- `excellent_utilization`: 优秀利用率阈值（%）
- `good_utilization`: 良好利用率阈值（%）
- `high_temp_warning`: 高温警告阈值（°C）
- `critical_temp`: 临界温度阈值（°C）

#### GPU规格
- `max_power`: 最大功率（瓦特）
- `max_temp`: 最大温度（摄氏度）
- `boost_clock`: 加速时钟频率（MHz）
- `expected_gflops`: 预期GFLOPS性能

## 🛠️ 部署流程

Ansible playbook会执行以下步骤：

1. **系统检查**
   - 验证操作系统兼容性
   - 检查Python版本
   - 验证NVIDIA驱动

2. **环境准备**
   - 安装系统依赖包
   - 创建项目目录结构
   - 设置Python虚拟环境

3. **项目部署**
   - 复制项目文件
   - 安装Python依赖
   - 生成配置文件

4. **脚本配置**
   - 创建手动运行脚本
   - 创建后台运行脚本
   - 创建管理脚本

5. **验证部署**
   - 检查文件完整性
   - 验证脚本可用性
   - 创建管理脚本

## 📊 部署后管理

### 手动运行

```bash
# 直接运行监控（前台）
./run_monitor.sh

# 后台运行监控
./start_background.sh

# 停止监控
./stop_monitor.sh

# 检查状态
./check_status.sh
```

### 快速脚本

部署后会在项目目录创建以下管理脚本：

- `run_monitor.sh`: 手动运行监控（前台）
- `start_background.sh`: 后台运行监控
- `stop_monitor.sh`: 停止监控进程
- `check_status.sh`: 检查运行状态

### 数据文件

- **配置文件**: `/opt/gpu-analysis/config/config.json`
- **数据文件**: `/opt/gpu-analysis/data/gpu_monitor.json`
- **日志文件**: `/opt/gpu-analysis/logs/gpu_analysis.log`

## 🔧 故障排除

### 常见问题

1. **SSH连接失败**
   ```bash
   # 检查SSH密钥
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   ssh-copy-id user@target-host
   ```

2. **Python依赖安装失败**
   ```bash
   # 手动安装依赖
   pip3 install -r requirements.txt
   ```

3. **NVIDIA驱动问题**
   ```bash
   # 检查驱动状态
   nvidia-smi
   
   # 安装驱动（Ubuntu）
   sudo apt install nvidia-driver-525
   ```

4. **权限问题**
   ```bash
   # 检查用户权限
   sudo usermod -aG docker $USER
   ```

### 调试模式

使用详细输出模式查看详细执行过程：

```bash
./deploy.sh -v
```

### 试运行模式

在正式部署前先试运行：

```bash
./deploy.sh -d
```

## 📈 监控数据

部署完成后，可以通过以下方式查看监控数据：

```bash
# 实时查看数据
watch -n 1 'cat /opt/gpu-analysis/data/gpu_monitor.json'

# 查看历史数据
ls -la /opt/gpu-analysis/data/

# 分析数据
python3 -c "
import json
with open('/opt/gpu-analysis/data/gpu_monitor.json', 'r') as f:
    data = json.load(f)
    print(json.dumps(data, indent=2))
"
```

## 🔄 更新部署

要更新已部署的项目：

```bash
# 重新运行部署脚本
./deploy.sh

# 或者只更新特定组件
ansible-playbook -i inventory.yml playbook.yml --tags update
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
```

### 修改监控参数

在inventory文件中设置变量：

```yaml
vars:
  monitor_interval: 2
  save_interval: 60
  max_memory_samples: 2000
```

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个Ansible部署方案。

## 📄 许可证

本项目采用MIT许可证。
