#!/usr/bin/env python3
"""Compile fuz.proto into fuz_pb2.py, rebuilding only when the proto is newer."""

import sys
import subprocess
from pathlib import Path

PROTO_DIR = Path(__file__).parent
PROTO_FILE = PROTO_DIR / "fuz.proto"
OUTPUT_FILE = PROTO_DIR / "fuz_pb2.py"

INSTALL_HINT = """protoc (Protocol Buffers compiler) is required:
  Ubuntu/Debian: sudo apt install protobuf-compiler
  macOS:         brew install protobuf
  Other:         https://github.com/protocolbuffers/protobuf/releases"""


def _protoc_available() -> bool:
    try:
        return subprocess.run(
            ["protoc", "--version"], capture_output=True, check=False
        ).returncode == 0
    except FileNotFoundError:
        return False


def build_proto() -> bool:
    if not PROTO_FILE.exists():
        print(f"ERROR: {PROTO_FILE} not found", file=sys.stderr)
        return False

    if not _protoc_available():
        print(INSTALL_HINT, file=sys.stderr)
        return False

    print(f"Building {OUTPUT_FILE.name} from {PROTO_FILE.name}...")
    try:
        subprocess.run(
            ["protoc", f"--proto_path={PROTO_DIR}", "--python_out", str(PROTO_DIR), PROTO_FILE.name],
            capture_output=True, text=True, check=True, cwd=PROTO_DIR,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: protoc failed\n{e.stderr}", file=sys.stderr)
        return False


def ensure_proto_built() -> bool:
    """Build fuz_pb2.py if it is missing or older than fuz.proto."""
    if OUTPUT_FILE.exists() and OUTPUT_FILE.stat().st_mtime >= PROTO_FILE.stat().st_mtime:
        return True
    return build_proto()


if __name__ == "__main__":
    sys.exit(0 if build_proto() else 1)
