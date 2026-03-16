# TEST.md - 测试计划与结果

## 测试计划

### 单元测试（`test_core.py`）

测试使用合成数据和模拟 HTTP，请求时不需要启动实际服务器。

#### 工作流测试
- `test_from_dict_api_format` - 解析 API 格式工作流
- `test_from_dict_wrapped_format` - 解析包装格式（包含 `"prompt"` 键）
- `test_from_json` - 从 JSON 字符串解析
- `test_from_file` / `test_from_file_not_found` - 文件加载
- `test_to_dict` / `test_to_json` - 序列化
- `test_save_and_load` - 保存 / 加载往返验证
- `test_get_node` - 按 ID 获取节点
- `test_get_nodes_by_type` - 按 `class_type` 过滤
- `test_get_output_nodes` - 查找输出节点
- `test_get_class_types` - 列出唯一类型
- `test_set_input` / `test_set_input_nonexistent_node` - 修改输入
- `test_set_seed` - 覆盖 `KSampler` 节点的种子
- `test_set_prompt_text` / `test_set_negative_text` - 覆盖提示词文本
- `test_set_checkpoint` - 覆盖模型
- `test_set_image_size` - 覆盖图像尺寸
- `test_validate_structure_valid` / `_empty` / `_missing_class_type` / `_broken_link` - 结构校验
- `test_summary` - 生成工作流摘要

#### Client 测试（模拟 HTTP）
- `test_init_defaults` / `test_init_custom` - Client 初始化
- `test_get_system_stats` - 系统信息
- `test_get_model_types` / `test_get_models` - 模型列表
- `test_queue_prompt` - 工作流提交
- `test_get_queue` / `test_get_history` / `test_get_node_info` - 数据获取
- `test_interrupt` - 中断信号
- `test_is_server_running_true` / `_false` - 连通性检查
- `test_api_error` / `test_connection_error` - 错误处理

#### Generate 测试
- `test_txt2img_basic` / `_custom_params` / `_is_valid_workflow` - `txt2img` 模板
- `test_img2img_basic` / `_denoise` / `_is_valid_workflow` - `img2img` 模板

#### Formatter 测试
- `test_format_json` / `test_format_table` / `_empty` - 格式化函数
- `test_format_list` / `_empty` - 列表格式化
- `test_format_kv` - 键值格式化
- `test_format_size` - 大小格式化
- `test_output_formatter_json_mode` / `_human_mode` - 输出模式切换

#### Config 测试
- `test_default_config` - 默认值
- `test_load_config_defaults` - 回退行为
- `test_get_server_args` - 参数提取

#### CLI 测试（Click CliRunner）
- `test_version` / `test_help` - 基础 CLI
- `test_workflow_validate` / `_info` / `_validate_json_mode` - 工作流命令
- `test_system_stats_json` / `test_system_ping_alive` / `_dead` - 系统命令
- `test_config_show` - 配置显示

#### Subprocess 测试
- `test_cli_version` / `_help` - 已安装 CLI 可执行文件
- `test_cli_workflow_validate` / `_json_mode` - 子进程执行

### E2E 测试（`test_full_e2e.py`）

要求：设置环境变量 `COMFYUI_TEST_SERVER=host:port`。

- 服务器连通性、系统状态
- 模型列表（types、checkpoints、loras、embeddings）
- 节点信息获取
- 队列操作
- 图片上传
- 完整 `txt2img` 执行（需要 `COMFYUI_TEST_CHECKPOINT`）
- 通过 CliRunner 连接真实服务器执行 CLI 命令

---

## 测试结果

### 单元测试 - PASSED ✓

**命令：** `pytest comfyui/tests/test_core.py -v`

**结果：** `95 passed in 1.24s`

```
comfyui\tests\test_core.py::TestWorkflow::test_from_dict_api_format PASSED
comfyui\tests\test_core.py::TestClient::test_get_system_stats PASSED
comfyui\tests\test_core.py::TestGenerate::test_txt2img_basic PASSED
comfyui\tests\test_core.py::TestGenerateLora::test_txt2img_lora_basic PASSED
comfyui\tests\test_core.py::TestGenerateUpscale::test_upscale_basic PASSED
comfyui\tests\test_core.py::TestClientNewMethods::test_get_folder_paths PASSED
comfyui\tests\test_core.py::TestCLINewCommands::test_system_paths_json PASSED
comfyui\tests\test_core.py::TestFormatters::test_format_json PASSED
comfyui\tests\test_core.py::TestConfig::test_default_config PASSED
comfyui\tests\test_core.py::TestCLI::test_version PASSED
comfyui\tests\test_core.py::TestDiverse::test_get_style_list PASSED
comfyui\tests\test_core.py::TestCLISubprocess::test_cli_version PASSED
...
============================= 95 passed in 1.24s ==============================
```

### 测试覆盖摘要

- **Workflow module:** 24 项测试 - 100% pass
- **Client module:** 14 项测试 - 100% pass
- **Generate module:** 6 项测试 - 100% pass
- **GenerateLora module:** 4 项测试 - 100% pass
- **GenerateUpscale module:** 3 项测试 - 100% pass
- **ClientNewMethods module:** 5 项测试 - 100% pass
- **CLINewCommands module:** 7 项测试 - 100% pass
- **Formatters module:** 8 项测试 - 100% pass
- **Config module:** 3 项测试 - 100% pass
- **CLI commands:** 8 项测试 - 100% pass
- **Diverse module:** 7 项测试 - 100% pass
- **Subprocess execution:** 4 项测试 - 100% pass

**总计：95/95 tests passed (100%)**

### E2E 测试

E2E 测试需要一个正在运行的 ComfyUI 服务器。执行方式如下：

```bash
# Start ComfyUI server
cd ComfyUI
python main.py --listen 127.0.0.1 --port 8188

# Run E2E tests
export COMFYUI_TEST_SERVER=127.0.0.1:8188
export COMFYUI_TEST_CHECKPOINT=your_model.safetensors
pytest comfyui/tests/test_full_e2e.py -v
```
