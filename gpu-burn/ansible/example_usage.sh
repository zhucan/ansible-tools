#!/bin/bash
# GPU分析项目 - 使用示例脚本
# 演示如何使用Ansible部署GPU分析项目

set -euo pipefail

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "GPU分析项目 - Ansible使用示例"
echo "=========================================="
echo ""

# 检查Ansible是否安装
if ! command -v ansible-playbook &> /dev/null; then
    echo "❌ Ansible未安装，请先安装Ansible"
    echo ""
    echo "安装方法:"
    echo "  Ubuntu/Debian: sudo apt install ansible"
    echo "  CentOS/RHEL: sudo yum install ansible"
    echo "  macOS: brew install ansible"
    echo "  pip: pip install ansible"
    exit 1
fi

echo "✅ Ansible已安装"
echo ""

# 显示当前配置
echo "📋 当前配置:"
echo "  项目目录: $SCRIPT_DIR"
echo "  Inventory文件: $SCRIPT_DIR/inventory.yml"
echo "  Playbook文件: $SCRIPT_DIR/playbook.yml"
echo ""

# 显示可用的部署选项
echo "🚀 可用的部署选项:"
echo ""
echo "1. 基本部署 (推荐)"
echo "   ./deploy.sh"
echo ""
echo "2. 详细输出部署"
echo "   ./deploy.sh -v"
echo ""
echo "3. 试运行模式 (不实际部署)"
echo "   ./deploy.sh -d"
echo ""
echo "4. 部署到特定组"
echo "   ./deploy.sh -g gpu_nodes"
echo ""
echo "5. 检查模式"
echo "   ./deploy.sh -c"
echo ""

# 显示目标主机
echo "🎯 目标主机配置:"
if [[ -f "$SCRIPT_DIR/inventory.yml" ]]; then
    echo "  从inventory.yml读取主机配置..."
    ansible-inventory -i "$SCRIPT_DIR/inventory.yml" --list 2>/dev/null | jq -r '.gpu_nodes.hosts | keys[]' 2>/dev/null || echo "  无法解析主机列表"
else
    echo "  ❌ inventory.yml文件不存在"
fi
echo ""

# 显示GPU类型支持
echo "🎮 支持的GPU类型:"
echo "  - RTX 3080 (320W, 83°C, 1710MHz)"
echo "  - RTX 4090 (450W, 83°C, 2520MHz)"
echo "  - RTX 3060 (170W, 83°C, 1777MHz)"
echo "  - 默认配置 (360W, 83°C, 2620MHz)"
echo ""

# 显示部署后的管理命令
echo "🛠️ 部署后的管理命令:"
echo ""
echo "服务管理:"
echo "  sudo systemctl start gpu-monitor     # 启动服务"
echo "  sudo systemctl stop gpu-monitor      # 停止服务"
echo "  sudo systemctl status gpu-monitor    # 查看状态"
echo "  sudo journalctl -u gpu-monitor -f     # 查看日志"
echo ""
echo "数据查看:"
echo "  cat /opt/gpu-analysis/data/gpu_monitor.json"
echo "  watch -n 1 'cat /opt/gpu-analysis/data/gpu_monitor.json'"
echo ""
echo "快速脚本:"
echo "  /opt/gpu-analysis/start_monitor.sh   # 启动监控"
echo "  /opt/gpu-analysis/stop_monitor.sh    # 停止监控"
echo "  /opt/gpu-analysis/check_status.sh    # 检查状态"
echo ""

# 询问是否开始部署
echo "❓ 是否开始部署? (y/N)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 开始部署..."
    echo ""
    
    # 运行部署脚本
    if [[ -f "$SCRIPT_DIR/deploy.sh" ]]; then
        chmod +x "$SCRIPT_DIR/deploy.sh"
        "$SCRIPT_DIR/deploy.sh"
    else
        echo "❌ deploy.sh脚本不存在"
        exit 1
    fi
else
    echo ""
    echo "👋 部署已取消"
    echo ""
    echo "💡 提示: 你可以随时运行以下命令开始部署:"
    echo "   cd $SCRIPT_DIR"
    echo "   ./deploy.sh"
fi
