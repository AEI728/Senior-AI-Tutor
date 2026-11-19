"""Build clearly labelled fictional sharing examples from user-provided reference assets."""
import json
import subprocess
from pathlib import Path
import imageio_ffmpeg

root = Path(__file__).resolve().parents[1]
out = root / "media/shares"
out.mkdir(exist_ok=True)
specs = [
    ("garden", "home-gardening", "repotting.jpg", "小林", "阳台绿植", "整理阳台绿植。"),
    ("writing", "calligraphy", "calligraphy.jpg", "阿琴", "写字练习", "练习钢笔字。"),
    ("light", "photography", "photography.jpg", "阿远", "晨光摄影", "记录清晨光线。"),
    ("music", "music", "music.jpg", "知音", "音乐练习", "今天的音乐练习。"),
]
items = []
for key, skill, image, author, title, description in specs:
    target = out / (key + ".mp4")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-loop", "1", "-i", str(root / "apps/web/public/images" / image), "-vf", "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,zoompan=z='min(zoom+0.0004,1.08)':d=150:s=540x960:fps=25", "-t", "6", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)], check=True)
    items.append({"id": "example-" + key, "skill_id": skill, "author": author, "title": title, "description": description, "media_file": key + ".mp4", "state": "APPROVED", "is_example": True, "is_mine": False, "video_available": True, "image_available": False, "created_at": "2026-11-18T00:00:00+00:00", "likes": 0})
(root / "data/community_examples.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Built", len(items), "labelled example videos")
