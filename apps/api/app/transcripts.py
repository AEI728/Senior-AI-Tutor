"""Small, explicit catalog homophone corrections; never remap missing skills."""

import re


def normalize_transcript(text):
    corrections = []
    for heard, correct in [
        ("元艺", "园艺"),
        ("元忆", "园艺"),
        ("园忆", "园艺"),
        ("园意", "园艺"),
        ("园益", "园艺"),
    ]:
        if heard in text:
            text = text.replace(heard, correct)
            corrections.append({"heard": heard, "catalog_term": correct})
    # Repeated identical utterances remain one request; preserve different clauses/corrections.
    sentences = re.findall(r"[^。！？]+[。！？]?", text)
    unique: list[str] = []
    for sentence in sentences:
        if not unique or sentence != unique[-1]:
            unique.append(sentence)
    return "".join(unique).strip(), corrections
