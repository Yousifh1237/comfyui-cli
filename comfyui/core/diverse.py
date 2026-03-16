"""Diverse generation utilities for avoiding same-face syndrome and style repetition.

This module provides tools for generating varied characters and styles by:
- Dynamically adjusting LoRA weights
- Randomizing prompts with templates
- Applying different artistic styles
- Testing multiple parameter combinations
"""

import random
from typing import Any

# Style presets based on community best practices
STYLE_PRESETS = {
    "cyberpunk": {
        "keywords": "cyberpunk style, neon lights, futuristic cityscape, tech wear, glowing accessories, night scene, rain, reflections, cinematic lighting",
        "negative_add": "medieval, fantasy, nature, daylight",
        "lora_weight_range": (0.5, 0.7),
    },
    "fantasy": {
        "keywords": "fantasy style, magical atmosphere, enchanted forest, mystical, ethereal lighting, glowing runes, particles, soft focus",
        "negative_add": "modern, urban, technology, cyberpunk",
        "lora_weight_range": (0.6, 0.75),
    },
    "realistic": {
        "keywords": "photorealistic, natural lighting, detailed textures, shallow depth of field, professional photography",
        "negative_add": "anime, cartoon, illustration, painting",
        "lora_weight_range": (0.7, 0.85),
    },
    "anime": {
        "keywords": "anime style, vibrant colors, cel shading, expressive eyes, dynamic pose",
        "negative_add": "realistic, photographic, 3d render",
        "lora_weight_range": (0.65, 0.8),
    },
    "painterly": {
        "keywords": "oil painting style, brush strokes, artistic, impressionist, soft edges, rich colors",
        "negative_add": "photographic, sharp, digital",
        "lora_weight_range": (0.6, 0.75),
    },
    "minimalist": {
        "keywords": "minimalist style, clean lines, simple composition, limited color palette, negative space",
        "negative_add": "detailed, complex, busy, ornate",
        "lora_weight_range": (0.5, 0.65),
    },
}

# Character variation templates
CHARACTER_VARIATIONS = {
    "hair_style": [
        "long flowing hair",
        "short bob cut",
        "pixie cut",
        "wavy shoulder-length hair",
        "straight hair with bangs",
        "messy bun",
        "braided hair",
        "ponytail",
    ],
    "hair_color": [
        "black hair",
        "brown hair",
        "blonde hair",
        "red hair",
        "silver hair",
        "purple hair",
        "blue hair",
        "pink hair",
        "white hair",
    ],
    "eye_color": [
        "blue eyes",
        "green eyes",
        "brown eyes",
        "amber eyes",
        "gray eyes",
        "violet eyes",
        "heterochromia eyes",
    ],
    "facial_features": [
        "sharp jawline",
        "soft features",
        "freckles",
        "beauty mark",
        "distinctive eyebrows",
        "high cheekbones",
    ],
    "expression": [
        "gentle smile",
        "confident smirk",
        "serious expression",
        "playful grin",
        "mysterious look",
        "determined gaze",
        "shy smile",
    ],
    "clothing": [
        "casual modern outfit",
        "elegant dress",
        "business attire",
        "streetwear",
        "traditional clothing",
        "fantasy armor",
        "sci-fi suit",
    ],
}


def generate_random_character_prompt(base_prompt: str = "", style: str | None = None) -> dict[str, Any]:
    """Generate a style-varied prompt while preserving character identity.

    Args:
        base_prompt: Base prompt with character identity (e.g., "Wakaba Mutsumi, green hair, yellow eyes")
        style: Style preset name (cyberpunk, fantasy, etc.)

    Returns:
        Dict with 'positive', 'negative', 'lora_weight', 'style_name'
    """
    # Add style if specified
    style_name = style or random.choice(list(STYLE_PRESETS.keys()))
    style_preset = STYLE_PRESETS[style_name]

    # Build positive prompt - preserve character, add style
    positive_parts = []
    if base_prompt:
        positive_parts.append(base_prompt)

    positive_parts.append(style_preset["keywords"])

    # Build negative prompt
    negative_parts = [
        "worst quality, low quality, bad quality, lowres, bad anatomy",
        style_preset["negative_add"],
    ]

    # Pick LoRA weight from style range
    lora_min, lora_max = style_preset["lora_weight_range"]
    lora_weight = round(random.uniform(lora_min, lora_max), 2)

    return {
        "positive": ", ".join(positive_parts),
        "negative": ", ".join(negative_parts),
        "lora_weight": lora_weight,
        "style_name": style_name,
    }


def generate_lora_weight_sweep(start: float = 0.3, end: float = 1.0, steps: int = 8) -> list[float]:
    """Generate a range of LoRA weights for testing.

    Args:
        start: Minimum weight
        end: Maximum weight
        steps: Number of steps

    Returns:
        List of weights
    """
    if steps == 1:
        return [(start + end) / 2]

    step_size = (end - start) / (steps - 1)
    return [round(start + i * step_size, 2) for i in range(steps)]


def apply_diversity_to_workflow(workflow_data: dict, config: dict) -> dict:
    """Apply diversity settings to a workflow.

    Args:
        workflow_data: Workflow dict
        config: Diversity config with keys:
            - lora_weight: float or None
            - positive_prompt: str or None
            - negative_prompt: str or None
            - seed: int or None
            - sampler: str or None
            - scheduler: str or None
            - cfg: float or None
            - steps: int or None
            - preserve_character: bool (if True, removes artist tags from base prompt)

    Returns:
        Modified workflow dict
    """
    import copy
    import re
    wf = copy.deepcopy(workflow_data)

    # Find and modify LoRA nodes
    if config.get("lora_weight") is not None:
        for node_id, node in wf.items():
            if node.get("class_type") == "LoraLoader":
                node["inputs"]["strength_model"] = config["lora_weight"]
                node["inputs"]["strength_clip"] = config["lora_weight"]

    # Find and modify CLIP text encode nodes
    if config.get("positive_prompt") is not None:
        for node_id, node in wf.items():
            if node.get("class_type") == "CLIPTextEncode":
                prompt = config["positive_prompt"]

                # If preserve_character is True, remove artist tags from base prompt
                if config.get("preserve_character", False):
                    # Remove common artist tag patterns: {{name}}, [[name]], {name}, [name], name
                    # Keep character names and other important tags
                    prompt = re.sub(r'\{\{[^}]+\}\}', '', prompt)  # {{artist}}
                    prompt = re.sub(r'\[\[[^\]]+\]\]', '', prompt)  # [[artist]]
                    prompt = re.sub(r'\{[^}]+\}', '', prompt)       # {artist}
                    prompt = re.sub(r'\[[^\]]+\]', '', prompt)      # [artist]
                    # Clean up multiple commas and spaces
                    prompt = re.sub(r',\s*,', ',', prompt)
                    prompt = re.sub(r'\s+', ' ', prompt)
                    prompt = prompt.strip(', ')

                # First one is typically positive
                node["inputs"]["text"] = prompt
                break

    if config.get("negative_prompt") is not None:
        clip_nodes = []
        for node_id, node in wf.items():
            if node.get("class_type") == "CLIPTextEncode":
                clip_nodes.append(node_id)
        if len(clip_nodes) >= 2:
            wf[clip_nodes[1]]["inputs"]["text"] = config["negative_prompt"]

    # Find and modify sampler nodes
    for node_id, node in wf.items():
        if "sampler" in node.get("class_type", "").lower() or node.get("class_type") == "KSampler":
            inputs = node.get("inputs", {})
            if config.get("seed") is not None and "seed" in inputs:
                node["inputs"]["seed"] = config["seed"]
            if config.get("sampler") is not None and "sampler_name" in inputs:
                node["inputs"]["sampler_name"] = config["sampler"]
            if config.get("scheduler") is not None and "scheduler" in inputs:
                node["inputs"]["scheduler"] = config["scheduler"]
            if config.get("cfg") is not None and "cfg" in inputs:
                node["inputs"]["cfg"] = config["cfg"]
            if config.get("steps") is not None and "steps" in inputs:
                node["inputs"]["steps"] = config["steps"]

    return wf


def get_style_list() -> list[str]:
    """Get list of available style presets."""
    return sorted(STYLE_PRESETS.keys())


def get_style_info(style_name: str) -> dict | None:
    """Get information about a style preset."""
    return STYLE_PRESETS.get(style_name)
