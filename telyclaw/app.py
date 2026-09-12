"""TelyClaw 服务入口

启动：  python app.py
然后浏览器打开终端里打印的地址
"""

import json
import sys
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import DATA_DIR, WINDOWS, Settings                      # noqa: E402
from core.pipeline import get_source, run_scan, WINDOW_LABEL        # noqa: E402
from store import json_store as store                               # noqa: E402
from ai.client import AIError                                       # noqa: E402
from ai import tasks                                                # noqa: E402

app = FastAPI(title="TelyClaw")

# 最近一次检测的结果（内存 + 本地文件双写，重启后仍在）
LAST_RUN: dict = {}


# ------------------------------------------------------------------ 初始化
def ensure_accounts():
    """首次启动写入默认账号；种子里新增的账号只做补充，不删用户已删的"""
    try:
        src = get_source("mock")
        accs = src.all_accounts()
    except Exception:
        accs = []

    stored = store.load_accounts()
    known = {a["handle"].lower() for a in stored}
    added = False
    for a in accs:
        if a["handle"].lower() in known:
            continue
        stored.append({
            "handle": a["handle"],
            "display_name": a.get("display_name", a["handle"]),
            "followers": a.get("followers", 10000),
            "enabled": True,
            "note": a.get("note", ""),
            "added_at": store.now_iso(),
        })
        added = True
    if added:
        store.save_accounts(stored)


ensure_accounts()
_state = store.load_state()
if _state:
    LAST_RUN = _state


# ------------------------------------------------------------------ 请求模型
class AccountIn(BaseModel):
    handle: str
    display_name: str = ""
    followers: int = 10000


class ScanIn(BaseModel):
    handles: list = []
    window: str = "24h"
    use_ai: bool = True


class ImportIn(BaseModel):
    raw: str = ""


class AngleIn(BaseModel):
    topic_id: str


class DraftIn(BaseModel):
    topic_id: str
    angle_id: str
    angle_title: str = ""
    style: str = ""
    content: str = ""


class PublishIn(BaseModel):
    draft_id: str


# ------------------------------------------------------------------ 页面
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


# ------------------------------------------------------------------ 账号
@app.get("/api/accounts")
def list_accounts():
    from core.models import Account
    return [Account(**a).to_dict() for a in store.load_accounts()]


@app.post("/api/accounts")
def add_account(body: AccountIn):
    handle = store.normalize_handle(body.handle)
    if not handle:
        raise HTTPException(400, "账号名不能为空")
    accs = store.load_accounts()
    if any(a["handle"].lower() == handle.lower() for a in accs):
        raise HTTPException(400, f"@{handle} 已经在列表里了")
    accs.append({
        "handle": handle,
        "display_name": body.display_name or handle,
        "followers": body.followers,
        "enabled": True,
        "note": "",
        "added_at": store.now_iso(),
    })
    store.save_accounts(accs)
    return {"ok": True, "handle": handle}


@app.delete("/api/accounts/{handle}")
def delete_account(handle: str):
    accs = [a for a in store.load_accounts() if a["handle"].lower() != handle.lower()]
    store.save_accounts(accs)
    return {"ok": True}


@app.post("/api/accounts/{handle}/toggle")
def toggle_account(handle: str):
    accs = store.load_accounts()
    for a in accs:
        if a["handle"].lower() == handle.lower():
            a["enabled"] = not a.get("enabled", True)
    store.save_accounts(accs)
    return {"ok": True}


# ------------------------------------------------------------------ 设置
@app.get("/api/settings")
def get_settings():
    s = Settings.load()
    safe = dict(s)
    safe["has_key"] = bool((s.get("deepseek_api_key") or "").strip())
    safe["deepseek_api_key"] = ("已填写" if safe["has_key"] else "")
    return safe


@app.put("/api/settings")
def put_settings(body: dict):
    if "deepseek_api_key" in body and not (body.get("deepseek_api_key") or "").strip():
        body.pop("deepseek_api_key")
    cur = Settings.save(body or {})
    cur["has_key"] = bool((cur.get("deepseek_api_key") or "").strip())
    cur["deepseek_api_key"] = ("已填写" if cur["has_key"] else "")
    return cur


# ------------------------------------------------------------------ 检测
@app.post("/api/scan")
def scan(body: ScanIn):
    global LAST_RUN
    handles = [store.normalize_handle(h) for h in (body.handles or [])]
    handles = [h for h in handles if h]
    if not handles:
        return {"ok": False, "notice": "先勾选至少一个要监测的账号"}

    s = Settings.load()
    res = run_scan(
        handles=handles,
        window=body.window,
        source_name=None,
        seed=s.get("mock_seed", 0),
        paste_raw=s.get("paste_raw", ""),
        use_ai=body.use_ai,
    )
    LAST_RUN = res
    store.save_state(res)
    return res


@app.get("/api/last_run")
def last_run():
    return LAST_RUN or store.load_state() or {}


@app.post("/api/reseed")
def reseed():
    """换一批模拟数据"""
    s = Settings.load()
    seed = int(s.get("mock_seed", 0)) + 1
    Settings.save({"mock_seed": seed})
    return {"ok": True, "mock_seed": seed}


# ------------------------------------------------------------------ 粘贴导入
@app.post("/api/import")
def import_posts(body: ImportIn):
    from sources.paste_source import PasteSource
    try:
        posts = PasteSource(body.raw).parse()
    except Exception as e:
        return {"ok": False, "notice": f"内容没看懂：{e}"}
    if not posts:
        return {"ok": False, "notice": "没有解析出任何帖子，检查一下格式"}
    Settings.save({"paste_raw": body.raw, "source": "paste"})
    authors = sorted({p.author_handle for p in posts})
    return {
        "ok": True,
        "count": len(posts),
        "authors": authors,
        "preview": [p.to_dict() for p in posts[:8]],
    }


# ------------------------------------------------------------------ 内容角度
def _ctx(topic_id: str):
    """从最近一次检测结果里取出话题与代表帖子"""
    run = LAST_RUN or store.load_state() or {}
    topic = next((t for t in run.get("topics", []) if t.get("id") == topic_id), None)
    if not topic:
        return None, [], run
    raw_posts = run.get("posts_by_topic", {}).get(topic_id, [])
    from core.models import Post
    posts = []
    for p in raw_posts:
        posts.append(Post(
            id=p.get("id", ""), author_handle=p.get("author_handle", ""),
            author_name=p.get("author_name", ""), text=p.get("text", ""),
            created_at=p.get("created_at", ""), likes=p.get("likes", 0),
            retweets=p.get("retweets", 0), replies=p.get("replies", 0),
            quotes=p.get("quotes", 0),
        ))
    return topic, posts, run


@app.post("/api/angles")
def angles(body: AngleIn):
    s = Settings.load()
    api_key = (s.get("deepseek_api_key") or "").strip()
    if not api_key:
        return {"ok": False, "error": AIError("no_key").to_dict()}

    topic, posts, _ = _ctx(body.topic_id)
    if not topic:
        return {"ok": False, "error": {"code": "unknown", "message": "找不到这个热点，请重新检测一次",
                                       "retryable": False, "detail": ""}}

    from core.models import Topic
    t = Topic(**{k: v for k, v in topic.items() if k in Topic.__dataclass_fields__})
    try:
        angles = tasks.gen_angles(t, posts, s.get("positioning", ""), api_key)
    except AIError as e:
        return {"ok": False, "error": e.to_dict()}
    except Exception as e:
        return {"ok": False, "error": AIError("unknown", str(e)).to_dict()}
    return {"ok": True, "topic_id": body.topic_id, "angles": angles}


# ------------------------------------------------------------------ 写稿
@app.post("/api/drafts/generate")
def generate_drafts(body: DraftIn):
    """根据选中的角度生成 3 条不同风格的帖子，存为草稿"""
    s = Settings.load()
    api_key = (s.get("deepseek_api_key") or "").strip()
    if not api_key:
        return {"ok": False, "error": AIError("no_key").to_dict()}

    topic, posts, _ = _ctx(body.topic_id)
    if not topic:
        return {"ok": False, "error": {"code": "unknown", "message": "找不到这个热点，请重新检测一次",
                                       "retryable": False, "detail": ""}}
    try:
        from core.models import Topic
        t = Topic(**{k: v for k, v in topic.items() if k in Topic.__dataclass_fields__})
        variants = tasks.gen_posts(t, {
            "title": body.angle_title, "rationale": "", "hook": ""
        }, posts, s.get("positioning", ""), api_key)
    except AIError as e:
        return {"ok": False, "error": e.to_dict()}
    except Exception as e:
        return {"ok": False, "error": AIError("unknown", str(e)).to_dict()}

    saved = []
    for v in variants:
        draft = {
            "id": store.new_id("d"),
            "topic_id": body.topic_id,
            "topic_label": topic.get("label", ""),
            "angle_id": body.angle_id,
            "angle_title": body.angle_title,
            "style": v.get("style", ""),
            "content": v.get("content", ""),
            "edited": False,
            "status": "draft",
            "created_at": store.now_iso(),
            "published_at": "",
        }
        store.upsert_record(draft)
        saved.append(draft)
    return {"ok": True, "drafts": saved}


@app.get("/api/drafts")
def list_drafts():
    return store.load_drafts()


@app.put("/api/drafts/{draft_id}")
def update_draft(draft_id: str, body: dict):
    drafts = store.load_drafts()
    item = next((d for d in drafts if d["id"] == draft_id), None)
    if not item:
        published = store.load_published()
        item = next((d for d in published if d["id"] == draft_id), None)
    if not item:
        raise HTTPException(404, "找不到这条草稿")
    if "content" in body:
        item["content"] = body["content"]
        item["edited"] = True
    store.upsert_record(item)
    return {"ok": True, "draft": item}


@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str):
    store.save_drafts([d for d in store.load_drafts() if d["id"] != draft_id])
    return {"ok": True}


# ------------------------------------------------------------------ 发布
class Publisher:
    """发布接口。当前只有模拟实现，接真实 X API 时新增一个 XApiPublisher 即可。"""

    def publish(self, item: dict) -> dict:
        # 真实接入时：POST /2/tweets  {"text": item["content"]}
        return {
            "ok": True,
            "published_at": store.now_iso(),
            "url": "https://x.com/compose/post",
            "mode": "mock",
        }


@app.post("/api/publish")
def publish(body: PublishIn):
    drafts = store.load_drafts()
    item = next((d for d in drafts if d["id"] == body.draft_id), None)
    if not item:
        published = store.load_published()
        item = next((d for d in published if d["id"] == body.draft_id), None)
        if item:
            return {"ok": True, "already": True, "record": item}
        raise HTTPException(404, "找不到这条草稿")

    res = Publisher().publish(item)
    item["status"] = "published"
    item["published_at"] = res["published_at"]
    store.upsert_record(item)
    return {"ok": True, "record": item, "publish": res}


@app.get("/api/published")
def list_published():
    return store.load_published()


@app.get("/api/window/{key}")
def window_info(key: str):
    return {"key": key, "hours": WINDOWS.get(key), "label": WINDOW_LABEL.get(key, key)}


# ------------------------------------------------------------------ 启动
def main():
    port = int(Settings.get("port", 8765))
    url = f"http://127.0.0.1:{port}"
    print("=" * 52)
    print("  TelyClaw 已启动")
    print(f"  请打开浏览器访问： {url}")
    print("  停止服务：在这个窗口按 Ctrl + C")
    print("=" * 52)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
