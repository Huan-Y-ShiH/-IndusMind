"""项目级路径与环境配置加载。"""
from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@functools.lru_cache(maxsize=1)
def _load_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


@functools.lru_cache(maxsize=1)
def load_paths() -> dict[str, str]:
    """读取 config/paths.yaml，返回 {key: 相对 repo 根目录的路径}。"""
    _load_env()
    with open(REPO_ROOT / "config" / "paths.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(key: str) -> Path:
    """把 paths.yaml 里的相对路径 key（如 'fmea_csv'）解析成绝对路径。"""
    paths = load_paths()
    if key not in paths:
        raise KeyError(f"config/paths.yaml 未定义路径 key: {key}")
    return REPO_ROOT / paths[key]


def env(name: str, default: str | None = None) -> str | None:
    _load_env()
    return os.environ.get(name, default)
