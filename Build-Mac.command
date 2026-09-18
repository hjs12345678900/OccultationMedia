#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 build_tools/create_macos_env.py
