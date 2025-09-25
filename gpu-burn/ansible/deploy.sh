#!/bin/bash
# GPU分析项目 - Ansible部署脚本
# 用于自动化部署GPU分析项目到多台服务器

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 默认配置
INVENTORY_FILE="${SCRIPT_DIR}/inventory.yml"
PLAYBOOK_FILE="${SCRIPT_DIR}/playbook.yml"
ANSIBLE_CONFIG="${SCRIPT_DIR}/ansible.cfg"
VERBOSE=""
DRY_RUN=""
TARGET_GROUP="gpu_nodes"

# 帮助信息
show_help() {
    cat << EOF
GPU分析项目 - Ansible部署脚本

用法: $0 [选项]

选项:
    -i, --inventory FILE    指定inventory文件 (默认: $INVENTORY_FILE)
    -p, --playbook FILE     指定playbook文件 (默认: $PLAYBOOK_FILE)
    -g, --group GROUP       指定目标组 (默认: $TARGET_GROUP)
    -v, --verbose           详细输出
    -d, --dry-run           试运行模式
    -c, --check             检查模式
    -h, --help              显示此帮助信息

示例:
    $0                                    # 使用默认配置部署
    $0 -v                                # 详细输出部署
    $0 -d                                # 试运行模式
    $0 -g local_dev                      # 部署到本地开发环境
    $0 -i custom_inventory.yml           # 使用自定义inventory

环境变量:
    ANSIBLE_CONFIG         Ansible配置文件路径
    ANSIBLE_HOST_KEY_CHECKING  是否检查主机密钥 (默认: False)
    ANSIBLE_SSH_PIPELINING      SSH管道化 (默认: True)

EOF
}

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    # 检查Ansible
    if ! command -v ansible-playbook &> /dev/null; then
        log_error "Ansible未安装，请先安装Ansible"
        echo "安装方法:"
        echo "  Ubuntu/Debian: sudo apt install ansible"
        echo "  CentOS/RHEL: sudo yum install ansible"
        echo "  macOS: brew install ansible"
        echo "  pip: pip install ansible"
        exit 1
    fi
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3未安装"
        exit 1
    fi
    
    # 检查SSH
    if ! command -v ssh &> /dev/null; then
        log_error "SSH未安装"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 验证配置文件
validate_config() {
    log_info "验证配置文件..."
    
    # 检查inventory文件
    if [[ ! -f "$INVENTORY_FILE" ]]; then
        log_error "Inventory文件不存在: $INVENTORY_FILE"
        exit 1
    fi
    
    # 检查playbook文件
    if [[ ! -f "$PLAYBOOK_FILE" ]]; then
        log_error "Playbook文件不存在: $PLAYBOOK_FILE"
        exit 1
    fi
    
    # 检查requirements文件
    if [[ ! -f "${SCRIPT_DIR}/requirements.txt" ]]; then
        log_error "Requirements文件不存在: ${SCRIPT_DIR}/requirements.txt"
        exit 1
    fi
    
    # 检查模板文件
    if [[ ! -d "${SCRIPT_DIR}/templates" ]]; then
        log_error "Templates目录不存在: ${SCRIPT_DIR}/templates"
        exit 1
    fi
    
    log_success "配置文件验证通过"
}

# 测试连接
test_connections() {
    log_info "测试目标主机连接..."
    
    local failed_hosts=()
    
    # 获取目标主机列表
    local hosts=$(ansible-inventory -i "$INVENTORY_FILE" --list | jq -r ".${TARGET_GROUP}.hosts[]?" 2>/dev/null || echo "")
    
    if [[ -z "$hosts" ]]; then
        log_warning "未找到目标组: $TARGET_GROUP"
        return 0
    fi
    
    for host in $hosts; do
        log_info "测试连接: $host"
        if ansible "$host" -i "$INVENTORY_FILE" -m ping &>/dev/null; then
            log_success "连接成功: $host"
        else
            log_error "连接失败: $host"
            failed_hosts+=("$host")
        fi
    done
    
    if [[ ${#failed_hosts[@]} -gt 0 ]]; then
        log_error "以下主机连接失败: ${failed_hosts[*]}"
        log_info "请检查:"
        log_info "  1. SSH密钥配置"
        log_info "  2. 主机网络连接"
        log_info "  3. 用户名和权限"
        return 1
    fi
    
    log_success "所有主机连接正常"
}

# 运行Ansible
run_ansible() {
    local ansible_args=()
    
    # 基本参数
    ansible_args+=("-i" "$INVENTORY_FILE")
    ansible_args+=("$PLAYBOOK_FILE")
    
    # 目标组
    if [[ -n "$TARGET_GROUP" ]]; then
        ansible_args+=("--limit" "$TARGET_GROUP")
    fi
    
    # 详细输出
    if [[ "$VERBOSE" == "true" ]]; then
        ansible_args+=("-vvv")
    fi
    
    # 试运行模式
    if [[ "$DRY_RUN" == "true" ]]; then
        ansible_args+=("--check")
        ansible_args+=("--diff")
    fi
    
    # 检查模式
    if [[ "$CHECK_MODE" == "true" ]]; then
        ansible_args+=("--check")
    fi
    
    log_info "运行Ansible playbook..."
    log_info "命令: ansible-playbook ${ansible_args[*]}"
    
    # 设置环境变量
    export ANSIBLE_HOST_KEY_CHECKING=False
    export ANSIBLE_SSH_PIPELINING=True
    export ANSIBLE_RETRY_FILES_ENABLED=False
    
    # 运行Ansible
    if ansible-playbook "${ansible_args[@]}"; then
        log_success "部署完成！"
        return 0
    else
        log_error "部署失败！"
        return 1
    fi
}

# 显示部署后信息
show_post_deployment_info() {
    log_info "部署后信息:"
    echo ""
    echo "=== 运行方式 ==="
    echo "前台运行: ./run_monitor.sh"
    echo "后台运行: ./start_background.sh"
    echo "停止监控: ./stop_monitor.sh"
    echo "检查状态: ./check_status.sh"
    echo ""
    echo "=== 项目文件位置 ==="
    echo "项目路径: /opt/gpu-analysis"
    echo "配置文件: /opt/gpu-analysis/config/config.json"
    echo "数据文件: /opt/gpu-analysis/data/"
    echo "日志文件: /opt/gpu-analysis/logs/"
    echo ""
    echo "=== 管理脚本 ==="
    echo "手动运行: /opt/gpu-analysis/run_monitor.sh"
    echo "后台运行: /opt/gpu-analysis/start_background.sh"
    echo "停止监控: /opt/gpu-analysis/stop_monitor.sh"
    echo "检查状态: /opt/gpu-analysis/check_status.sh"
    echo ""
    echo "=== 监控数据 ==="
    echo "数据文件: /opt/gpu-analysis/data/gpu_monitor.json"
    echo "实时监控: watch -n 1 'cat /opt/gpu-analysis/data/gpu_monitor.json'"
    echo "后台日志: tail -f /opt/gpu-analysis/logs/monitor.log"
}

# 主函数
main() {
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -i|--inventory)
                INVENTORY_FILE="$2"
                shift 2
                ;;
            -p|--playbook)
                PLAYBOOK_FILE="$2"
                shift 2
                ;;
            -g|--group)
                TARGET_GROUP="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE="true"
                shift
                ;;
            -d|--dry-run)
                DRY_RUN="true"
                shift
                ;;
            -c|--check)
                CHECK_MODE="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 显示开始信息
    echo "=========================================="
    echo "GPU分析项目 - Ansible部署脚本"
    echo "=========================================="
    echo ""
    
    # 执行部署流程
    check_dependencies
    validate_config
    
    if [[ "$DRY_RUN" != "true" && "$CHECK_MODE" != "true" ]]; then
        test_connections
    fi
    
    if run_ansible; then
        if [[ "$DRY_RUN" != "true" && "$CHECK_MODE" != "true" ]]; then
            show_post_deployment_info
        fi
        log_success "部署完成！"
    else
        log_error "部署失败！"
        exit 1
    fi
}

# 运行主函数
main "$@"
