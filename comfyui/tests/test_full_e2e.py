"""End-to-end tests for comfyui-cli.

These tests require a running ComfyUI server.
Set COMFYUI_TEST_SERVER=host:port to enable, or skip automatically.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from click.testing import CliRunner

from comfyui.core.client import ComfyUIClient
from comfyui.core.generate import build_txt2img_workflow
from comfyui.core.workflow import Workflow
from comfyui.comfyui_cli import cli


def _get_server():
    """Get test server host:port from environment."""
    server = os.environ.get("COMFYUI_TEST_SERVER", "")
    if not server:
        pytest.skip("COMFYUI_TEST_SERVER not set")
    parts = server.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 8188
    return host, port


def _get_client():
    host, port = _get_server()
    return ComfyUIClient(host=host, port=port)


@pytest.fixture
def client():
    return _get_client()


@pytest.fixture
def runner():
    return CliRunner()


class TestServerConnectivity:
    """E2E: Test server connectivity."""

    def test_ping(self, client):
        assert client.is_server_running()

    def test_system_stats(self, client):
        stats = client.get_system_stats()
        assert "system" in stats
        assert "devices" in stats


class TestModelDiscovery:
    """E2E: Test model listing."""

    def test_model_types(self, client):
        types = client.get_model_types()
        assert isinstance(types, list)
        assert len(types) > 0

    def test_list_checkpoints(self, client):
        models = client.get_models("checkpoints")
        assert isinstance(models, list)

    def test_list_loras(self, client):
        models = client.get_models("loras")
        assert isinstance(models, list)

    def test_embeddings(self, client):
        emb = client.get_embeddings()
        assert isinstance(emb, list)


class TestNodeInfo:
    """E2E: Test node information retrieval."""

    def test_all_nodes(self, client):
        info = client.get_node_info()
        assert isinstance(info, dict)
        assert "KSampler" in info
        assert "CheckpointLoaderSimple" in info
        assert "SaveImage" in info

    def test_specific_node(self, client):
        info = client.get_node_info("KSampler")
        assert "KSampler" in info
        node = info["KSampler"]
        assert "input" in node
        assert "output" in node

    def test_node_has_required_fields(self, client):
        info = client.get_node_info("KSampler")
        node = info["KSampler"]
        required = node["input"]["required"]
        assert "seed" in required
        assert "steps" in required
        assert "cfg" in required
        assert "sampler_name" in required


class TestQueueOperations:
    """E2E: Test queue operations."""

    def test_get_queue(self, client):
        q = client.get_queue()
        assert "queue_running" in q
        assert "queue_pending" in q

    def test_queue_status(self, client):
        status = client.get_queue_status()
        assert "exec_info" in status


class TestHistory:
    """E2E: Test history operations."""

    def test_get_history(self, client):
        hist = client.get_history()
        assert isinstance(hist, dict)


class TestImageUpload:
    """E2E: Test image upload."""

    def test_upload_image(self, client):
        # Create a minimal valid PNG
        import struct
        import zlib

        width, height = 2, 2
        raw = b""
        for _ in range(height):
            raw += b"\x00" + b"\xff\x00\x00" * width

        def chunk(chunk_type, data):
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(raw))
        png += chunk(b"IEND", b"")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(png)
            path = f.name

        try:
            result = client.upload_image(path)
            assert "name" in result
        finally:
            os.unlink(path)


class TestWorkflowExecution:
    """E2E: Test actual workflow execution.

    These tests only run if a checkpoint is available.
    Set COMFYUI_TEST_CHECKPOINT to the checkpoint name.
    """

    @pytest.fixture
    def checkpoint(self):
        ckpt = os.environ.get("COMFYUI_TEST_CHECKPOINT", "")
        if not ckpt:
            pytest.skip("COMFYUI_TEST_CHECKPOINT not set")
        return ckpt

    def test_txt2img_execution(self, client, checkpoint):
        """Run a full txt2img workflow and verify outputs."""
        prompt = build_txt2img_workflow(
            checkpoint=checkpoint,
            positive_prompt="a solid red square",
            negative_prompt="",
            width=64,
            height=64,
            steps=3,
            cfg=7.0,
            seed=42,
        )

        result = client.execute_and_wait(prompt, timeout=120)
        assert result["status"]["status_str"] == "success"

        # Check outputs exist
        outputs = result.get("outputs", {})
        image_count = sum(len(o.get("images", [])) for o in outputs.values())
        assert image_count > 0

    def test_txt2img_download_result(self, client, checkpoint):
        """Run txt2img and download the output image."""
        prompt = build_txt2img_workflow(
            checkpoint=checkpoint,
            positive_prompt="a blue circle",
            width=64,
            height=64,
            steps=2,
            cfg=7.0,
            seed=100,
        )

        result = client.execute_and_wait(prompt, timeout=120)
        outputs = result.get("outputs", {})

        with tempfile.TemporaryDirectory() as tmpdir:
            for _nid, out in outputs.items():
                for img in out.get("images", []):
                    dest = os.path.join(tmpdir, img["filename"])
                    client.view_image(
                        img["filename"],
                        image_type=img.get("type", "output"),
                        save_to=dest,
                    )
                    assert os.path.exists(dest)
                    assert os.path.getsize(dest) > 0


class TestCLIE2E:
    """E2E: Test CLI commands against real server."""

    def test_system_ping(self, runner):
        host, port = _get_server()
        result = runner.invoke(cli, [
            "--host", host, "--port", str(port),
            "system", "ping",
        ])
        assert result.exit_code == 0
        assert "ALIVE" in result.output

    def test_system_stats(self, runner):
        host, port = _get_server()
        result = runner.invoke(cli, [
            "--host", host, "--port", str(port),
            "--json", "system", "stats",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "system" in data

    def test_models_types(self, runner):
        host, port = _get_server()
        result = runner.invoke(cli, [
            "--host", host, "--port", str(port),
            "--json", "models", "types",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_nodes_list(self, runner):
        host, port = _get_server()
        result = runner.invoke(cli, [
            "--host", host, "--port", str(port),
            "--json", "nodes", "list",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_queue_status(self, runner):
        host, port = _get_server()
        result = runner.invoke(cli, [
            "--host", host, "--port", str(port),
            "queue", "status",
        ])
        assert result.exit_code == 0
