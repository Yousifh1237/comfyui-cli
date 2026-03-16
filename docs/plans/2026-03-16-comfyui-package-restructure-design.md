# comfyui-cli Package Restructure Design

## Goal

将当前基于 `comfyui/` 的模板化目录结构迁移为标准独立 Python CLI 项目结构，去掉 `cli_anything/` 这一层，使仓库更适合长期维护、公开展示和后续发布。

## Approved Design

### Target Structure

```text
agent-harness/
├── .gitignore
├── README.md
├── COMFYUI.md
├── setup.py
└── comfyui/
    ├── __init__.py
    ├── comfyui_cli.py
    ├── core/
    ├── utils/
    └── tests/
```

### Scope

本次迁移会调整：

- 目录结构
- Python import 路径
- `setup.py` 打包配置
- 测试路径与测试命令
- README 与相关文档中的结构说明

本次迁移不会调整：

- CLI 功能行为
- 命令参数设计
- ComfyUI API 交互逻辑
- 被 `.gitignore` 排除的 workflow 示例与本地辅助脚本策略

### Packaging Decisions

- 对外命令保持为 `comfyui-cli`
- 仓库名保持为 `comfyui-cli`
- Python 包改为普通单包结构：`comfyui`
- `setup.py` 改为使用 `find_packages(include=["comfyui", "comfyui.*"])`
- `entry_points` 改为 `comfyui-cli=comfyui.comfyui_cli:main`
- `long_description` 改为读取仓库根目录 `README.md`

### Validation Requirements

迁移完成后必须重新验证：

- `python -m pip install -e .`
- `comfyui-cli --version`
- `pytest comfyui/tests/test_core.py -v`

### Risks

- 导入路径替换不完整导致运行时失败
- 打包配置未同步导致命令入口失效
- 文档仍引用旧路径导致说明不一致

### Mitigation

- 统一搜索并替换 `comfyui` 与 `comfyui`
- 安装验证与完整核心测试必须在迁移后重新执行
- 提交前再次搜索旧路径残留
