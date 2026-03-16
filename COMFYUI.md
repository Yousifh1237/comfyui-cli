# COMFYUI.md - 标准操作说明

## 概览

ComfyUI 是一个基于节点的 Stable Diffusion 图像生成 GUI。它以本地 Web 服务器形式运行（默认 `http://127.0.0.1:8188`），并提供 REST API 与 WebSocket 接口。

## 架构

```
ComfyUI Server (aiohttp)
  ├── REST API (HTTP)
  │   ├── /prompt          - Submit/query workflows
  │   ├── /queue            - Queue management
  │   ├── /history          - Execution history
  │   ├── /models/{type}    - Model listing
  │   ├── /object_info      - Node definitions
  │   ├── /upload/image     - Image upload
  │   ├── /view             - Image download
  │   ├── /system_stats     - Hardware info
  │   ├── /interrupt        - Cancel execution
  │   └── /free             - Release memory
  ├── WebSocket (/ws)
  │   └── Real-time events (progress, executing, executed, errors)
  └── Execution Engine
      ├── PromptQueue       - Priority queue
      ├── PromptExecutor    - Node graph execution
      └── Cache             - Output caching (LRU/classic)
```

## CLI 命令映射

| CLI Command                       | API Call                          |
|-----------------------------------|-----------------------------------|
| `workflow run <file>`             | POST /prompt + 轮询 /history       |
| `workflow validate <file>`        | 本地校验                           |
| `workflow info <file>`            | 本地分析                           |
| `queue status`                    | GET /queue                        |
| `queue clear`                     | POST /queue {clear: true}         |
| `models list [type]`             | GET /models/{type}                |
| `models types`                    | GET /models                       |
| `models metadata <type> <name>`  | GET /view_metadata/{type}         |
| `nodes list`                      | GET /object_info                  |
| `nodes info <class>`             | GET /object_info/{class}          |
| `nodes search <query>`           | GET /object_info + 过滤            |
| `history list`                    | GET /history                      |
| `history get <id>`               | GET /history/{id}                 |
| `images upload <file>`           | POST /upload/image                |
| `images download <name>`         | GET /view                         |
| `system stats`                    | GET /system_stats                 |
| `system interrupt`               | POST /interrupt                   |
| `system free`                     | POST /free                        |
| `system ping`                     | GET /system_stats（连通性检查）     |
| `generate txt2img --prompt ...`  | POST /prompt（构建工作流）          |
| `generate img2img --prompt ...`  | POST /prompt（构建工作流）          |
| `generate diverse <file>`       | POST /prompt（变体参数）            |
| `generate lora-sweep <file>`    | POST /prompt（权重扫描）            |
| `generate styles`               | 本地风格预设                       |
| `config show/set/reset`          | 本地配置文件                       |
| `repl`                            | 交互式会话                         |

## 工作流格式

ComfyUI 工作流是一个 JSON 字典，使用节点 ID 映射到对应的节点定义：

```json
{
  "1": {
    "class_type": "CheckpointLoaderSimple",
    "inputs": {"ckpt_name": "model.safetensors"}
  },
  "2": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 42,
      "model": ["1", 0],
      "positive": ["3", 0],
      "negative": ["4", 0],
      "latent_image": ["5", 0]
    }
  }
}
```

节点之间的连接使用 `[source_node_id, output_index]` 元组表示。

## 常用 Sampler

euler, euler_ancestral, heun, dpm_2, dpm_2_ancestral, lms, dpm_fast,
dpm_adaptive, dpmpp_2s_ancestral, dpmpp_sde, dpmpp_2m, dpmpp_3m_sde,
ddim, uni_pc

## 常用 Scheduler

normal, karras, exponential, simple, ddim_uniform, sgm_uniform, beta

## 模型类型

checkpoints, loras, vae, text_encoders, diffusion_models, clip_vision,
controlnet, upscale_models, embeddings, diffusers
