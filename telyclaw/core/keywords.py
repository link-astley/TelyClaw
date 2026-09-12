"""关键词抽取

针对 X 科技圈以英文为主的现实，用规则抽取：
- #话题标签 作为强信号
- 全大写缩写保留（AI / LLM / MCP / RAG / API ...）
- 去停用词后的实词，以及相邻两词组合（bigram）
"""

import re
from collections import Counter

STOPWORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any", "are", "as", "at",
    "back", "be", "because", "been", "before", "being", "best", "both", "but", "by", "can",
    "come", "could", "day", "do", "does", "doing", "done", "down", "each", "else", "even",
    "every", "for", "from", "get", "go", "going", "good", "got", "had", "has", "have", "he",
    "her", "here", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "know", "like", "made", "make", "many", "me", "more", "most", "much", "my", "need", "new",
    "no", "not", "now", "of", "off", "on", "one", "only", "or", "other", "our", "out", "over",
    "own", "part", "people", "really", "right", "said", "same", "see", "she", "should", "so",
    "some", "still", "stop", "take", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "thing", "things", "think", "this", "those", "time", "to", "too", "up",
    "us", "use", "used", "using", "very", "want", "was", "way", "we", "well", "went", "were",
    "what", "when", "where", "which", "while", "who", "why", "will", "with", "would", "you",
    "your", "youre", "im", "ive", "dont", "doesnt", "isnt", "thats", "wasnt", "cant", "wont",
    "s", "t", "m", "re", "ll", "ve", "d", "https", "http", "com", "www", "amp", "rt",
}

TOKEN_RE = re.compile(r"#(\w+)|@(\w+)|[A-Za-z][A-Za-z'\-]*|\d+")
ACRONYM_RE = re.compile(r"^[A-Z]{2,}$")

# 大写字缩写白名单（防止被当成普通词忽略）
ACRONYM_KEEP = {
    "ai", "llm", "llms", "mcp", "rag", "api", "apis", "gpu", "gpus", "cli", "ui", "ux",
    "mvp", "arr", "mrr", "saas", "dev", "devs", "ci", "cd", "usb", "oss", "sql", "js", "ts",
}


def tokenize(text: str) -> list:
    """切成小写词元；全大写缩写保持原样标记"""
    out = []
    for m in TOKEN_RE.finditer(text or ""):
        if m.group(1):          # hashtag
            out.append(("#" + m.group(1).lower(), "tag"))
        elif m.group(2):        # @mention，跳过
            continue
        else:
            w = m.group(0)
            if ACRONYM_RE.match(w):
                out.append((w.lower(), "acronym"))
            else:
                out.append((w.lower().strip("'-"), "word"))
    return out


def extract_tags(text: str) -> set:
    """从一条帖子里抽出候选标签"""
    toks = tokenize(text)
    tags = set()

    words = []
    for w, kind in toks:
        if kind == "tag":
            tags.add(w)                                   # #AIcoding -> "#aicoding"
        elif kind == "acronym":
            tags.add(w)
            words.append(w)
        else:
            if w in STOPWORDS or len(w) < 3:
                words.append("")                          # 占位，保证 bigram 位置正确
                continue
            if w in ACRONYM_KEEP:
                tags.add(w)
            tags.add(w)
            words.append(w)

    # 相邻两词组合（跳过被停用词打断的位置）
    for a, b in zip(words, words[1:]):
        if a and b and a != b:
            tags.add(f"{a} {b}")

    return {t for t in tags if t and len(t) > 1}
