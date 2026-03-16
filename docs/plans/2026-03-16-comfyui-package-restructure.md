# comfyui-cli Package Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the `cli_anything/` wrapper and convert the project into a standard top-level `comfyui` Python package while preserving the `comfyui-cli` command.

**Architecture:** Move the source tree from `comfyui/` to `comfyui/`, update package discovery and entry points in `setup.py`, rewrite imports and documentation, then re-install the package and re-run the core test suite.

**Tech Stack:** Python, setuptools, Click, pytest

---

### Task 1: Write planning artifacts

**Files:**
- Create: `docs/plans/2026-03-16-comfyui-package-restructure-design.md`
- Create: `docs/plans/2026-03-16-comfyui-package-restructure.md`

**Step 1: Save approved design**

Write the approved target structure, migration scope, packaging decisions, and validation requirements.

**Step 2: Save implementation plan**

Document the migration tasks and exact validation commands.

**Step 3: Verify files exist**

Run: `Get-ChildItem docs/plans`
Expected: Both plan files are listed

### Task 2: Move source package

**Files:**
- Move: `comfyui/` -> `comfyui/`
- Delete: `cli_anything/` if empty

**Step 1: Move directory**

Move the entire package tree to the repository root under `comfyui/`.

**Step 2: Verify moved layout**

Run: `Get-ChildItem -Recurse comfyui`
Expected: `__init__.py`, `comfyui_cli.py`, `core/`, `utils/`, `tests/`

### Task 3: Update package configuration and imports

**Files:**
- Modify: `setup.py`
- Modify: all Python files under `comfyui/`

**Step 1: Update packaging**

- switch to `find_packages`
- change `long_description` to root `README.md`
- update console entry point to `comfyui.comfyui_cli:main`

**Step 2: Rewrite imports**

Replace `comfyui` imports with `comfyui`.

**Step 3: Verify no old import paths remain**

Run: `Get-ChildItem -Recurse -File | Select-String -Pattern 'cli_anything\\.comfyui|comfyui'`
Expected: No matches

### Task 4: Add top-level README and update docs

**Files:**
- Create: `README.md`
- Modify: `COMFYUI.md`
- Modify: `comfyui/README.md`
- Modify: `comfyui/tests/TEST.md`

**Step 1: Create repository homepage README**

Add a concise Chinese README for GitHub homepage with install, usage, commands, and structure.

**Step 2: Update internal doc paths**

Ensure project structure examples and test commands point to `comfyui/...`.

**Step 3: Verify documentation naming**

Run: `Get-ChildItem -Recurse -File | Select-String -Pattern 'comfyui'`
Expected: No matches

### Task 5: Reinstall and validate

**Files:**
- Test: `comfyui/tests/test_core.py`

**Step 1: Reinstall package**

Run: `python -m pip install -e .`
Expected: editable install succeeds for `comfyui-cli`

**Step 2: Verify command entry point**

Run: `comfyui-cli --version`
Expected: `comfyui-cli, version 0.1.0`

**Step 3: Run core tests**

Run: `pytest comfyui/tests/test_core.py -v`
Expected: test suite passes

### Task 6: Commit and push

**Files:**
- All modified tracked files

**Step 1: Review working tree**

Run: `git status --short`
Expected: only intended migration changes

**Step 2: Commit**

```bash
git add .
git commit -m "refactor: flatten package structure"
```

**Step 3: Push**

Run: `git push`
Expected: remote `main` updated
