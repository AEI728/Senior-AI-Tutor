from app.transcripts import normalize_transcript


def test_explicit_homophones_and_duplicate_utterance():
    text, corrections = normalize_transcript("把元艺加入技能库。把元艺加入技能库。")
    assert text == "把园艺加入技能库。" and corrections


def test_does_not_substitute_unavailable_skill_or_remove_correction():
    assert normalize_transcript("我想学认字。不是书法。")[0] == "我想学认字。不是书法。"
