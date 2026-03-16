"""High-level generation templates for common workflows."""

from typing import Any


def build_txt2img_workflow(
    checkpoint: str,
    positive_prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    seed: int = 0,
    batch_size: int = 1,
    denoise: float = 1.0,
    filename_prefix: str = "ComfyUI",
) -> dict[str, Any]:
    """Build a text-to-image workflow prompt."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": batch_size,
            },
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
            },
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": filename_prefix,
                "images": ["6", 0],
            },
        },
    }


def build_txt2img_lora_workflow(
    checkpoint: str,
    positive_prompt: str,
    lora_name: str,
    lora_strength_model: float = 1.0,
    lora_strength_clip: float = 1.0,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    seed: int = 0,
    batch_size: int = 1,
    denoise: float = 1.0,
    filename_prefix: str = "ComfyUI",
) -> dict[str, Any]:
    """Build a text-to-image workflow with LoRA."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_name,
                "strength_model": lora_strength_model,
                "strength_clip": lora_strength_clip,
                "model": ["1", 0],
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["2", 1],
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["2", 1],
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": batch_size,
            },
        },
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
                "model": ["2", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
            },
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["6", 0],
                "vae": ["1", 2],
            },
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": filename_prefix,
                "images": ["7", 0],
            },
        },
    }


def build_upscale_workflow(
    image_filename: str,
    upscale_model: str = "RealESRGAN_x4plus.pth",
    filename_prefix: str = "ComfyUI_upscale",
) -> dict[str, Any]:
    """Build an upscale workflow using an upscale model."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": image_filename},
        },
        "2": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": upscale_model},
        },
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["2", 0],
                "image": ["1", 0],
            },
        },
        "4": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": filename_prefix,
                "images": ["3", 0],
            },
        },
    }


def build_img2img_workflow(
    checkpoint: str,
    positive_prompt: str,
    image_filename: str,
    negative_prompt: str = "",
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    seed: int = 0,
    denoise: float = 0.7,
    filename_prefix: str = "ComfyUI",
) -> dict[str, Any]:
    """Build an image-to-image workflow prompt."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": image_filename},
        },
        "5": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["4", 0],
                "vae": ["1", 2],
            },
        },
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["5", 0],
            },
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["6", 0],
                "vae": ["1", 2],
            },
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": filename_prefix,
                "images": ["7", 0],
            },
        },
    }
