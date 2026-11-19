"""Fictional, labelled built-in sharing content; never attributed to real users."""

import json
from functools import lru_cache
from fastapi import HTTPException
from .config import ROOT


@lru_cache
def example_items():
    path = ROOT / "data/community_examples.json"
    return json.loads(path.read_text("utf-8")) if path.is_file() else []


def get_example(eid):
    item = next((item for item in example_items() if item["id"] == eid), None)
    if item is None:
        raise HTTPException(404, "EXAMPLE_NOT_FOUND")
    return item


def example_video(eid):
    item = get_example(eid)
    folder = (ROOT / "media/shares").resolve()
    path = (folder / item["media_file"]).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise HTTPException(404, "VIDEO_NOT_FOUND")
    return path
