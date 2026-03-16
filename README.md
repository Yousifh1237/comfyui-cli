# comfyui-cli

`comfyui-cli` 是一个面向 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 的命令行工具，用来通过终端完成工作流执行、模型查询、队列管理、节点信息查看以及基础生成任务。

## 功能概览

- 执行与校验 ComfyUI 工作流
- 查看模型、节点、队列、历史记录与系统状态
- 支持 `txt2img`、`img2img`、LoRA 与风格化生成辅助命令
- 支持 `--json` 机器可读输出
- 提供可安装的命令入口：`comfyui-cli`

## 安装

```bash
git clone https://github.com/XXXxx7258/comfyui-cli.git
cd comfyui-cli
python -m pip install -e .
```

安装完成后，可通过以下命令检查是否可用：

```bash
comfyui-cli --version
```

## 前置条件

需要先启动一个正在运行的 ComfyUI 服务器（默认：`http://127.0.0.1:8188`）。

```bash
python main.py --listen 127.0.0.1 --port 8188
```

## 快速开始

```bash
# 检查服务连通性
comfyui-cli system ping

# 列出 checkpoints
comfyui-cli models list checkpoints

# 执行工作流
comfyui-cli workflow run my_workflow.json --save-to ./output

# 输出 JSON
comfyui-cli --json system stats
```

## 常用场景

### 校验工作流

```bash
comfyui-cli workflow validate my_workflow.json
```

### 查看模型类型

```bash
comfyui-cli models types
```

### 查看节点列表

```bash
comfyui-cli nodes list
```

### 执行 txt2img

```bash
comfyui-cli generate txt2img --prompt "a cat" --checkpoint "model.safetensors"
```

## 常用命令

```bash
comfyui-cli workflow validate <file>
comfyui-cli workflow info <file>
comfyui-cli queue status
comfyui-cli models types
comfyui-cli nodes list
comfyui-cli history list
comfyui-cli generate txt2img --prompt "a cat" --checkpoint "model.safetensors"
```

## 项目结构

```text
.
├── README.md
├── COMFYUI.md
├── setup.py
└── comfyui/
    ├── comfyui_cli.py
    ├── core/
    ├── utils/
    └── tests/
```

## 测试

运行核心单元测试：

```bash
pytest comfyui/tests/test_core.py -v
```

如果需要连接真实 ComfyUI 服务执行 E2E 测试：

```bash
export COMFYUI_TEST_SERVER=127.0.0.1:8188
export COMFYUI_TEST_CHECKPOINT=your_model.safetensors
pytest comfyui/tests/test_full_e2e.py -v
```

## 相关文档

- `COMFYUI.md`：ComfyUI API 与命令映射说明
