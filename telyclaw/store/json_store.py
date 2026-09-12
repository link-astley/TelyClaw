"""本地 JSON 存储：账号 / 设置 / 草稿 / 发布记录 / 会话状态"""

import json
import re
import time
import uuid
from pathlib import Path

from config import DATA_DIR


def _read(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ------------------------------------------------------------------ 账号

ACCOUNTS_PATH = DATA_DIR / "accounts.json"


def load_accounts() -> list:
    return _read(ACCOUNTS_PATH, []) or []


def save_accounts(accounts: list):
    _write(ACCOUNTS_PATH, accounts)


def normalize_handle(raw: str) -> str:
    """把用户粘贴的各种形态统一成纯用户名"""
    h = (raw or "").strip()
    h = h.lstrip("@")
    h = re.sub(r"^https?://(www\.)?(x|twitter)\.com/", "", h)
    h = h.split("?")[0].strip("/")
    h = h.split("/")[0]
    return h


# ------------------------------------------------------------------ 草稿 / 已发布

DRAFTS_PATH = DATA_DIR / "drafts.json"
PUBLISHED_PATH = DATA_DIR / "published.json"


def load_drafts() -> list:
    return _read(DRAFTS_PATH, []) or []


def save_drafts(drafts: list):
    _write(DRAFTS_PATH, drafts)


def load_published() -> list:
    return _read(PUBLISHED_PATH, []) or []


def save_published(items: list):
    _write(PUBLISHED_PATH, items)


def upsert_record(item: dict):
    """草稿编辑后同步更新到对应列表"""
    if item.get("status") == "published":
        items = load_published()
        idx = next((i for i, x in enumerate(items) if x.get("id") == item["id"]), None)
        if idx is None:
            items.insert(0, item)
        else:
            items[idx] = item
        save_published(items)
        # 从草稿里移除
        drafts = [d for d in load_drafts() if d.get("id") != item["id"]]
        save_drafts(drafts)
    else:
        items = load_drafts()
        idx = next((i for i, x in enumerate(items) if x.get("id") == item["id"]), None)
        if idx is None:
            items.insert(0, item)
        else:
            items[idx] = item
        save_drafts(items)


# ------------------------------------------------------------------ 会话状态（最近一次检测结果）

STATE_PATH = DATA_DIR / "last_run.json"


def save_state(state: dict):
    _write(STATE_PATH, state)


def load_state() -> dict:
    return _read(STATE_PATH, {}) or {}
