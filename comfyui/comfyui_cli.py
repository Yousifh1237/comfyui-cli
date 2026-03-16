"""comfyui-cli - Command-line interface for ComfyUI.

Usage:
    comfyui-cli [OPTIONS] COMMAND [ARGS]...

Provides workflow execution, model management, queue control, and more.
"""

import copy
import json
import os
import random
import sys
from pathlib import Path

import click

from comfyui.core.client import (
    ComfyUIAPIError,
    ComfyUIClient,
    ComfyUIConnectionError,
    ComfyUITimeoutError,
)
from comfyui.core.generate import (
    build_img2img_workflow,
    build_txt2img_lora_workflow,
    build_txt2img_workflow,
    build_upscale_workflow,
)
from comfyui.core.diverse import (
    apply_diversity_to_workflow,
    generate_lora_weight_sweep,
    generate_random_character_prompt,
    get_style_info,
    get_style_list,
)
from comfyui.core.workflow import Workflow
from comfyui.utils.config import get_server_args, load_config, save_config
from comfyui.utils.formatters import (
    OutputFormatter,
    format_kv,
    format_list,
    format_size,
    format_table,
)


def _get_client(ctx: click.Context) -> ComfyUIClient:
    """Get client from context."""
    return ctx.obj["client"]


def _get_fmt(ctx: click.Context) -> OutputFormatter:
    """Get formatter from context."""
    return ctx.obj["fmt"]


def _handle_error(fmt: OutputFormatter, e: Exception) -> None:
    """Handle common errors."""
    if isinstance(e, ComfyUIConnectionError):
        fmt.error("Cannot connect to ComfyUI server", {"hint": "Is ComfyUI running?"})
    elif isinstance(e, ComfyUIAPIError):
        fmt.error(str(e), e.data if isinstance(e.data, dict) else None)
    elif isinstance(e, ComfyUITimeoutError):
        fmt.error(str(e))
    else:
        fmt.error(str(e))
    sys.exit(1)


def _safe_echo(text: str) -> None:
    """Echo text safely, handling encoding errors on Windows."""
    try:
        click.echo(text)
    except UnicodeEncodeError:
        # Fallback: write UTF-8 directly to stdout buffer
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()


# ============================================================
# Main CLI group
# ============================================================

@click.group()
@click.option("--host", default=None, help="ComfyUI server host")
@click.option("--port", default=None, type=int, help="ComfyUI server port")
@click.option("--ssl", is_flag=True, default=False, help="Use HTTPS/WSS")
@click.option("--json", "json_mode", is_flag=True, default=False, help="Output JSON")
@click.version_option(version="0.1.0", prog_name="comfyui-cli")
@click.pass_context
def cli(ctx, host, port, ssl, json_mode):
    """comfyui-cli - Command-line interface for ComfyUI."""
    config = load_config()
    server_args = get_server_args(config)
    if host:
        server_args["host"] = host
    if port:
        server_args["port"] = port
    if ssl:
        server_args["use_ssl"] = True
    ctx.ensure_object(dict)
    ctx.obj["client"] = ComfyUIClient(**server_args)
    ctx.obj["fmt"] = OutputFormatter(json_mode=json_mode)
    ctx.obj["config"] = config


# ============================================================
# workflow commands
# ============================================================

@cli.group()
def workflow():
    """Manage and execute workflows."""


@workflow.command("run")
@click.argument("file", type=click.Path(exists=True))
@click.option("--seed", type=int, default=None, help="Override seed")
@click.option("--prompt", "prompt_text", default=None, help="Override positive prompt")
@click.option("--negative", default=None, help="Override negative prompt")
@click.option("--checkpoint", default=None, help="Override checkpoint model")
@click.option("--width", type=int, default=None, help="Override width")
@click.option("--height", type=int, default=None, help="Override height")
@click.option("--steps", type=int, default=None, help="Override steps")
@click.option("--cfg", type=float, default=None, help="Override CFG scale")
@click.option("--wait/--no-wait", default=True, help="Wait for completion")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--timeout", type=float, default=600.0, help="Timeout in seconds")
@click.pass_context
def workflow_run(ctx, file, seed, prompt_text, negative, checkpoint,
                 width, height, steps, cfg, wait, save_to, timeout):
    """Execute a workflow from a JSON file."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    try:
        wf = Workflow.from_file(file)

        # Apply overrides
        if seed is not None:
            wf.set_seed(seed)
        if prompt_text is not None:
            wf.set_prompt_text(prompt_text)
        if negative is not None:
            wf.set_negative_text(negative)
        if checkpoint is not None:
            wf.set_checkpoint(checkpoint)
        if width is not None and height is not None:
            wf.set_image_size(width, height)
        if steps is not None:
            for nid, node in wf.data.items():
                if "steps" in node.get("inputs", {}):
                    node["inputs"]["steps"] = steps
        if cfg is not None:
            for nid, node in wf.data.items():
                if "cfg" in node.get("inputs", {}):
                    node["inputs"]["cfg"] = cfg

        if wait:
            def progress_cb(queue, elapsed):
                if not fmt.json_mode:
                    running = len(queue.get("queue_running", []))
                    pending = len(queue.get("queue_pending", []))
                    click.echo(
                        f"\r  Running: {running} | Pending: {pending} | "
                        f"Elapsed: {elapsed:.0f}s",
                        nl=False,
                    )

            if not fmt.json_mode:
                click.echo(f"Submitting workflow ({wf.node_count} nodes)...")

            result = client.execute_and_wait(
                wf.to_dict(),
                poll_interval=1.0,
                timeout=timeout,
                progress_callback=progress_cb if not fmt.json_mode else None,
            )

            if not fmt.json_mode:
                click.echo()  # newline after progress

            status = result.get("status", {})
            outputs = result.get("outputs", {})

            # Download images if requested
            if save_to and outputs:
                save_dir = Path(save_to)
                save_dir.mkdir(parents=True, exist_ok=True)
                for _nid, out in outputs.items():
                    for img in out.get("images", []):
                        fname = img["filename"]
                        dest = str(save_dir / fname)
                        client.view_image(
                            fname,
                            image_type=img.get("type", "output"),
                            subfolder=img.get("subfolder", ""),
                            save_to=dest,
                        )
                        if not fmt.json_mode:
                            click.echo(f"  Saved: {dest}")

            fmt.print(
                {"status": status, "outputs": outputs},
                human_text=(
                    f"Status: {status.get('status_str', 'unknown')}\n"
                    f"Outputs: {sum(len(o.get('images', [])) for o in outputs.values())} images"
                ),
            )
        else:
            result = client.queue_prompt(wf.to_dict())
            fmt.print(
                result,
                human_text=f"Queued: prompt_id={result.get('prompt_id')}",
            )
    except Exception as e:
        _handle_error(fmt, e)


@workflow.command("validate")
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def workflow_validate(ctx, file):
    """Validate a workflow JSON file."""
    fmt = _get_fmt(ctx)
    try:
        wf = Workflow.from_file(file)
        errors = wf.validate_structure()
        summary = wf.summary()
        if errors:
            fmt.print(
                {"valid": False, "errors": errors, "summary": summary},
                human_text="INVALID\n" + format_list(errors),
            )
            sys.exit(1)
        else:
            fmt.print(
                {"valid": True, "summary": summary},
                human_text=(
                    f"VALID - {wf.node_count} nodes, "
                    f"{len(summary['output_nodes'])} outputs\n"
                    f"Types: {', '.join(summary['class_types'])}"
                ),
            )
    except Exception as e:
        _handle_error(fmt, e)


@workflow.command("info")
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def workflow_info(ctx, file):
    """Show detailed information about a workflow."""
    fmt = _get_fmt(ctx)
    try:
        wf = Workflow.from_file(file)
        summary = wf.summary()

        if fmt.json_mode:
            fmt.print(summary)
        else:
            click.echo(f"Workflow: {file}")
            click.echo(f"Nodes: {summary['node_count']}")
            click.echo(f"Output nodes: {', '.join(summary['output_nodes']) or 'none'}")
            click.echo("\nNode types:")
            for ct, count in sorted(summary["class_counts"].items()):
                click.echo(f"  {ct}: {count}")
            if summary["errors"]:
                click.echo("\nValidation errors:")
                click.echo(format_list(summary["errors"]))
    except Exception as e:
        _handle_error(fmt, e)


@workflow.command("batch")
@click.argument("file", type=click.Path(exists=True))
@click.option("--seeds", default=None, help="Comma-separated seeds (e.g. 1,2,3,42)")
@click.option("--count", type=int, default=None, help="Number of random seeds to generate")
@click.option("--prompts", default=None, help="Comma-separated prompts (use | separator)")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--timeout", type=float, default=600.0, help="Timeout per execution")
@click.pass_context
def workflow_batch(ctx, file, seeds, count, prompts, save_to, timeout):
    """Run a workflow multiple times with different seeds or prompts."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    try:
        wf_base = Workflow.from_file(file)

        # Build list of variations
        variations = []
        if seeds:
            for s in seeds.split(","):
                variations.append({"seed": int(s.strip())})
        elif count:
            for _ in range(count):
                variations.append({"seed": random.randint(0, 2**63 - 1)})
        elif prompts:
            for p in prompts.split("|"):
                variations.append({"prompt": p.strip()})
        else:
            fmt.error("Provide --seeds, --count, or --prompts")
            sys.exit(1)

        results = []
        total = len(variations)

        for i, var in enumerate(variations):
            wf = Workflow(copy.deepcopy(wf_base.to_dict()))

            if "seed" in var:
                wf.set_seed(var["seed"])
            if "prompt" in var:
                wf.set_prompt_text(var["prompt"])

            if not fmt.json_mode:
                label = var.get("seed", var.get("prompt", "?"))
                click.echo(f"[{i + 1}/{total}] Running variation: {label}")

            result = client.execute_and_wait(wf.to_dict(), timeout=timeout)
            outputs = result.get("outputs", {})
            status = result.get("status", {})

            if save_to and outputs:
                save_dir = Path(save_to)
                save_dir.mkdir(parents=True, exist_ok=True)
                for _nid, out in outputs.items():
                    for img in out.get("images", []):
                        dest = str(save_dir / img["filename"])
                        client.view_image(
                            img["filename"],
                            image_type=img.get("type", "output"),
                            subfolder=img.get("subfolder", ""),
                            save_to=dest,
                        )
                        if not fmt.json_mode:
                            click.echo(f"  Saved: {dest}")

            results.append({
                "variation": var,
                "status": status.get("status_str", "?"),
                "images": sum(len(o.get("images", [])) for o in outputs.values()),
            })

        if fmt.json_mode:
            fmt.print(results)
        else:
            click.echo(f"\nBatch complete: {total} runs")
            click.echo(format_table(
                [{"#": i + 1, **r} for i, r in enumerate(results)],
                columns=["#", "variation", "status", "images"],
            ))
    except Exception as e:
        _handle_error(fmt, e)


# ============================================================
# queue commands
# ============================================================

@cli.group()
def queue():
    """Manage the execution queue."""


@queue.command("status")
@click.pass_context
def queue_status(ctx):
    """Show current queue status."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        q = client.get_queue()
        running = q.get("queue_running", [])
        pending = q.get("queue_pending", [])
        fmt.print(
            q,
            human_text=(
                f"Running: {len(running)}\n"
                f"Pending: {len(pending)}"
            ),
        )
    except Exception as e:
        _handle_error(fmt, e)


@queue.command("clear")
@click.confirmation_option(prompt="Clear entire queue?")
@click.pass_context
def queue_clear(ctx):
    """Clear all pending queue items."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        client.clear_queue()
        fmt.print({"cleared": True}, human_text="Queue cleared.")
    except Exception as e:
        _handle_error(fmt, e)


@queue.command("delete")
@click.argument("prompt_ids", nargs=-1, required=True)
@click.pass_context
def queue_delete(ctx, prompt_ids):
    """Delete specific items from the queue."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        client.delete_queue_items(list(prompt_ids))
        fmt.print(
            {"deleted": list(prompt_ids)},
            human_text=f"Deleted {len(prompt_ids)} item(s).",
        )
    except Exception as e:
        _handle_error(fmt, e)


@queue.command("submit")
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def queue_submit(ctx, file):
    """Submit a workflow JSON to the queue (fire-and-forget)."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        wf = Workflow.from_file(file)
        result = client.queue_prompt(wf.to_dict())
        fmt.print(
            result,
            human_text=f"Queued: prompt_id={result.get('prompt_id')}",
        )
    except Exception as e:
        _handle_error(fmt, e)


# ============================================================
# models commands
# ============================================================

@cli.group()
def models():
    """List and inspect models."""


@models.command("types")
@click.pass_context
def models_types(ctx):
    """List available model folder types."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        types = client.get_model_types()
        fmt.print(types, human_text=format_list(sorted(types)))
    except Exception as e:
        _handle_error(fmt, e)


@models.command("list")
@click.argument("folder", default="checkpoints")
@click.pass_context
def models_list(ctx, folder):
    """List models in a folder (default: checkpoints)."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        items = client.get_models(folder)
        fmt.print(
            {"folder": folder, "count": len(items), "models": items},
            human_text=f"[{folder}] ({len(items)} models)\n" + format_list(items),
        )
    except Exception as e:
        _handle_error(fmt, e)


@models.command("metadata")
@click.argument("folder")
@click.argument("filename")
@click.pass_context
def models_metadata(ctx, folder, filename):
    """Get metadata for a safetensors model."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        meta = client.get_model_metadata(folder, filename)
        if fmt.json_mode:
            fmt.print(meta)
        else:
            if isinstance(meta, dict):
                click.echo(format_kv(meta))
            else:
                click.echo(str(meta))
    except Exception as e:
        _handle_error(fmt, e)


@models.command("embeddings")
@click.pass_context
def models_embeddings(ctx):
    """List available embeddings."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        items = client.get_embeddings()
        fmt.print(
            {"count": len(items), "embeddings": items},
            human_text=f"Embeddings ({len(items)}):\n" + format_list(items),
        )
    except Exception as e:
        _handle_error(fmt, e)


# ============================================================
# nodes commands
# ============================================================

@cli.group()
def nodes():
    """Query available nodes."""


@nodes.command("list")
@click.option("--category", default=None, help="Filter by category")
@click.pass_context
def nodes_list(ctx, category):
    """List all available nodes."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        info = client.get_node_info()
        rows = []
        for name, data in sorted(info.items()):
            cat = data.get("category", "")
            if category and category.lower() not in cat.lower():
                continue
            rows.append({
                "name": name,
                "display_name": data.get("display_name", name),
                "category": cat,
                "output": data.get("output_node", False),
            })

        if fmt.json_mode:
            fmt.print(rows)
        else:
            click.echo(f"Total: {len(rows)} nodes")
            click.echo(format_table(
                rows[:100],
                columns=["name", "display_name", "category", "output"],
                max_width=120,
            ))
            if len(rows) > 100:
                click.echo(f"  ... and {len(rows) - 100} more (use --json for full list)")
    except Exception as e:
        _handle_error(fmt, e)


@nodes.command("info")
@click.argument("node_class")
@click.pass_context
def nodes_info(ctx, node_class):
    """Show detailed info about a specific node."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        info = client.get_node_info(node_class)
        node = info.get(node_class, info)

        if fmt.json_mode:
            fmt.print(node)
        else:
            click.echo(f"Node: {node.get('display_name', node_class)}")
            click.echo(f"Class: {node.get('name', node_class)}")
            click.echo(f"Category: {node.get('category', '')}")
            click.echo(f"Description: {node.get('description', '(none)')}")
            click.echo(f"Output Node: {node.get('output_node', False)}")

            inputs = node.get("input", {})
            for section in ("required", "optional"):
                section_inputs = inputs.get(section, {})
                if section_inputs:
                    click.echo(f"\n{section.title()} Inputs:")
                    for iname, idef in section_inputs.items():
                        if isinstance(idef, list) and len(idef) >= 1:
                            if isinstance(idef[0], list):
                                click.echo(f"  {iname}: enum {idef[0][:5]}{'...' if len(idef[0]) > 5 else ''}")
                            else:
                                opts = idef[1] if len(idef) > 1 else {}
                                click.echo(f"  {iname}: {idef[0]} {opts}")
                        else:
                            click.echo(f"  {iname}: {idef}")

            outputs = node.get("output", [])
            output_names = node.get("output_name", outputs)
            if outputs:
                click.echo(f"\nOutputs: {', '.join(str(n) for n in output_names)}")
    except Exception as e:
        _handle_error(fmt, e)


@nodes.command("search")
@click.argument("query")
@click.pass_context
def nodes_search(ctx, query):
    """Search nodes by name or category."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        info = client.get_node_info()
        query_lower = query.lower()
        matches = []
        for name, data in sorted(info.items()):
            searchable = " ".join([
                name, data.get("display_name", ""),
                data.get("category", ""),
                data.get("description", ""),
            ]).lower()
            if query_lower in searchable:
                matches.append({
                    "name": name,
                    "display_name": data.get("display_name", name),
                    "category": data.get("category", ""),
                })

        if fmt.json_mode:
            fmt.print(matches)
        else:
            click.echo(f"Found {len(matches)} nodes matching '{query}':")
            click.echo(format_table(
                matches[:50],
                columns=["name", "display_name", "category"],
                max_width=120,
            ))
    except Exception as e:
        _handle_error(fmt, e)


@nodes.command("samplers")
@click.pass_context
def nodes_samplers(ctx):
    """List available samplers from the running server."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        info = client.get_node_info("KSampler")
        node = info.get("KSampler", {})
        required = node.get("input", {}).get("required", {})
        samplers = []
        schedulers = []
        for key, val in required.items():
            if key == "sampler_name" and isinstance(val, list) and isinstance(val[0], list):
                samplers = val[0]
            if key == "scheduler" and isinstance(val, list) and isinstance(val[0], list):
                schedulers = val[0]
        fmt.print(
            {"samplers": samplers, "schedulers": schedulers},
            human_text=(
                f"Samplers ({len(samplers)}):\n"
                + format_list(samplers)
                + f"\n\nSchedulers ({len(schedulers)}):\n"
                + format_list(schedulers)
            ),
        )
    except Exception as e:
        _handle_error(fmt, e)


@nodes.command("categories")
@click.pass_context
def nodes_categories(ctx):
    """List all node categories."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        info = client.get_node_info()
        cats: dict[str, int] = {}
        for _name, data in info.items():
            cat = data.get("category", "(uncategorized)")
            cats[cat] = cats.get(cat, 0) + 1
        sorted_cats = sorted(cats.items(), key=lambda x: x[0])
        if fmt.json_mode:
            fmt.print({c: n for c, n in sorted_cats})
        else:
            click.echo(f"Categories ({len(sorted_cats)}):")
            for cat, count in sorted_cats:
                _safe_echo(f"  {cat}: {count} nodes")
    except Exception as e:
        _handle_error(fmt, e)


# ============================================================
# history commands
# ============================================================

@cli.group()
def history():
    """View and manage execution history."""


@history.command("list")
@click.option("--max-items", type=int, default=20, help="Max items to show")
@click.pass_context
def history_list(ctx, max_items):
    """List recent execution history."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        hist = client.get_history(max_items=max_items)
        rows = []
        for pid, entry in hist.items():
            status = entry.get("status", {})
            outputs = entry.get("outputs", {})
            image_count = sum(
                len(o.get("images", [])) for o in outputs.values()
            )
            rows.append({
                "prompt_id": pid[:12] + "...",
                "status": status.get("status_str", "?"),
                "images": image_count,
            })

        if fmt.json_mode:
            fmt.print(hist)
        else:
            click.echo(f"History ({len(rows)} entries):")
            click.echo(format_table(rows, columns=["prompt_id", "status", "images"]))
    except Exception as e:
        _handle_error(fmt, e)


@history.command("get")
@click.argument("prompt_id")
@click.pass_context
def history_get(ctx, prompt_id):
    """Get details for a specific execution."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        hist = client.get_history(prompt_id=prompt_id)
        entry = hist.get(prompt_id, {})
        if not entry:
            fmt.error(f"No history found for {prompt_id}")
            sys.exit(1)
        fmt.print(entry)
    except Exception as e:
        _handle_error(fmt, e)


@history.command("clear")
@click.confirmation_option(prompt="Clear all history?")
@click.pass_context
def history_clear(ctx):
    """Clear all execution history."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        client.clear_history()
        fmt.print({"cleared": True}, human_text="History cleared.")
    except Exception as e:
        _handle_error(fmt, e)


@history.command("save-images")
@click.argument("prompt_id")
@click.option("--save-to", required=True, help="Directory to save images")
@click.pass_context
def history_save_images(ctx, prompt_id, save_to):
    """Download all images from a specific history entry."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        hist = client.get_history(prompt_id=prompt_id)
        entry = hist.get(prompt_id, {})
        if not entry:
            fmt.error(f"No history found for {prompt_id}")
            sys.exit(1)

        outputs = entry.get("outputs", {})
        save_dir = Path(save_to)
        save_dir.mkdir(parents=True, exist_ok=True)

        saved = []
        for _nid, out in outputs.items():
            for img in out.get("images", []):
                fname = img["filename"]
                dest = str(save_dir / fname)
                client.view_image(
                    fname,
                    image_type=img.get("type", "output"),
                    subfolder=img.get("subfolder", ""),
                    save_to=dest,
                )
                saved.append(dest)
                if not fmt.json_mode:
                    click.echo(f"  Saved: {dest}")

        fmt.print(
            {"saved": saved, "count": len(saved)},
            human_text=f"Saved {len(saved)} image(s) to {save_to}",
        )
    except Exception as e:
        _handle_error(fmt, e)


# ============================================================
# images commands
# ============================================================

@cli.group()
def images():
    """Upload and download images."""


@images.command("upload")
@click.argument("file", type=click.Path(exists=True))
@click.option("--type", "image_type", default="input",
              type=click.Choice(["input", "temp", "output"]))
@click.option("--subfolder", default="")
@click.option("--overwrite", is_flag=True, default=False)
@click.pass_context
def images_upload(ctx, file, image_type, subfolder, overwrite):
    """Upload an image to the ComfyUI server."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        result = client.upload_image(file, image_type, subfolder, overwrite)
        fmt.print(
            result,
            human_text=(
                f"Uploaded: {result.get('name')}\n"
                f"Type: {result.get('type')}\n"
                f"Subfolder: {result.get('subfolder', '')}"
            ),
        )
    except Exception as e:
        _handle_error(fmt, e)


@images.command("download")
@click.argument("filename")
@click.option("--type", "image_type", default="output",
              type=click.Choice(["input", "temp", "output"]))
@click.option("--subfolder", default="")
@click.option("--save-to", required=True, help="Path to save the image")
@click.pass_context
def images_download(ctx, filename, image_type, subfolder, save_to):
    """Download an image from the ComfyUI server."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        result = client.view_image(filename, image_type, subfolder, save_to=save_to)
        if isinstance(result, dict):
            fmt.print(result, human_text=f"Saved to: {result.get('saved_to')}")
        else:
            fmt.print(
                {"saved_to": save_to, "size": len(result)},
                human_text=f"Saved {len(result)} bytes to {save_to}",
            )
    except Exception as e:
        _handle_error(fmt, e)


@images.command("list")
@click.option("--type", "dir_type", default="output",
              type=click.Choice(["input", "temp", "output"]))
@click.pass_context
def images_list(ctx, dir_type):
    """List files in the output/input/temp directory."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        files = client.list_files(dir_type)
        if fmt.json_mode:
            fmt.print({"directory": dir_type, "count": len(files), "files": files})
        else:
            if isinstance(files, list):
                # files may be dicts or strings
                if files and isinstance(files[0], dict):
                    rows = []
                    for f in files:
                        rows.append({
                            "name": f.get("name", f.get("path", "?")),
                            "size": format_size(f["size"]) if "size" in f else "?",
                            "type": f.get("type", "?"),
                        })
                    click.echo(f"[{dir_type}] ({len(rows)} files)")
                    click.echo(format_table(rows[:100], columns=["name", "size", "type"]))
                    if len(rows) > 100:
                        click.echo(f"  ... and {len(rows) - 100} more")
                else:
                    click.echo(f"[{dir_type}] ({len(files)} files)")
                    click.echo(format_list(files[:100]))
                    if len(files) > 100:
                        click.echo(f"  ... and {len(files) - 100} more")
            else:
                click.echo(str(files))
    except Exception as e:
        _handle_error(fmt, e)


# ============================================================
# system commands
# ============================================================

@cli.group()
def system():
    """System info and control."""


@system.command("stats")
@click.pass_context
def system_stats(ctx):
    """Show system statistics."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        stats = client.get_system_stats()
        if fmt.json_mode:
            fmt.print(stats)
        else:
            sys_info = stats.get("system", {})
            click.echo(f"OS: {sys_info.get('os', '?')}")
            click.echo(f"RAM Total: {format_size(sys_info.get('ram_total', 0))}")
            click.echo(f"RAM Free: {format_size(sys_info.get('ram_free', 0))}")
            click.echo(f"Python: {sys_info.get('python_version', '?')}")
            click.echo(f"PyTorch: {sys_info.get('pytorch_version', '?')}")
            click.echo(f"ComfyUI: {sys_info.get('comfyui_version', '?')}")

            devices = stats.get("devices", [])
            for i, dev in enumerate(devices):
                click.echo(f"\nGPU {i}: {dev.get('name', '?')}")
                click.echo(f"  Type: {dev.get('type', '?')}")
                click.echo(f"  VRAM Total: {format_size(dev.get('vram_total', 0))}")
                click.echo(f"  VRAM Free: {format_size(dev.get('vram_free', 0))}")
                click.echo(f"  Torch VRAM Total: {format_size(dev.get('torch_vram_total', 0))}")
                click.echo(f"  Torch VRAM Free: {format_size(dev.get('torch_vram_free', 0))}")
    except Exception as e:
        _handle_error(fmt, e)


@system.command("interrupt")
@click.pass_context
def system_interrupt(ctx):
    """Interrupt the currently running workflow."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        client.interrupt()
        fmt.print({"interrupted": True}, human_text="Interrupt signal sent.")
    except Exception as e:
        _handle_error(fmt, e)


@system.command("free")
@click.option("--unload-models/--no-unload-models", default=True)
@click.option("--free-memory/--no-free-memory", default=True)
@click.pass_context
def system_free(ctx, unload_models, free_memory):
    """Free GPU memory."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        client.free_memory(unload_models=unload_models, free_memory=free_memory)
        fmt.print(
            {"freed": True, "unload_models": unload_models, "free_memory": free_memory},
            human_text="Memory freed.",
        )
    except Exception as e:
        _handle_error(fmt, e)


@system.command("extensions")
@click.pass_context
def system_extensions(ctx):
    """List loaded extensions."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        exts = client.get_extensions()
        fmt.print(exts, human_text=format_list(exts))
    except Exception as e:
        _handle_error(fmt, e)


@system.command("ping")
@click.pass_context
def system_ping(ctx):
    """Check if ComfyUI server is running."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    alive = client.is_server_running()
    fmt.print(
        {"alive": alive, "url": client.base_url},
        human_text=f"{'ALIVE' if alive else 'UNREACHABLE'} - {client.base_url}",
    )
    if not alive:
        sys.exit(1)


@system.command("paths")
@click.pass_context
def system_paths(ctx):
    """Show all configured folder paths."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        paths = client.get_folder_paths()
        if fmt.json_mode:
            fmt.print(paths)
        else:
            if isinstance(paths, dict):
                for name, info in sorted(paths.items()):
                    if isinstance(info, list):
                        click.echo(f"{name}:")
                        for p in info:
                            click.echo(f"  {p}")
                    elif isinstance(info, dict):
                        dirs = info.get("paths", info.get("directories", [info]))
                        click.echo(f"{name}: {', '.join(str(d) for d in dirs) if isinstance(dirs, list) else dirs}")
                    else:
                        click.echo(f"{name}: {info}")
            else:
                click.echo(str(paths))
    except Exception as e:
        _handle_error(fmt, e)


@system.command("logs")
@click.option("--raw", is_flag=True, default=False, help="Get raw log format")
@click.pass_context
def system_logs(ctx, raw):
    """View server logs."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)
    try:
        logs = client.get_logs(raw=raw)
        if fmt.json_mode:
            fmt.print(logs)
        else:
            if isinstance(logs, str):
                _safe_echo(logs)
            elif isinstance(logs, dict):
                entries = logs.get("entries", logs.get("logs", []))
                if isinstance(entries, list):
                    for entry in entries:
                        _safe_echo(str(entry))
                else:
                    click.echo(format_kv(logs))
            else:
                _safe_echo(str(logs))
    except Exception as e:
        _handle_error(fmt, e)


# ============================================================
# generate commands
# ============================================================

@cli.group()
def generate():
    """High-level generation commands."""


@generate.command("txt2img")
@click.option("--prompt", "positive", required=True, help="Positive prompt text")
@click.option("--negative", default="", help="Negative prompt text")
@click.option("--checkpoint", required=True, help="Checkpoint model name")
@click.option("--width", type=int, default=512)
@click.option("--height", type=int, default=512)
@click.option("--steps", type=int, default=20)
@click.option("--cfg", type=float, default=7.0)
@click.option("--sampler", default="euler")
@click.option("--scheduler", default="normal")
@click.option("--seed", type=int, default=None, help="Random seed (default: random)")
@click.option("--batch-size", type=int, default=1)
@click.option("--prefix", default="ComfyUI", help="Output filename prefix")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--timeout", type=float, default=600.0)
@click.pass_context
def generate_txt2img(ctx, positive, negative, checkpoint, width, height,
                     steps, cfg, sampler, scheduler, seed, batch_size,
                     prefix, save_to, timeout):
    """Generate images from text prompts."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    if seed is None:
        seed = random.randint(0, 2**63 - 1)

    try:
        prompt = build_txt2img_workflow(
            checkpoint=checkpoint,
            positive_prompt=positive,
            negative_prompt=negative,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            seed=seed,
            batch_size=batch_size,
            filename_prefix=prefix,
        )

        if not fmt.json_mode:
            click.echo(f"Generating {width}x{height} with {checkpoint}...")
            click.echo(f"Prompt: {positive[:80]}{'...' if len(positive) > 80 else ''}")
            click.echo(f"Seed: {seed}, Steps: {steps}, CFG: {cfg}")

        result = client.execute_and_wait(
            prompt, timeout=timeout,
            progress_callback=(
                lambda q, t: click.echo(
                    f"\r  Elapsed: {t:.0f}s", nl=False
                ) if not fmt.json_mode else None
            ),
        )

        if not fmt.json_mode:
            click.echo()

        outputs = result.get("outputs", {})
        status = result.get("status", {})

        if save_to and outputs:
            save_dir = Path(save_to)
            save_dir.mkdir(parents=True, exist_ok=True)
            for _nid, out in outputs.items():
                for img in out.get("images", []):
                    dest = str(save_dir / img["filename"])
                    client.view_image(
                        img["filename"],
                        image_type=img.get("type", "output"),
                        subfolder=img.get("subfolder", ""),
                        save_to=dest,
                    )
                    if not fmt.json_mode:
                        click.echo(f"  Saved: {dest}")

        fmt.print(
            {"status": status, "outputs": outputs, "seed": seed},
            human_text=f"Done! Status: {status.get('status_str', '?')}",
        )
    except Exception as e:
        _handle_error(fmt, e)


@generate.command("img2img")
@click.option("--prompt", "positive", required=True, help="Positive prompt text")
@click.option("--negative", default="", help="Negative prompt text")
@click.option("--checkpoint", required=True, help="Checkpoint model name")
@click.option("--image", required=True, help="Input image (filename in input dir, or path to upload)")
@click.option("--steps", type=int, default=20)
@click.option("--cfg", type=float, default=7.0)
@click.option("--sampler", default="euler")
@click.option("--scheduler", default="normal")
@click.option("--seed", type=int, default=None)
@click.option("--denoise", type=float, default=0.7, help="Denoise strength (0-1)")
@click.option("--prefix", default="ComfyUI", help="Output filename prefix")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--upload", is_flag=True, default=False, help="Upload the image first")
@click.option("--timeout", type=float, default=600.0)
@click.pass_context
def generate_img2img(ctx, positive, negative, checkpoint, image, steps, cfg,
                     sampler, scheduler, seed, denoise, prefix, save_to,
                     upload, timeout):
    """Generate images from an input image + text prompt."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    if seed is None:
        seed = random.randint(0, 2**63 - 1)

    try:
        image_name = image
        if upload and Path(image).exists():
            if not fmt.json_mode:
                click.echo(f"Uploading {image}...")
            result = client.upload_image(image)
            image_name = result.get("name", image)

        prompt = build_img2img_workflow(
            checkpoint=checkpoint,
            positive_prompt=positive,
            image_filename=image_name,
            negative_prompt=negative,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            seed=seed,
            denoise=denoise,
            filename_prefix=prefix,
        )

        if not fmt.json_mode:
            click.echo(f"Running img2img with {checkpoint}...")
            click.echo(f"Input: {image_name}, Denoise: {denoise}")

        result = client.execute_and_wait(prompt, timeout=timeout)

        outputs = result.get("outputs", {})
        status = result.get("status", {})

        if save_to and outputs:
            save_dir = Path(save_to)
            save_dir.mkdir(parents=True, exist_ok=True)
            for _nid, out in outputs.items():
                for img in out.get("images", []):
                    dest = str(save_dir / img["filename"])
                    client.view_image(
                        img["filename"],
                        image_type=img.get("type", "output"),
                        subfolder=img.get("subfolder", ""),
                        save_to=dest,
                    )
                    if not fmt.json_mode:
                        click.echo(f"  Saved: {dest}")

        fmt.print(
            {"status": status, "outputs": outputs, "seed": seed},
            human_text=f"Done! Status: {status.get('status_str', '?')}",
        )
    except Exception as e:
        _handle_error(fmt, e)


@generate.command("txt2img-lora")
@click.option("--prompt", "positive", required=True, help="Positive prompt text")
@click.option("--negative", default="", help="Negative prompt text")
@click.option("--checkpoint", required=True, help="Checkpoint model name")
@click.option("--lora", required=True, help="LoRA model name")
@click.option("--lora-strength", type=float, default=1.0, help="LoRA model strength")
@click.option("--lora-clip-strength", type=float, default=None,
              help="LoRA CLIP strength (default: same as model strength)")
@click.option("--width", type=int, default=512)
@click.option("--height", type=int, default=512)
@click.option("--steps", type=int, default=20)
@click.option("--cfg", type=float, default=7.0)
@click.option("--sampler", default="euler")
@click.option("--scheduler", default="normal")
@click.option("--seed", type=int, default=None)
@click.option("--batch-size", type=int, default=1)
@click.option("--prefix", default="ComfyUI", help="Output filename prefix")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--timeout", type=float, default=600.0)
@click.pass_context
def generate_txt2img_lora(ctx, positive, negative, checkpoint, lora,
                          lora_strength, lora_clip_strength, width, height,
                          steps, cfg, sampler, scheduler, seed, batch_size,
                          prefix, save_to, timeout):
    """Generate images with LoRA applied."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    if seed is None:
        seed = random.randint(0, 2**63 - 1)
    if lora_clip_strength is None:
        lora_clip_strength = lora_strength

    try:
        prompt = build_txt2img_lora_workflow(
            checkpoint=checkpoint,
            positive_prompt=positive,
            lora_name=lora,
            lora_strength_model=lora_strength,
            lora_strength_clip=lora_clip_strength,
            negative_prompt=negative,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            sampler=sampler,
            scheduler=scheduler,
            seed=seed,
            batch_size=batch_size,
            filename_prefix=prefix,
        )

        if not fmt.json_mode:
            click.echo(f"Generating {width}x{height} with {checkpoint} + LoRA: {lora}")
            click.echo(f"Prompt: {positive[:80]}{'...' if len(positive) > 80 else ''}")
            click.echo(f"Seed: {seed}, Steps: {steps}, CFG: {cfg}, LoRA strength: {lora_strength}")

        result = client.execute_and_wait(prompt, timeout=timeout)

        if not fmt.json_mode:
            click.echo()

        outputs = result.get("outputs", {})
        status = result.get("status", {})

        if save_to and outputs:
            save_dir = Path(save_to)
            save_dir.mkdir(parents=True, exist_ok=True)
            for _nid, out in outputs.items():
                for img in out.get("images", []):
                    dest = str(save_dir / img["filename"])
                    client.view_image(
                        img["filename"],
                        image_type=img.get("type", "output"),
                        subfolder=img.get("subfolder", ""),
                        save_to=dest,
                    )
                    if not fmt.json_mode:
                        click.echo(f"  Saved: {dest}")

        fmt.print(
            {"status": status, "outputs": outputs, "seed": seed},
            human_text=f"Done! Status: {status.get('status_str', '?')}",
        )
    except Exception as e:
        _handle_error(fmt, e)


@generate.command("upscale")
@click.option("--image", required=True, help="Input image filename (in input dir)")
@click.option("--model", "upscale_model", default="RealESRGAN_x4plus.pth",
              help="Upscale model name")
@click.option("--prefix", default="ComfyUI_upscale", help="Output filename prefix")
@click.option("--upload", is_flag=True, default=False, help="Upload the image first")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--timeout", type=float, default=600.0)
@click.pass_context
def generate_upscale(ctx, image, upscale_model, prefix, upload, save_to, timeout):
    """Upscale an image using an upscale model."""
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    try:
        image_name = image
        if upload and Path(image).exists():
            if not fmt.json_mode:
                click.echo(f"Uploading {image}...")
            result = client.upload_image(image)
            image_name = result.get("name", image)

        prompt = build_upscale_workflow(
            image_filename=image_name,
            upscale_model=upscale_model,
            filename_prefix=prefix,
        )

        if not fmt.json_mode:
            click.echo(f"Upscaling {image_name} with {upscale_model}...")

        result = client.execute_and_wait(prompt, timeout=timeout)

        outputs = result.get("outputs", {})
        status = result.get("status", {})

        if save_to and outputs:
            save_dir = Path(save_to)
            save_dir.mkdir(parents=True, exist_ok=True)
            for _nid, out in outputs.items():
                for img in out.get("images", []):
                    dest = str(save_dir / img["filename"])
                    client.view_image(
                        img["filename"],
                        image_type=img.get("type", "output"),
                        subfolder=img.get("subfolder", ""),
                        save_to=dest,
                    )
                    if not fmt.json_mode:
                        click.echo(f"  Saved: {dest}")

        fmt.print(
            {"status": status, "outputs": outputs},
            human_text=f"Done! Status: {status.get('status_str', '?')}",
        )
    except Exception as e:
        _handle_error(fmt, e)


@generate.command("diverse")
@click.argument("file", type=click.Path(exists=True))
@click.option("--count", type=int, default=4, help="Number of style variations to generate")
@click.option("--styles", default=None, help="Comma-separated styles (e.g., 'cyberpunk,fantasy,anime') or leave empty for random")
@click.option("--lora-weight-min", type=float, default=0.75, help="Minimum LoRA weight")
@click.option("--lora-weight-max", type=float, default=0.85, help="Maximum LoRA weight")
@click.option("--preserve-character/--no-preserve-character", default=True, help="Remove artist tags to preserve character likeness (recommended for character LoRAs)")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--timeout", type=float, default=600.0)
@click.pass_context
def generate_diverse(ctx, file, count, styles, lora_weight_min,
                     lora_weight_max, preserve_character, save_to, timeout):
    """Generate the same character in different artistic styles.

    This command preserves the character identity from your workflow
    while applying different artistic styles (cyberpunk, fantasy, anime, etc.).

    With --preserve-character (default), it removes artist tags from your
    base prompt to prevent style conflicts with the character LoRA.

    Example:
        comfyui-cli generate diverse wakaba_workflow.json --count 6 --styles "cyberpunk,fantasy,anime"
    """
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    try:
        wf_base = Workflow.from_file(file)

        # Get base prompt from workflow
        base_prompt = ""
        for node_id, node in wf_base.to_dict().items():
            if node.get("class_type") == "CLIPTextEncode":
                base_prompt = node.get("inputs", {}).get("text", "")
                break

        # Parse styles
        style_list = []
        if styles:
            style_list = [s.strip() for s in styles.split(",")]
        else:
            # Use all available styles
            style_list = get_style_list()

        # Generate variations
        if not fmt.json_mode:
            click.echo(f"Generating {count} style variations of the same character...")
            click.echo(f"Base prompt: {base_prompt[:80]}{'...' if len(base_prompt) > 80 else ''}")
            if preserve_character:
                click.echo("Character preservation: ON (removing artist tags)")
            click.echo()

        results = []

        for i in range(count):
            # Pick style (cycle through list if count > len(styles))
            style = style_list[i % len(style_list)]

            # Generate style-specific prompt
            char_config = generate_random_character_prompt(base_prompt, style)

            # Pick random LoRA weight
            lora_weight = round(random.uniform(lora_weight_min, lora_weight_max), 2)

            # Generate random seed
            seed = random.randint(100000, 999999)

            if not fmt.json_mode:
                click.echo(f"[{i+1}/{count}] Style: {char_config['style_name']}, LoRA: {lora_weight}, Seed: {seed}")

            # Apply diversity settings
            diversity_config = {
                "lora_weight": lora_weight,
                "positive_prompt": char_config["positive"],
                "negative_prompt": char_config["negative"],
                "seed": seed,
                "preserve_character": preserve_character,
            }

            wf_modified = apply_diversity_to_workflow(wf_base.to_dict(), diversity_config)

            # Execute
            result = client.execute_and_wait(wf_modified, timeout=timeout)
            outputs = result.get("outputs", {})
            status = result.get("status", {})

            # Save images
            if save_to and outputs:
                save_dir = Path(save_to)
                save_dir.mkdir(parents=True, exist_ok=True)
                for _nid, out in outputs.items():
                    for img in out.get("images", []):
                        dest = str(save_dir / img["filename"])
                        client.view_image(
                            img["filename"],
                            image_type=img.get("type", "output"),
                            subfolder=img.get("subfolder", ""),
                            save_to=dest,
                        )
                        if not fmt.json_mode:
                            click.echo(f"  Saved: {dest}")

            results.append({
                "index": i + 1,
                "style": char_config["style_name"],
                "lora_weight": lora_weight,
                "seed": seed,
                "status": status.get("status_str", "?"),
                "images": sum(len(o.get("images", [])) for o in outputs.values()),
            })

            if not fmt.json_mode:
                click.echo()

        if fmt.json_mode:
            fmt.print(results)
        else:
            click.echo(f"Batch complete! Generated {count} style variations.")
            click.echo(format_table(
                results,
                columns=["index", "style", "lora_weight", "seed", "status", "images"],
            ))
    except Exception as e:
        _handle_error(fmt, e)


@generate.command("lora-sweep")
@click.argument("file", type=click.Path(exists=True))
@click.option("--start", type=float, default=0.3, help="Starting LoRA weight")
@click.option("--end", type=float, default=1.0, help="Ending LoRA weight")
@click.option("--steps", type=int, default=8, help="Number of steps")
@click.option("--save-to", default=None, help="Save output images to directory")
@click.option("--timeout", type=float, default=600.0)
@click.pass_context
def generate_lora_sweep(ctx, file, start, end, steps, save_to, timeout):
    """Test different LoRA weights to find optimal diversity.

    Generates multiple images with the same prompt but different LoRA weights,
    helping you find the sweet spot that balances character consistency with
    facial diversity.

    Example:
        comfyui-cli generate lora-sweep my_workflow.json --start 0.4 --end 0.8 --steps 5
    """
    client = _get_client(ctx)
    fmt = _get_fmt(ctx)

    try:
        wf_base = Workflow.from_file(file)
        weights = generate_lora_weight_sweep(start, end, steps)

        if not fmt.json_mode:
            click.echo(f"Testing {len(weights)} LoRA weights: {weights}")
            click.echo()

        results = []

        for i, weight in enumerate(weights):
            if not fmt.json_mode:
                click.echo(f"[{i+1}/{len(weights)}] LoRA weight: {weight}")

            # Apply weight
            diversity_config = {
                "lora_weight": weight,
                "seed": random.randint(100000, 999999),  # Random seed for each
            }

            wf_modified = apply_diversity_to_workflow(wf_base.to_dict(), diversity_config)

            # Execute
            result = client.execute_and_wait(wf_modified, timeout=timeout)
            outputs = result.get("outputs", {})
            status = result.get("status", {})

            # Save images
            if save_to and outputs:
                save_dir = Path(save_to)
                save_dir.mkdir(parents=True, exist_ok=True)
                for _nid, out in outputs.items():
                    for img in out.get("images", []):
                        # Rename to include weight
                        filename = img["filename"]
                        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "png")
                        new_filename = f"{name}_lora{weight}{ext if ext else '.png'}"
                        dest = str(save_dir / new_filename)
                        client.view_image(
                            img["filename"],
                            image_type=img.get("type", "output"),
                            subfolder=img.get("subfolder", ""),
                            save_to=dest,
                        )
                        if not fmt.json_mode:
                            click.echo(f"  Saved: {dest}")

            results.append({
                "weight": weight,
                "status": status.get("status_str", "?"),
                "images": sum(len(o.get("images", [])) for o in outputs.values()),
            })

            if not fmt.json_mode:
                click.echo()

        if fmt.json_mode:
            fmt.print(results)
        else:
            click.echo("LoRA weight sweep complete!")
            click.echo(format_table(results, columns=["weight", "status", "images"]))
    except Exception as e:
        _handle_error(fmt, e)


@generate.command("styles")
@click.pass_context
def generate_styles(ctx):
    """List available style presets for diverse generation."""
    fmt = _get_fmt(ctx)

    styles = get_style_list()
    style_details = []

    for style_name in styles:
        info = get_style_info(style_name)
        if info:
            style_details.append({
                "name": style_name,
                "lora_range": f"{info['lora_weight_range'][0]}-{info['lora_weight_range'][1]}",
                "keywords": info["keywords"][:60] + "..." if len(info["keywords"]) > 60 else info["keywords"],
            })

    if fmt.json_mode:
        fmt.print(style_details)
    else:
        click.echo(f"Available style presets ({len(styles)}):")
        click.echo()
        click.echo(format_table(
            style_details,
            columns=["name", "lora_range", "keywords"],
            max_width=120,
        ))
        click.echo()
        click.echo("Usage: comfyui-cli generate diverse <workflow.json> --style <name>")


# ============================================================
# config commands
# ============================================================

@cli.group()
def config():
    """Manage CLI configuration."""


@config.command("show")
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    fmt = _get_fmt(ctx)
    cfg = ctx.obj["config"]
    fmt.print(cfg, human_text=format_kv(cfg))


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx, key, value):
    """Set a configuration value."""
    fmt = _get_fmt(ctx)
    cfg = ctx.obj["config"]

    # Type coercion
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    else:
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass

    cfg[key] = value
    save_config(cfg)
    fmt.print({"key": key, "value": value}, human_text=f"Set {key} = {value}")


@config.command("reset")
@click.confirmation_option(prompt="Reset configuration to defaults?")
@click.pass_context
def config_reset(ctx):
    """Reset configuration to defaults."""
    from comfyui.utils.config import DEFAULT_CONFIG
    fmt = _get_fmt(ctx)
    save_config(dict(DEFAULT_CONFIG))
    fmt.print(DEFAULT_CONFIG, human_text="Configuration reset to defaults.")


# ============================================================
# REPL mode
# ============================================================

@cli.command("repl")
@click.pass_context
def repl_mode(ctx):
    """Start an interactive REPL session."""
    click.echo("comfyui-cli REPL - type 'help' for commands, 'exit' to quit")
    click.echo(f"Server: {ctx.obj['client'].base_url}")

    while True:
        try:
            line = click.prompt("comfyui", prompt_suffix="> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye!")
            break

        if not line:
            continue
        if line in ("exit", "quit", "q"):
            click.echo("Bye!")
            break
        if line == "help":
            click.echo("Available commands:")
            click.echo("  system stats    - Show system info")
            click.echo("  system ping     - Check server")
            click.echo("  system interrupt - Interrupt execution")
            click.echo("  system free     - Free memory")
            click.echo("  system paths    - Show folder paths")
            click.echo("  system logs     - View server logs")
            click.echo("  queue status    - Queue status")
            click.echo("  models list [type] - List models")
            click.echo("  models types    - Model types")
            click.echo("  nodes search <q> - Search nodes")
            click.echo("  nodes samplers  - List samplers & schedulers")
            click.echo("  nodes categories - List node categories")
            click.echo("  images list     - List output files")
            click.echo("  history list    - Recent history")
            click.echo("  exit/quit       - Exit REPL")
            continue

        # Parse and dispatch
        parts = line.split()
        try:
            cli.main(args=parts, standalone_mode=False, obj=ctx.obj)
        except SystemExit:
            pass
        except click.exceptions.UsageError as e:
            click.echo(f"Usage error: {e}")
        except Exception as e:
            click.echo(f"Error: {e}")


def main():
    """Entry point for the CLI."""
    cli(auto_envvar_prefix="COMFYUI_CLI")


if __name__ == "__main__":
    main()
