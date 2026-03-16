"""HTTP and WebSocket client for communicating with a ComfyUI server."""

import json
import uuid
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any


class ComfyUIClient:
    """Client for the ComfyUI REST API and WebSocket interface."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8188, use_ssl: bool = False):
        self.host = host
        self.port = port
        self.scheme = "https" if use_ssl else "http"
        self.ws_scheme = "wss" if use_ssl else "ws"
        self.base_url = f"{self.scheme}://{self.host}:{self.port}"
        self.client_id = str(uuid.uuid4())

    def _request(self, method: str, path: str, data: dict | None = None,
                 timeout: float = 30.0) -> Any:
        """Make an HTTP request to the ComfyUI server."""
        url = f"{self.base_url}{path}"
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                if content:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        return content
                return None
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            try:
                error_data = json.loads(error_body)
            except json.JSONDecodeError:
                error_data = {"raw": error_body}
            raise ComfyUIAPIError(e.code, error_data) from e
        except urllib.error.URLError as e:
            raise ComfyUIConnectionError(
                f"Cannot connect to ComfyUI at {self.base_url}: {e.reason}"
            ) from e

    def _get(self, path: str, params: dict | None = None, timeout: float = 30.0) -> Any:
        if params:
            query = urllib.parse.urlencode(params)
            path = f"{path}?{query}"
        return self._request("GET", path, timeout=timeout)

    def _post(self, path: str, data: dict | None = None, timeout: float = 30.0) -> Any:
        return self._request("POST", path, data=data, timeout=timeout)

    def _upload(self, path: str, filepath: str, field: str = "image",
                extra_fields: dict | None = None, timeout: float = 60.0) -> Any:
        """Upload a file using multipart/form-data."""
        boundary = f"----ComfyCLI{uuid.uuid4().hex}"
        file_path = Path(filepath)
        filename = file_path.name

        body_parts = []

        if extra_fields:
            for key, value in extra_fields.items():
                body_parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                    f"{value}\r\n"
                )

        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        )

        file_data = file_path.read_bytes()
        end_boundary = f"\r\n--{boundary}--\r\n"

        body = b""
        for part in body_parts:
            body += part.encode("utf-8")
        body += file_data
        body += end_boundary.encode("utf-8")

        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise ComfyUIAPIError(e.code, {"raw": error_body}) from e
        except urllib.error.URLError as e:
            raise ComfyUIConnectionError(
                f"Cannot connect to ComfyUI at {self.base_url}: {e.reason}"
            ) from e

    # --- Prompt / Workflow ---

    def queue_prompt(self, prompt: dict, extra_data: dict | None = None,
                     front: bool = False) -> dict:
        """Submit a workflow prompt for execution."""
        payload: dict[str, Any] = {
            "prompt": prompt,
            "client_id": self.client_id,
        }
        if front:
            payload["front"] = True
        if extra_data:
            payload["extra_data"] = extra_data
        return self._post("/prompt", payload)

    def get_queue_status(self) -> dict:
        """Get current queue remaining count."""
        return self._get("/prompt")

    # --- Queue ---

    def get_queue(self) -> dict:
        """Get running and pending queue items."""
        return self._get("/queue")

    def clear_queue(self) -> Any:
        """Clear the entire pending queue."""
        return self._post("/queue", {"clear": True})

    def delete_queue_items(self, prompt_ids: list[str]) -> Any:
        """Delete specific items from the queue."""
        return self._post("/queue", {"delete": prompt_ids})

    def interrupt(self) -> Any:
        """Interrupt the currently executing workflow."""
        return self._post("/interrupt")

    # --- History ---

    def get_history(self, prompt_id: str | None = None,
                    max_items: int | None = None) -> dict:
        """Get execution history."""
        if prompt_id:
            return self._get(f"/history/{prompt_id}")
        params = {}
        if max_items is not None:
            params["max_items"] = str(max_items)
        return self._get("/history", params=params if params else None)

    def clear_history(self) -> Any:
        """Clear all history."""
        return self._post("/history", {"clear": True})

    def delete_history_items(self, prompt_ids: list[str]) -> Any:
        """Delete specific history items."""
        return self._post("/history", {"delete": prompt_ids})

    # --- Models ---

    def get_model_types(self) -> list[str]:
        """List all available model folder types."""
        return self._get("/models")

    def get_models(self, folder: str) -> list[str]:
        """List models in a specific folder."""
        return self._get(f"/models/{folder}")

    def get_embeddings(self) -> list[str]:
        """List available embeddings."""
        return self._get("/embeddings")

    def get_model_metadata(self, folder: str, filename: str) -> dict:
        """Get metadata for a safetensors model file."""
        return self._get(f"/view_metadata/{folder}", params={"filename": filename})

    # --- Nodes ---

    def get_node_info(self, node_class: str | None = None) -> dict:
        """Get node definitions. If node_class given, return just that node."""
        if node_class:
            return self._get(f"/object_info/{node_class}")
        return self._get("/object_info")

    # --- Images ---

    def upload_image(self, filepath: str, image_type: str = "input",
                     subfolder: str = "", overwrite: bool = False) -> dict:
        """Upload an image to the server."""
        extra = {"type": image_type}
        if subfolder:
            extra["subfolder"] = subfolder
        if overwrite:
            extra["overwrite"] = "true"
        return self._upload("/upload/image", filepath, extra_fields=extra)

    def view_image(self, filename: str, image_type: str = "output",
                   subfolder: str = "", save_to: str | None = None) -> bytes | dict:
        """Download/view an image from the server."""
        params: dict[str, str] = {"filename": filename, "type": image_type}
        if subfolder:
            params["subfolder"] = subfolder
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/view?{query}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                if save_to:
                    Path(save_to).write_bytes(data)
                    return {"saved_to": save_to, "size": len(data)}
                return data
        except urllib.error.HTTPError as e:
            raise ComfyUIAPIError(e.code, {"raw": e.read().decode()}) from e
        except urllib.error.URLError as e:
            raise ComfyUIConnectionError(str(e.reason)) from e

    # --- System ---

    def get_system_stats(self) -> dict:
        """Get system statistics (GPU, CPU, memory)."""
        return self._get("/system_stats")

    def free_memory(self, unload_models: bool = True, free_memory: bool = True) -> Any:
        """Free GPU memory."""
        return self._post("/free", {
            "unload_models": unload_models,
            "free_memory": free_memory,
        })

    def get_extensions(self) -> list[str]:
        """List loaded frontend extensions."""
        return self._get("/extensions")

    # --- Internal / Diagnostics ---

    def get_folder_paths(self) -> dict:
        """Get all configured folder paths."""
        return self._get("/internal/folder_paths")

    def list_files(self, directory_type: str) -> list:
        """List files in output/input/temp directories."""
        return self._get(f"/internal/files/{directory_type}")

    def get_logs(self, raw: bool = False) -> Any:
        """Get server logs."""
        if raw:
            return self._get("/internal/logs/raw")
        return self._get("/internal/logs")

    # --- User & Settings ---

    def get_users(self) -> dict:
        """List users or get migration status."""
        return self._get("/users")

    def create_user(self, username: str) -> Any:
        """Create a new user."""
        return self._post("/users", {"username": username})

    def get_settings(self) -> dict:
        """Get all user settings."""
        return self._get("/settings")

    def set_settings(self, settings: dict) -> Any:
        """Update multiple settings at once."""
        return self._post("/settings", settings)

    def get_setting(self, setting_id: str) -> Any:
        """Get a specific setting."""
        return self._get(f"/settings/{setting_id}")

    def set_setting(self, setting_id: str, value: Any) -> Any:
        """Set a specific setting."""
        return self._post(f"/settings/{setting_id}", {"value": value})

    # --- Userdata ---

    def list_userdata(self, recurse: bool = False) -> list:
        """List user data files."""
        params = {}
        if recurse:
            params["recurse"] = "true"
        return self._get("/userdata", params=params if params else None)

    def get_userdata(self, filename: str) -> Any:
        """Download a user data file."""
        return self._get(f"/userdata/{filename}")

    # --- Workflow Templates ---

    def get_workflow_templates(self) -> Any:
        """Get available workflow templates."""
        return self._get("/workflow_templates")

    # --- Execution helpers ---

    def execute_and_wait(self, prompt: dict, poll_interval: float = 1.0,
                         timeout: float = 600.0,
                         progress_callback=None) -> dict:
        """Submit a prompt and poll until completion. Returns the history entry."""
        result = self.queue_prompt(prompt)
        prompt_id = result["prompt_id"]
        start = time.time()

        while True:
            elapsed = time.time() - start
            if elapsed > timeout:
                raise ComfyUITimeoutError(
                    f"Execution timed out after {timeout}s for prompt {prompt_id}"
                )

            history = self.get_history(prompt_id)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("completed", False) or status.get("status_str") == "error":
                    return entry

            if progress_callback:
                queue = self.get_queue()
                progress_callback(queue, elapsed)

            time.sleep(poll_interval)

    def is_server_running(self) -> bool:
        """Check if the ComfyUI server is reachable."""
        try:
            self.get_system_stats()
            return True
        except (ComfyUIConnectionError, ComfyUIAPIError):
            return False


class ComfyUIAPIError(Exception):
    """HTTP error from ComfyUI API."""
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self.data = data
        message = data.get("error", {}).get("message", "") if isinstance(data, dict) else str(data)
        super().__init__(f"HTTP {status_code}: {message}")


class ComfyUIConnectionError(Exception):
    """Cannot connect to ComfyUI server."""


class ComfyUITimeoutError(Exception):
    """Execution timed out."""
