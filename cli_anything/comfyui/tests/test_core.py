"""Unit tests for comfyui-cli core modules.

Tests use synthetic data - no external dependencies or running server required.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# Workflow tests
# ============================================================
from cli_anything.comfyui.core.workflow import Workflow


class TestWorkflow:
    """Tests for the Workflow class."""

    SAMPLE_PROMPT = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a cat", "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "ugly", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]},
        },
    }

    def test_from_dict_api_format(self):
        wf = Workflow.from_dict(self.SAMPLE_PROMPT)
        assert wf.node_count == 7
        assert "1" in wf.node_ids

    def test_from_dict_wrapped_format(self):
        wrapped = {"prompt": self.SAMPLE_PROMPT}
        wf = Workflow.from_dict(wrapped)
        assert wf.node_count == 7

    def test_from_json(self):
        json_str = json.dumps(self.SAMPLE_PROMPT)
        wf = Workflow.from_json(json_str)
        assert wf.node_count == 7

    def test_from_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(self.SAMPLE_PROMPT, f)
            f.flush()
            path = f.name

        try:
            wf = Workflow.from_file(path)
            assert wf.node_count == 7
        finally:
            os.unlink(path)

    def test_from_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            Workflow.from_file("/nonexistent/file.json")

    def test_to_dict(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        d = wf.to_dict()
        assert d == self.SAMPLE_PROMPT

    def test_to_json(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        j = wf.to_json()
        parsed = json.loads(j)
        assert parsed == self.SAMPLE_PROMPT

    def test_save_and_load(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            wf.save(path)
            loaded = Workflow.from_file(path)
            assert loaded.node_count == wf.node_count
        finally:
            os.unlink(path)

    def test_get_node(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        node = wf.get_node("1")
        assert node["class_type"] == "CheckpointLoaderSimple"
        assert wf.get_node("999") is None

    def test_get_nodes_by_type(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        clip_nodes = wf.get_nodes_by_type("CLIPTextEncode")
        assert len(clip_nodes) == 2

    def test_get_output_nodes(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        outputs = wf.get_output_nodes()
        assert len(outputs) == 1
        assert "7" in outputs

    def test_get_class_types(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        types = wf.get_class_types()
        assert "KSampler" in types
        assert "SaveImage" in types

    def test_set_input(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        wf.set_input("5", "steps", 30)
        assert wf.get_input("5", "steps") == 30

    def test_set_input_nonexistent_node(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        with pytest.raises(KeyError):
            wf.set_input("999", "key", "val")

    def test_set_seed(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        modified = wf.set_seed(123)
        assert "5" in modified
        assert wf.get_input("5", "seed") == 123

    def test_set_prompt_text(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        modified = wf.set_prompt_text("a dog")
        assert len(modified) >= 1
        assert wf.get_input(modified[0], "text") == "a dog"

    def test_set_negative_text(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        modified = wf.set_negative_text("bad quality")
        assert len(modified) == 1
        # Should modify second CLIPTextEncode
        assert wf.get_input(modified[0], "text") == "bad quality"

    def test_set_checkpoint(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        modified = wf.set_checkpoint("new_model.safetensors")
        assert "1" in modified
        assert wf.get_input("1", "ckpt_name") == "new_model.safetensors"

    def test_set_image_size(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        modified = wf.set_image_size(1024, 768)
        assert "4" in modified
        assert wf.get_input("4", "width") == 1024
        assert wf.get_input("4", "height") == 768

    def test_validate_structure_valid(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        errors = wf.validate_structure()
        assert len(errors) == 0

    def test_validate_structure_empty(self):
        wf = Workflow({})
        errors = wf.validate_structure()
        assert len(errors) > 0

    def test_validate_structure_missing_class_type(self):
        data = {"1": {"inputs": {}}}
        wf = Workflow(data)
        errors = wf.validate_structure()
        assert any("class_type" in e for e in errors)

    def test_validate_structure_broken_link(self):
        data = {
            "1": {
                "class_type": "Test",
                "inputs": {"x": ["999", 0]},
            }
        }
        wf = Workflow(data)
        errors = wf.validate_structure()
        assert any("999" in e for e in errors)

    def test_summary(self):
        wf = Workflow(self.SAMPLE_PROMPT)
        s = wf.summary()
        assert s["node_count"] == 7
        assert "KSampler" in s["class_types"]
        assert len(s["errors"]) == 0


# ============================================================
# Client tests (mocked)
# ============================================================
from cli_anything.comfyui.core.client import (
    ComfyUIAPIError,
    ComfyUIClient,
    ComfyUIConnectionError,
)


class TestClient:
    """Tests for the ComfyUIClient (with mocked HTTP)."""

    def _mock_response(self, data, status=200):
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode("utf-8")
        resp.status = status
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_init_defaults(self):
        c = ComfyUIClient()
        assert c.host == "127.0.0.1"
        assert c.port == 8188
        assert c.base_url == "http://127.0.0.1:8188"

    def test_init_custom(self):
        c = ComfyUIClient(host="192.168.1.1", port=9999, use_ssl=True)
        assert c.base_url == "https://192.168.1.1:9999"

    @patch("urllib.request.urlopen")
    def test_get_system_stats(self, mock_urlopen):
        data = {"system": {"os": "nt", "ram_total": 16_000_000_000}}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_system_stats()
        assert result["system"]["os"] == "nt"

    @patch("urllib.request.urlopen")
    def test_get_model_types(self, mock_urlopen):
        data = ["checkpoints", "loras", "vae"]
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_model_types()
        assert "checkpoints" in result

    @patch("urllib.request.urlopen")
    def test_get_models(self, mock_urlopen):
        data = ["model1.safetensors", "model2.ckpt"]
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_models("checkpoints")
        assert len(result) == 2

    @patch("urllib.request.urlopen")
    def test_queue_prompt(self, mock_urlopen):
        data = {"prompt_id": "abc-123", "number": 0, "node_errors": {}}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.queue_prompt({"1": {"class_type": "Test", "inputs": {}}})
        assert result["prompt_id"] == "abc-123"

    @patch("urllib.request.urlopen")
    def test_get_queue(self, mock_urlopen):
        data = {"queue_running": [], "queue_pending": []}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_queue()
        assert "queue_running" in result

    @patch("urllib.request.urlopen")
    def test_get_history(self, mock_urlopen):
        data = {"abc-123": {"status": {"status_str": "success", "completed": True}}}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_history(prompt_id="abc-123")
        assert "abc-123" in result

    @patch("urllib.request.urlopen")
    def test_get_node_info(self, mock_urlopen):
        data = {"KSampler": {"display_name": "KSampler", "category": "sampling"}}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_node_info("KSampler")
        assert "KSampler" in result

    @patch("urllib.request.urlopen")
    def test_interrupt(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(None)
        # Handle None response
        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp
        c = ComfyUIClient()
        c.interrupt()  # should not raise

    @patch("urllib.request.urlopen")
    def test_is_server_running_true(self, mock_urlopen):
        data = {"system": {}}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        assert c.is_server_running() is True

    @patch("urllib.request.urlopen")
    def test_is_server_running_false(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("refused")
        c = ComfyUIClient()
        assert c.is_server_running() is False

    @patch("urllib.request.urlopen")
    def test_api_error(self, mock_urlopen):
        error = urllib.error.HTTPError(
            "http://test", 400,
            "Bad Request", {},
            MagicMock(read=MagicMock(return_value=b'{"error": {"message": "bad"}}'))
        )
        mock_urlopen.side_effect = error
        c = ComfyUIClient()
        with pytest.raises(ComfyUIAPIError) as exc_info:
            c.get_system_stats()
        assert exc_info.value.status_code == 400

    @patch("urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        c = ComfyUIClient()
        with pytest.raises(ComfyUIConnectionError):
            c.get_system_stats()


import urllib.error


# ============================================================
# Generate tests
# ============================================================
from cli_anything.comfyui.core.generate import (
    build_img2img_workflow,
    build_txt2img_workflow,
)


class TestGenerate:
    """Tests for workflow generation templates."""

    def test_txt2img_basic(self):
        wf = build_txt2img_workflow(
            checkpoint="model.safetensors",
            positive_prompt="a cat",
        )
        assert isinstance(wf, dict)
        # Should have 7 nodes
        assert len(wf) == 7
        # Check checkpoint
        assert wf["1"]["inputs"]["ckpt_name"] == "model.safetensors"
        # Check positive prompt
        assert wf["2"]["inputs"]["text"] == "a cat"

    def test_txt2img_custom_params(self):
        wf = build_txt2img_workflow(
            checkpoint="xl.safetensors",
            positive_prompt="test",
            negative_prompt="bad",
            width=1024,
            height=768,
            steps=30,
            cfg=5.0,
            sampler="dpmpp_2m",
            scheduler="karras",
            seed=123,
            batch_size=2,
        )
        ks = wf["5"]["inputs"]
        assert ks["steps"] == 30
        assert ks["cfg"] == 5.0
        assert ks["sampler_name"] == "dpmpp_2m"
        assert ks["scheduler"] == "karras"
        assert ks["seed"] == 123
        assert wf["4"]["inputs"]["width"] == 1024
        assert wf["4"]["inputs"]["height"] == 768
        assert wf["4"]["inputs"]["batch_size"] == 2
        assert wf["3"]["inputs"]["text"] == "bad"

    def test_txt2img_is_valid_workflow(self):
        wf_data = build_txt2img_workflow(
            checkpoint="test.safetensors",
            positive_prompt="hello",
        )
        wf = Workflow(wf_data)
        errors = wf.validate_structure()
        assert len(errors) == 0

    def test_img2img_basic(self):
        wf = build_img2img_workflow(
            checkpoint="model.safetensors",
            positive_prompt="enhance",
            image_filename="input.png",
        )
        assert isinstance(wf, dict)
        assert len(wf) == 8
        assert wf["4"]["class_type"] == "LoadImage"
        assert wf["4"]["inputs"]["image"] == "input.png"

    def test_img2img_denoise(self):
        wf = build_img2img_workflow(
            checkpoint="m.safetensors",
            positive_prompt="test",
            image_filename="img.png",
            denoise=0.5,
        )
        assert wf["6"]["inputs"]["denoise"] == 0.5

    def test_img2img_is_valid_workflow(self):
        wf_data = build_img2img_workflow(
            checkpoint="test.safetensors",
            positive_prompt="test",
            image_filename="img.png",
        )
        wf = Workflow(wf_data)
        errors = wf.validate_structure()
        assert len(errors) == 0


# ============================================================
# Generate LoRA/Upscale tests
# ============================================================
from cli_anything.comfyui.core.generate import (
    build_txt2img_lora_workflow,
    build_upscale_workflow,
)


class TestGenerateLora:
    """Tests for LoRA workflow generation."""

    def test_txt2img_lora_basic(self):
        wf = build_txt2img_lora_workflow(
            checkpoint="model.safetensors",
            positive_prompt="a cat",
            lora_name="style.safetensors",
        )
        assert isinstance(wf, dict)
        assert len(wf) == 8
        assert wf["2"]["class_type"] == "LoraLoader"
        assert wf["2"]["inputs"]["lora_name"] == "style.safetensors"

    def test_txt2img_lora_strength(self):
        wf = build_txt2img_lora_workflow(
            checkpoint="model.safetensors",
            positive_prompt="test",
            lora_name="lora.safetensors",
            lora_strength_model=0.8,
            lora_strength_clip=0.6,
        )
        assert wf["2"]["inputs"]["strength_model"] == 0.8
        assert wf["2"]["inputs"]["strength_clip"] == 0.6

    def test_txt2img_lora_uses_lora_output(self):
        """Verify sampler connects to LoRA model output, not raw checkpoint."""
        wf = build_txt2img_lora_workflow(
            checkpoint="model.safetensors",
            positive_prompt="test",
            lora_name="lora.safetensors",
        )
        # KSampler should connect to LoraLoader output
        assert wf["6"]["inputs"]["model"] == ["2", 0]
        # CLIP should connect to LoraLoader CLIP output
        assert wf["3"]["inputs"]["clip"] == ["2", 1]

    def test_txt2img_lora_is_valid(self):
        wf_data = build_txt2img_lora_workflow(
            checkpoint="model.safetensors",
            positive_prompt="test",
            lora_name="lora.safetensors",
        )
        wf = Workflow(wf_data)
        errors = wf.validate_structure()
        assert len(errors) == 0


class TestGenerateUpscale:
    """Tests for upscale workflow generation."""

    def test_upscale_basic(self):
        wf = build_upscale_workflow(image_filename="input.png")
        assert isinstance(wf, dict)
        assert len(wf) == 4
        assert wf["1"]["class_type"] == "LoadImage"
        assert wf["2"]["class_type"] == "UpscaleModelLoader"
        assert wf["3"]["class_type"] == "ImageUpscaleWithModel"

    def test_upscale_custom_model(self):
        wf = build_upscale_workflow(
            image_filename="test.png",
            upscale_model="4x_NMKD.pth",
        )
        assert wf["2"]["inputs"]["model_name"] == "4x_NMKD.pth"

    def test_upscale_is_valid(self):
        wf_data = build_upscale_workflow(image_filename="input.png")
        wf = Workflow(wf_data)
        errors = wf.validate_structure()
        assert len(errors) == 0


# ============================================================
# New Client method tests (mocked)
# ============================================================
class TestClientNewMethods:
    """Tests for newly added client methods."""

    def _mock_response(self, data, status=200):
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode("utf-8")
        resp.status = status
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    @patch("urllib.request.urlopen")
    def test_get_folder_paths(self, mock_urlopen):
        data = {"checkpoints": ["path1", "path2"], "loras": ["path3"]}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_folder_paths()
        assert "checkpoints" in result

    @patch("urllib.request.urlopen")
    def test_list_files(self, mock_urlopen):
        data = ["file1.png", "file2.png"]
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.list_files("output")
        assert len(result) == 2

    @patch("urllib.request.urlopen")
    def test_get_logs(self, mock_urlopen):
        data = "log line 1\nlog line 2\n"
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode("utf-8")
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp
        c = ComfyUIClient()
        result = c.get_logs()
        assert isinstance(result, str)

    @patch("urllib.request.urlopen")
    def test_get_settings(self, mock_urlopen):
        data = {"setting1": "value1"}
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_settings()
        assert "setting1" in result

    @patch("urllib.request.urlopen")
    def test_get_workflow_templates(self, mock_urlopen):
        data = [{"name": "basic"}]
        mock_urlopen.return_value = self._mock_response(data)
        c = ComfyUIClient()
        result = c.get_workflow_templates()
        assert isinstance(result, list)


# ============================================================
# New CLI command tests
# ============================================================
class TestCLINewCommands:
    """Tests for newly added CLI commands."""

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.get_folder_paths")
    def test_system_paths_json(self, mock_paths):
        mock_paths.return_value = {
            "checkpoints": ["/models/checkpoints"],
            "loras": ["/models/loras"],
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "system", "paths"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "checkpoints" in data

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.get_logs")
    def test_system_logs(self, mock_logs):
        mock_logs.return_value = "line 1\nline 2\n"
        runner = CliRunner()
        result = runner.invoke(cli, ["system", "logs"])
        assert result.exit_code == 0
        assert "line 1" in result.output

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.list_files")
    def test_images_list(self, mock_files):
        mock_files.return_value = ["img1.png", "img2.png", "img3.png"]
        runner = CliRunner()
        result = runner.invoke(cli, ["images", "list"])
        assert result.exit_code == 0
        assert "3 files" in result.output

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.list_files")
    def test_images_list_json(self, mock_files):
        mock_files.return_value = ["img1.png", "img2.png"]
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "images", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.get_node_info")
    def test_nodes_samplers(self, mock_info):
        mock_info.return_value = {
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "dpmpp_2m", "ddim"]],
                        "scheduler": [["normal", "karras", "exponential"]],
                        "seed": ["INT", {}],
                        "steps": ["INT", {}],
                        "cfg": ["FLOAT", {}],
                        "denoise": ["FLOAT", {}],
                        "model": ["MODEL"],
                        "positive": ["CONDITIONING"],
                        "negative": ["CONDITIONING"],
                        "latent_image": ["LATENT"],
                    }
                }
            }
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["nodes", "samplers"])
        assert result.exit_code == 0
        assert "euler" in result.output
        assert "karras" in result.output

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.get_node_info")
    def test_nodes_categories(self, mock_info):
        mock_info.return_value = {
            "KSampler": {"category": "sampling"},
            "SaveImage": {"category": "image"},
            "LoadImage": {"category": "image"},
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["nodes", "categories"])
        assert result.exit_code == 0
        assert "sampling" in result.output
        assert "image" in result.output

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.get_history")
    @patch("cli_anything.comfyui.core.client.ComfyUIClient.view_image")
    def test_history_save_images(self, mock_view, mock_hist):
        mock_hist.return_value = {
            "abc-123": {
                "status": {"status_str": "success"},
                "outputs": {
                    "7": {
                        "images": [
                            {"filename": "out.png", "type": "output", "subfolder": ""}
                        ]
                    }
                },
            }
        }
        mock_view.return_value = {"saved_to": "/tmp/out.png", "size": 1000}

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, [
                "history", "save-images", "abc-123", "--save-to", tmpdir,
            ])
            assert result.exit_code == 0
            assert "1 image" in result.output


# ============================================================
# Formatter tests
# ============================================================
from cli_anything.comfyui.utils.formatters import (
    OutputFormatter,
    format_json,
    format_kv,
    format_list,
    format_size,
    format_table,
)


class TestFormatters:
    """Tests for output formatting utilities."""

    def test_format_json(self):
        result = format_json({"a": 1})
        parsed = json.loads(result)
        assert parsed["a"] == 1

    def test_format_table(self):
        rows = [
            {"name": "a", "value": 1},
            {"name": "bb", "value": 22},
        ]
        result = format_table(rows)
        assert "name" in result
        assert "value" in result
        assert "a" in result
        assert "bb" in result

    def test_format_table_empty(self):
        result = format_table([])
        assert "no data" in result.lower()

    def test_format_list(self):
        result = format_list(["a", "b", "c"])
        assert "a" in result
        assert "b" in result

    def test_format_list_empty(self):
        result = format_list([])
        assert "none" in result.lower()

    def test_format_kv(self):
        result = format_kv({"host": "localhost", "port": 8188})
        assert "host" in result
        assert "8188" in result

    def test_format_size(self):
        assert "B" in format_size(100)
        assert "KB" in format_size(1024)
        assert "MB" in format_size(1024 * 1024)
        assert "GB" in format_size(1024 ** 3)

    def test_output_formatter_json_mode(self):
        fmt = OutputFormatter(json_mode=True)
        output = fmt.output({"test": 1}, human_text="human")
        parsed = json.loads(output)
        assert parsed["test"] == 1

    def test_output_formatter_human_mode(self):
        fmt = OutputFormatter(json_mode=False)
        output = fmt.output({"test": 1}, human_text="human readable")
        assert output == "human readable"


# ============================================================
# Config tests
# ============================================================
from cli_anything.comfyui.utils.config import (
    DEFAULT_CONFIG,
    get_server_args,
    load_config,
)


class TestConfig:
    """Tests for configuration management."""

    def test_default_config(self):
        assert "host" in DEFAULT_CONFIG
        assert "port" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["port"] == 8188

    def test_load_config_defaults(self):
        # Should fall back to defaults when no config file
        with patch(
            "cli_anything.comfyui.utils.config.get_config_path",
            return_value=Path("/nonexistent/.comfyui-cli.json"),
        ):
            config = load_config()
            assert config["host"] == "127.0.0.1"
            assert config["port"] == 8188

    def test_get_server_args(self):
        config = {"host": "10.0.0.1", "port": 9999, "ssl": True}
        args = get_server_args(config)
        assert args["host"] == "10.0.0.1"
        assert args["port"] == 9999
        assert args["use_ssl"] is True


# ============================================================
# CLI tests (Click testing)
# ============================================================
from click.testing import CliRunner

from cli_anything.comfyui.comfyui_cli import cli


class TestCLI:
    """Tests for the Click CLI commands."""

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "workflow" in result.output
        assert "queue" in result.output
        assert "models" in result.output

    def test_workflow_validate(self):
        runner = CliRunner()
        prompt = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "test.safetensors"},
            },
            "2": {
                "class_type": "SaveImage",
                "inputs": {"images": ["1", 0], "filename_prefix": "test"},
            },
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(prompt, f)
            path = f.name

        try:
            result = runner.invoke(cli, ["workflow", "validate", path])
            assert result.exit_code == 0
            assert "VALID" in result.output
        finally:
            os.unlink(path)

    def test_workflow_info(self):
        runner = CliRunner()
        prompt = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "test.safetensors"},
            },
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(prompt, f)
            path = f.name

        try:
            result = runner.invoke(cli, ["workflow", "info", path])
            assert result.exit_code == 0
            assert "CheckpointLoaderSimple" in result.output
        finally:
            os.unlink(path)

    def test_workflow_validate_json_mode(self):
        runner = CliRunner()
        prompt = {
            "1": {
                "class_type": "Test",
                "inputs": {},
            },
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(prompt, f)
            path = f.name

        try:
            result = runner.invoke(cli, ["--json", "workflow", "validate", path])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "valid" in data
        finally:
            os.unlink(path)

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.get_system_stats")
    def test_system_stats_json(self, mock_stats):
        mock_stats.return_value = {
            "system": {"os": "nt", "ram_total": 16_000_000_000, "ram_free": 8_000_000_000},
            "devices": [],
        }
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "system", "stats"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "system" in data

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.is_server_running")
    def test_system_ping_alive(self, mock_ping):
        mock_ping.return_value = True
        runner = CliRunner()
        result = runner.invoke(cli, ["system", "ping"])
        assert result.exit_code == 0
        assert "ALIVE" in result.output

    @patch("cli_anything.comfyui.core.client.ComfyUIClient.is_server_running")
    def test_system_ping_dead(self, mock_ping):
        mock_ping.return_value = False
        runner = CliRunner()
        result = runner.invoke(cli, ["system", "ping"])
        assert result.exit_code == 1
        assert "UNREACHABLE" in result.output

    def test_config_show(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "host" in result.output
        assert "port" in result.output


# ============================================================
# Diverse generation tests
# ============================================================
from cli_anything.comfyui.core.diverse import (
    apply_diversity_to_workflow,
    generate_lora_weight_sweep,
    generate_random_character_prompt,
    get_style_info,
    get_style_list,
)


class TestDiverse:
    """Tests for diverse generation utilities."""

    def test_get_style_list(self):
        styles = get_style_list()
        assert isinstance(styles, list)
        assert len(styles) > 0
        assert "cyberpunk" in styles
        assert "fantasy" in styles

    def test_get_style_info(self):
        info = get_style_info("cyberpunk")
        assert info is not None
        assert "keywords" in info
        assert "negative_add" in info
        assert "lora_weight_range" in info
        assert isinstance(info["lora_weight_range"], tuple)
        assert len(info["lora_weight_range"]) == 2

    def test_generate_random_character_prompt(self):
        result = generate_random_character_prompt()
        assert "positive" in result
        assert "negative" in result
        assert "lora_weight" in result
        assert "style_name" in result

    def test_generate_random_character_prompt_with_style(self):
        result = generate_random_character_prompt(style="fantasy")
        assert result["style_name"] == "fantasy"
        assert "fantasy" in result["positive"]

    def test_generate_lora_weight_sweep(self):
        weights = generate_lora_weight_sweep(0.3, 1.0, 8)
        assert len(weights) == 8
        assert weights[0] == 0.3
        assert weights[-1] == 1.0
        assert all(0.3 <= w <= 1.0 for w in weights)

    def test_generate_lora_weight_sweep_single(self):
        weights = generate_lora_weight_sweep(0.5, 0.7, 1)
        assert len(weights) == 1
        assert weights[0] == 0.6  # midpoint

    def test_apply_diversity_to_workflow(self):
        workflow = {
            "1": {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": "test.safetensors",
                    "strength_model": 1.0,
                    "strength_clip": 1.0,
                },
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "old prompt"},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "old negative"},
            },
            "4": {
                "class_type": "KSampler",
                "inputs": {"seed": 42, "steps": 20, "cfg": 7.0},
            },
        }

        config = {
            "lora_weight": 0.65,
            "positive_prompt": "new prompt",
            "negative_prompt": "new negative",
            "seed": 12345,
            "cfg": 8.0,
        }

        result = apply_diversity_to_workflow(workflow, config)

        # Check LoRA weight changed
        assert result["1"]["inputs"]["strength_model"] == 0.65
        assert result["1"]["inputs"]["strength_clip"] == 0.65

        # Check prompts changed
        assert result["2"]["inputs"]["text"] == "new prompt"
        assert result["3"]["inputs"]["text"] == "new negative"

        # Check sampler params changed
        assert result["4"]["inputs"]["seed"] == 12345
        assert result["4"]["inputs"]["cfg"] == 8.0

        # Original workflow should be unchanged
        assert workflow["1"]["inputs"]["strength_model"] == 1.0


# ============================================================
# Subprocess tests
# ============================================================
import shutil
import subprocess


class TestCLISubprocess:
    """Tests that verify the installed CLI works via subprocess."""

    @staticmethod
    def _resolve_cli(name: str) -> str:
        """Resolve CLI executable path.

        In test mode, returns the executable name (assumes it's in PATH).
        Set CLI_ANYTHING_FORCE_INSTALLED=1 to skip existence check.
        """
        if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED"):
            return name
        path = shutil.which(name)
        if path:
            return path
        pytest.skip(f"{name} not found in PATH. Install with: pip install -e .")

    def test_cli_version(self):
        exe = self._resolve_cli("comfyui-cli")
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_cli_help(self):
        exe = self._resolve_cli("comfyui-cli")
        result = subprocess.run(
            [exe, "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "workflow" in result.stdout

    def test_cli_workflow_validate(self):
        exe = self._resolve_cli("comfyui-cli")
        prompt = {
            "1": {"class_type": "Test", "inputs": {}},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(prompt, f)
            path = f.name

        try:
            result = subprocess.run(
                [exe, "workflow", "validate", path],
                capture_output=True, text=True, timeout=10,
            )
            assert result.returncode == 0
            assert "VALID" in result.stdout
        finally:
            os.unlink(path)

    def test_cli_json_mode(self):
        exe = self._resolve_cli("comfyui-cli")
        prompt = {
            "1": {"class_type": "Test", "inputs": {}},
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(prompt, f)
            path = f.name

        try:
            result = subprocess.run(
                [exe, "--json", "workflow", "validate", path],
                capture_output=True, text=True, timeout=10,
            )
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert "valid" in data
        finally:
            os.unlink(path)
