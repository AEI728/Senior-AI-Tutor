"""Bounded local lexical retrieval. Only selected course directories are read."""

import re
from pathlib import Path
from .config import settings, ROOT


def retrieve(course_id, query):
    configured = settings().knowledge_base_path
    folder = Path(configured) if configured else ROOT / "data/knowledge"
    if not folder.is_absolute():
        folder = ROOT / folder
    folder = folder.resolve()
    if not folder.is_dir():
        folder = ROOT / "data/knowledge"
    course = (folder / course_id).resolve()
    if not course.is_relative_to(folder) or not course.is_dir():
        return []
    terms = set(re.findall(r"[\u4e00-\u9fff]{2}|[A-Za-z]{2,}", query))
    passages = []
    for path in sorted(course.rglob("*"))[:100]:
        if (
            path.suffix.lower() not in (".md", ".txt")
            or not path.resolve().is_relative_to(course)
            or path.stat().st_size > 100000
        ):
            continue
        for chunk in path.read_text("utf-8").split("\n\n")[:100]:
            score = sum(t in chunk for t in terms)
            if score:
                passages.append(
                    {"source": path.relative_to(folder).as_posix(), "text": chunk[:1200], "score": score}
                )
    return sorted(passages, key=lambda p: p["score"], reverse=True)[: settings().rag_top_k]
