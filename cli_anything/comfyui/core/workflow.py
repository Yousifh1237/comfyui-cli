"""Workflow loading, validation, and manipulation."""

import json
from pathlib import Path
from typing import Any


class Workflow:
    """Represents a ComfyUI workflow (prompt dictionary)."""

    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def from_file(cls, filepath: str) -> "Workflow":
        """Load a workflow from a JSON file.

        Supports both API format (flat dict of nodes) and UI format
        (with 'workflow' and/or 'prompt' keys from exported files).
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {filepath}")

        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "Workflow":
        """Parse a workflow from a dictionary, handling multiple formats."""
        if "prompt" in raw and isinstance(raw["prompt"], dict):
            # Exported format with wrapper
            prompt = raw["prompt"]
        elif "output" in raw and isinstance(raw["output"], dict):
            # Another export format
            prompt = raw["output"]
        elif all(isinstance(v, dict) and "class_type" in v for v in raw.values()):
            # API format: flat dict of nodes
            prompt = raw
        else:
            # Try to use as-is
            prompt = raw

        return cls(prompt)

    @classmethod
    def from_json(cls, json_str: str) -> "Workflow":
        """Parse a workflow from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> dict:
        return self.data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.data, indent=indent, ensure_ascii=False)

    def save(self, filepath: str) -> None:
        Path(filepath).write_text(self.to_json(), encoding="utf-8")

    @property
    def node_ids(self) -> list[str]:
        return list(self.data.keys())

    @property
    def node_count(self) -> int:
        return len(self.data)

    def get_node(self, node_id: str) -> dict | None:
        return self.data.get(node_id)

    def get_nodes_by_type(self, class_type: str) -> dict[str, dict]:
        """Find all nodes of a given class type."""
        return {
            nid: node for nid, node in self.data.items()
            if node.get("class_type") == class_type
        }

    def get_output_nodes(self) -> dict[str, dict]:
        """Find nodes that are likely outputs (SaveImage, PreviewImage, etc.)."""
        output_types = {
            "SaveImage", "PreviewImage", "SaveImageWebsocket",
            "SaveAnimatedWEBP", "SaveAnimatedPNG", "SaveLatent",
        }
        return {
            nid: node for nid, node in self.data.items()
            if node.get("class_type") in output_types
        }

    def get_class_types(self) -> set[str]:
        """Get all unique node class types used."""
        return {node.get("class_type", "") for node in self.data.values()}

    def set_input(self, node_id: str, key: str, value: Any) -> None:
        """Set an input value on a specific node."""
        if node_id not in self.data:
            raise KeyError(f"Node '{node_id}' not found in workflow")
        self.data[node_id].setdefault("inputs", {})[key] = value

    def get_input(self, node_id: str, key: str) -> Any:
        """Get an input value from a specific node."""
        node = self.data.get(node_id)
        if node is None:
            raise KeyError(f"Node '{node_id}' not found in workflow")
        return node.get("inputs", {}).get(key)

    def set_seed(self, seed: int) -> list[str]:
        """Set the seed on all KSampler nodes. Returns list of modified node IDs."""
        modified = []
        for nid, node in self.data.items():
            ct = node.get("class_type", "")
            if "sampler" in ct.lower() or ct in ("KSampler", "KSamplerAdvanced"):
                if "seed" in node.get("inputs", {}):
                    node["inputs"]["seed"] = seed
                    modified.append(nid)
        return modified

    def set_prompt_text(self, text: str, node_id: str | None = None) -> list[str]:
        """Set positive prompt text. If node_id not given, find CLIPTextEncode nodes."""
        modified = []
        if node_id:
            self.set_input(node_id, "text", text)
            return [node_id]
        # Find CLIPTextEncode nodes - typically the first one is positive
        for nid, node in self.data.items():
            if node.get("class_type") == "CLIPTextEncode":
                if "text" in node.get("inputs", {}):
                    node["inputs"]["text"] = text
                    modified.append(nid)
                    break  # Only set first one
        return modified

    def set_negative_text(self, text: str, node_id: str | None = None) -> list[str]:
        """Set negative prompt text on the second CLIPTextEncode node."""
        modified = []
        if node_id:
            self.set_input(node_id, "text", text)
            return [node_id]
        clip_nodes = []
        for nid, node in self.data.items():
            if node.get("class_type") == "CLIPTextEncode":
                if "text" in node.get("inputs", {}):
                    clip_nodes.append(nid)
        if len(clip_nodes) >= 2:
            self.set_input(clip_nodes[1], "text", text)
            modified.append(clip_nodes[1])
        return modified

    def set_checkpoint(self, ckpt_name: str) -> list[str]:
        """Set the checkpoint model on all CheckpointLoaderSimple nodes."""
        modified = []
        for nid, node in self.data.items():
            if node.get("class_type") in ("CheckpointLoaderSimple", "CheckpointLoader"):
                node["inputs"]["ckpt_name"] = ckpt_name
                modified.append(nid)
        return modified

    def set_image_size(self, width: int, height: int) -> list[str]:
        """Set image size on EmptyLatentImage nodes."""
        modified = []
        for nid, node in self.data.items():
            if node.get("class_type") == "EmptyLatentImage":
                node["inputs"]["width"] = width
                node["inputs"]["height"] = height
                modified.append(nid)
        return modified

    def validate_structure(self) -> list[str]:
        """Basic structural validation. Returns list of error messages."""
        errors = []
        if not self.data:
            errors.append("Workflow is empty")
            return errors

        for nid, node in self.data.items():
            if not isinstance(node, dict):
                errors.append(f"Node '{nid}' is not a dictionary")
                continue
            if "class_type" not in node:
                errors.append(f"Node '{nid}' missing 'class_type'")
            inputs = node.get("inputs", {})
            for key, val in inputs.items():
                if isinstance(val, list) and len(val) == 2:
                    src_id = str(val[0])
                    if src_id not in self.data:
                        errors.append(
                            f"Node '{nid}' input '{key}' links to "
                            f"non-existent node '{src_id}'"
                        )
        return errors

    def summary(self) -> dict:
        """Get a summary of the workflow."""
        class_counts: dict[str, int] = {}
        for node in self.data.values():
            ct = node.get("class_type", "unknown")
            class_counts[ct] = class_counts.get(ct, 0) + 1

        return {
            "node_count": self.node_count,
            "class_types": sorted(self.get_class_types()),
            "class_counts": class_counts,
            "output_nodes": list(self.get_output_nodes().keys()),
            "errors": self.validate_structure(),
        }
