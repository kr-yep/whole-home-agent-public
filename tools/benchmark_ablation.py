"""Compatibility entry point for the measured local component benchmark.

The earlier scripted LLM control is preserved in Git history; it must not be
reported as a real model measurement. Run with --help for current options.
"""
from benchmark_local_components import main

if __name__ == "__main__":
    raise SystemExit(main())
