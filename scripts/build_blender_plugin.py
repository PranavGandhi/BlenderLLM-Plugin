"""Build the BlenderLLM-Plugin installable add-on ZIP."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PACKAGE = PROJECT_ROOT / "plugins" / "blenderllm_plugin" / "blenderllm_plugin"
CORE_PACKAGE = PROJECT_ROOT / "packages" / "blenderllm_plugin_core" / "blenderllm_plugin_core"
DIST_DIR = PROJECT_ROOT / "dist"


def add_tree(archive: zipfile.ZipFile, source_dir: Path, zip_prefix: Path) -> None:
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        archive.write(path, zip_prefix / path.relative_to(source_dir))


def build_zip(version: str) -> Path:
    if not PLUGIN_PACKAGE.is_dir():
        raise FileNotFoundError(f"Plugin package not found: {PLUGIN_PACKAGE}")
    if not CORE_PACKAGE.is_dir():
        raise FileNotFoundError(f"Core package not found: {CORE_PACKAGE}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / f"blenderllm_plugin-{version}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        add_tree(archive, PLUGIN_PACKAGE, Path("blenderllm_plugin"))
        archive.writestr("blenderllm_plugin/core/__init__.py", '"""Bundled BlenderLLM-Plugin core package."""\n')
        add_tree(archive, CORE_PACKAGE, Path("blenderllm_plugin") / "core" / "blenderllm_plugin_core")

    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package BlenderLLM-Plugin as a Blender add-on ZIP.")
    parser.add_argument("--version", default="0.9.0", help="Version suffix for the output ZIP.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(build_zip(args.version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
