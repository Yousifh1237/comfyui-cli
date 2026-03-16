# comfyui-cli

这是一个面向 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 的命令行界面，用于操作这个基于节点的 Stable Diffusion GUI。

## 安装

```bash
cd agent-harness
pip install -e .
```

安装完成后，可通过 `comfyui-cli` 使用 CLI。

## 前置条件

需要先启动一个正在运行的 ComfyUI 服务器（默认：`http://127.0.0.1:8188`）。

```bash
# Start ComfyUI
python main.py --listen 127.0.0.1 --port 8188
```

## 快速开始

```bash
# Check server connectivity
comfyui-cli system ping

# List available checkpoints
comfyui-cli models list checkpoints

# Generate an image from text
comfyui-cli generate txt2img \
  --prompt "a beautiful sunset over mountains" \
  --negative "ugly, blurry" \
  --checkpoint "v1-5-pruned-emaonly.safetensors" \
  --width 512 --height 512 \
  --steps 20 --cfg 7.0 \
  --save-to ./my-outputs

# Run a saved workflow
comfyui-cli workflow run my_workflow.json --save-to ./output

# Run with overrides
comfyui-cli workflow run my_workflow.json \
  --seed 42 \
  --prompt "new prompt text" \
  --steps 30
```

## 命令说明

### 工作流管理

```bash
workflow run <file>       # Execute a workflow JSON
workflow validate <file>  # Validate workflow structure
workflow info <file>      # Show workflow details
```

### 队列管理

```bash
queue status              # Show queue status
queue clear               # Clear pending queue
queue delete <id> ...     # Delete specific items
```

### 模型管理

```bash
models types              # List model folder types
models list [folder]      # List models (default: checkpoints)
models metadata <f> <n>   # Get safetensors metadata
models embeddings         # List embeddings
```

### 节点信息

```bash
nodes list [--category X] # List all nodes
nodes info <class>        # Detailed node info
nodes search <query>      # Search by name/category
```

### 历史记录

```bash
history list [--max-items N]  # Recent history
history get <prompt_id>       # Specific execution
history clear                 # Clear all
```

### 图片操作

```bash
images upload <file> [--type input]         # Upload image
images download <name> --save-to <path>     # Download image
```

### 系统操作

```bash
system stats              # GPU/CPU/RAM info
system ping               # Server connectivity check
system interrupt          # Cancel current execution
system free               # Release GPU memory
system extensions         # List extensions
```

### 生成功能

```bash
generate txt2img --prompt "..." --checkpoint "..."
generate img2img --prompt "..." --checkpoint "..." --image "..." --denoise 0.7
generate txt2img-lora --prompt "..." --checkpoint "..." --lora "..." --lora-strength 0.7
generate upscale --image "..." --model "RealESRGAN_x4plus.pth"

# NEW: Diverse generation (avoid same-face syndrome)
generate diverse <workflow.json> --count 8 --style cyberpunk --save-to ./output
generate lora-sweep <workflow.json> --start 0.4 --end 0.8 --steps 5 --save-to ./output
generate styles  # List available style presets
```

#### 多样化生成功能

`generate diverse` 命令用于生成**同一角色在不同艺术风格下的图像**：
- 保持角色身份特征（来自你的 LoRA 和基础提示词）
- 应用不同的艺术风格（cyberpunk、fantasy、realistic、anime、painterly、minimalist）
- 动态调整 LoRA 权重（0.6-0.75 区间，以获得更合适的结果）
- 使用随机种子带来自然变化

`generate lora-sweep` 命令用于测试多个 LoRA 权重，从而找到更合适的平衡点。

示例工作流：
```bash
# Generate Wakaba Mutsumi in 6 different artistic styles
comfyui-cli generate diverse wakaba_workflow.json \
  --count 6 \
  --styles "cyberpunk,fantasy,anime,painterly,realistic,minimalist" \
  --save-to ./wakaba_styles

# Or let it randomly pick styles
comfyui-cli generate diverse wakaba_workflow.json \
  --count 8 \
  --save-to ./output

# Test LoRA weights from 0.4 to 0.8
comfyui-cli generate lora-sweep wakaba_workflow.json \
  --start 0.4 \
  --end 0.8 \
  --steps 5 \
  --save-to ./lora_test
```


### 配置

```bash
config show               # Show config
config set host 0.0.0.0   # Set a value
config reset              # Reset to defaults
```

### REPL 模式

```bash
comfyui-cli repl
```

这是一个带有 Tab 补全和命令历史记录的交互式会话。

## JSON 输出

所有命令都支持 `--json` 参数，用于输出机器可读结果：

```bash
comfyui-cli --json models list checkpoints
comfyui-cli --json system stats
comfyui-cli --json workflow run my_workflow.json
```

## 配置文件

配置文件路径：`~/.comfyui-cli.json`

```json
{
  "host": "127.0.0.1",
  "port": 8188,
  "ssl": false,
  "default_output_dir": "./output",
  "poll_interval": 1.0,
  "timeout": 600.0
}
```

环境变量（前缀为 `COMFYUI_CLI_`）：

```bash
export COMFYUI_CLI_HOST=192.168.1.100
export COMFYUI_CLI_PORT=8188
```

## 架构

```
comfyui/
├── comfyui_cli.py        # Main CLI (Click-based)
├── core/
│   ├── client.py         # HTTP/WebSocket client
│   ├── workflow.py       # Workflow loading/manipulation
│   └── generate.py       # txt2img/img2img templates
├── utils/
│   ├── config.py         # Configuration management
│   └── formatters.py     # Output formatting
└── tests/
    ├── test_core.py      # Unit tests
    └── test_full_e2e.py  # E2E tests
```
