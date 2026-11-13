#!/usr/bin/env bash
set -euxo pipefail

python -m pytest -v -p no:cacheprovider test_bootstrap_ssh_guards.py
