#!/bin/bash

# SDEV 自动构建并上传到 PyPI 脚本
# 1. 自动从 git 分支名获取版本号（如 0.1.2）
# 2. 自动更新 setup.py/pyproject.toml/__init__.py 版本号
# 3. 自动清理、构建、上传
# 4. 使用 api_key 文件作为 PyPI Token
# 5. 仅需运行本脚本，无需其它脚本

set -e

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查依赖
if ! command -v git &>/dev/null; then error "git 未安装"; exit 1; fi
if ! command -v python &>/dev/null; then error "python 未安装"; exit 1; fi
if ! python -c "import build" &>/dev/null; then info "安装 build..."; pip install build; fi
if ! python -c "import twine" &>/dev/null; then info "安装 twine..."; pip install twine; fi

# 获取分支名作为版本号
branch=$(git branch --show-current)
if [[ ! "$branch" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then error "分支名 '$branch' 必须为 x.y.z 版本号格式"; exit 1; fi
version=$branch
info "当前版本: $version"

# 更新版本号
sed -i "s/version=\"[^\"]*\"/version=\"$version\"/" setup.py
sed -i "s/version = \"[^\"]*\"/version = \"$version\"/" pyproject.toml
sed -i "s/__version__ = \"[^\"]*\"/__version__ = \"$version\"/" sdev/__init__.py
success "版本号已更新为 $version"

# 清理
rm -rf build/ dist/ *.egg-info/ sdev.egg-info/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
success "清理完成"

# 构建
info "开始构建..."
python -m build
success "构建完成"

# 检查 api_key
if [[ ! -f "api_key" ]]; then error "api_key 文件不存在"; exit 1; fi
api_key=$(cat api_key)
if [[ -z "$api_key" ]]; then error "api_key 文件为空"; exit 1; fi
success "API 密钥检查通过"

# 上传
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="$api_key"
export TWINE_DISABLE_PROMPT=1
info "上传到 PyPI..."
twine upload dist/*
if [[ $? -eq 0 ]]; then
  success "上传成功"
else
  error "上传失败"
  exit 1
fi
unset TWINE_USERNAME TWINE_PASSWORD TWINE_DISABLE_PROMPT

# 验证
sleep 5
pip install --upgrade sdev==$version && success "PyPI 安装验证通过" || warning "PyPI 安装验证失败，可能需要等待同步"

success "全部流程完成！版本 $version 已发布。"