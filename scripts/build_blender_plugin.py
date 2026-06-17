"""Build the BlenderLLM-Plugin installable add-on ZIP."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PACKAGE = PROJECT_ROOT / "plugins"
CORE_PACKAGE = PROJECT_ROOT / "packages"
DIST_DIR = PROJECT_ROOT / "dist"
ENV_FILE = PROJECT_ROOT / ".env"


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def add_tree(archive: zipfile.ZipFile, source_dir: Path, zip_prefix: Path) -> None:
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.name == ".DS_Store":
            continue
        archive.write(path, zip_prefix / path.relative_to(source_dir))


def local_settings_source() -> str:
    values = parse_env_file(ENV_FILE)
    api_key = values.get("OPENAI_API_KEY", "")
    return (
        '"""Local settings generated from the project .env during packaging."""\n\n'
        "# This file is inside the Blender add-on zip. Do not commit real keys.\n"
        f"OPENAI_API_KEY = {api_key!r}\n"
    )


def build_zip(version: str) -> Path:
    if not PLUGIN_PACKAGE.is_dir():
        raise FileNotFoundError(f"Plugin package not found: {PLUGIN_PACKAGE}")
    if not CORE_PACKAGE.is_dir():
        raise FileNotFoundError(f"Core package not found: {CORE_PACKAGE}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / f"blenderllm_plugin-{version}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        add_tree(archive, PLUGIN_PACKAGE, Path("blenderllm_plugin"))
        archive.writestr("blenderllm_plugin/local_settings.py", local_settings_source())
        archive.writestr("blenderllm_plugin/core/__init__.py", '\"\"\"Bundled BlenderLLM-Plugin core package.\"\"\"\n')
        add_tree(archive, CORE_PACKAGE, Path("blenderllm_plugin") / "core" / "blenderllm_plugin_core")

    if not ENV_FILE.is_file():
        print("Warning: .env not found. Packaged add-on will not include an OpenAI API key.")
    elif not parse_env_file(ENV_FILE).get("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY is empty in .env. Packaged add-on will not include a key.")

    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package BlenderLLM-Plugin as a Blender add-on ZIP.")
    parser.add_argument("--version", default="1.0.0", help="Version suffix for the output ZIP.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(build_zip(args.version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
