"""Add two distinct short lessons per skill without rewriting existing courses."""
import json
from copy import deepcopy
from pathlib import Path

root = Path(__file__).resolve().parents[1]
specs = [
    ("home-gardening", "gardening-02-watering", "浇水判断", ["把花盆放在平稳托盘上，先看植物养护说明。", "轻触表层盆土。仍湿润时先不浇水；不同植物要求不同。", "按植物要求少量缓慢浇水，等余水流出后倒掉托盘积水。"], "盆土仍湿时不要反复加水。"),
    ("home-gardening", "gardening-03-leaves", "清洁叶片", ["准备柔软的湿布，拧去多余水分。", "一只手轻托光滑叶片，另一只手用布轻擦灰尘，不拉扯叶柄。", "检查是否遗漏。带绒毛的叶片不要照此湿擦，先查植物说明。"], "不使用洗洁精或酒精擦叶片。"),
    ("calligraphy", "calligraphy-02-vertical", "竖线练习", ["放好纸笔，坐稳，肩膀和手腕放松。", "从上向下轻轻画一条竖线，按舒适速度落笔。", "再画两条，比较方向和间距，不必反复描粗。"], "手腕疲劳时停下来休息。"),
    ("calligraphy", "calligraphy-03-grid", "方格排字", ["准备方格纸，先观察每格的边线和中心位置。", "在相邻格中各写一个简单的字，尽量给四周留出空隙。", "对比两个字的大小，再选一个格子慢慢重写。"], "不要长时间低头，感到疲劳就休息。"),
    ("photography", "photography-02-light", "顺光拍摄", ["选择安全位置的一件静物，不拍摄他人隐私。", "让光线从身后或侧后方照向物品，注意不要挡住光。", "保持站稳，拍一张，再稍微换个角度比较画面。"], "不直视强光，也不要站到道路或高处边缘拍照。"),
    ("photography", "photography-03-focus", "对焦拍摄", ["坐稳或站稳，双手拿稳手机，打开相机。", "轻点屏幕里的主体，等画面清晰后再按快门。", "放大查看照片，比较主体是否清楚，再试一次。"], "不要边走边拍，不将手机伸出危险边缘。"),
    ("music", "music-02-count", "四拍练习", ["坐稳，放松肩膀和双手。", "轻声数一二三四，每数一下，用一根手指轻点桌面。", "用同样的舒适速度重复两轮，中间可以停下来。"], "不需要用力敲击，保持舒适音量。"),
    ("music", "music-03-rest", "节奏停顿", ["坐稳，先轻声数一二三四。", "在一、二、三时各轻拍一下，数到四时不拍。", "慢慢重复两轮，试着让停顿和拍点一样均匀。"], "手指或手腕不适时停止练习。"),
]
template = json.loads((root / "data/courses/calligraphy-lines.zh-CN.json").read_text("utf-8"))["course"]
skills = {"home-gardening":"家庭园艺", "calligraphy":"书法入门", "photography":"手机摄影", "music":"节奏入门"}
for sid, cid, title, instructions, note in specs:
    course = deepcopy(template)
    course.update(id=cid, title=title, learning_goal=title, prerequisites=["准备好工具，保持环境平稳、安全。"])
    course["steps"] = [{"no":i+1, "title":["准备","练习","回看"][i], "instruction":instruction, "explanation":"", "safety_notes":[note], "completion_rule":"用户自述完成", "source_role":"platform_editor"} for i,instruction in enumerate(instructions)]
    course["faq"] = [{"step_no":1,"question":"一次没做好怎么办？","answer":"可以暂停，再按自己的速度试一次。","verified":False},{"step_no":2,"question":"需要注意什么？","answer":note,"verified":False}]
    data = {"skill":{"id":sid,"name":skills[sid],"category":sid}, "course":course}
    path = root / "data/courses" / (cid+".zh-CN.json")
    content = json.dumps(data, ensure_ascii=False, indent=2)+"\n"
    if path.exists() and path.read_text("utf-8") != content:
        raise SystemExit("Refusing to overwrite changed course: "+cid)
    path.write_text(content, "utf-8")
print("Added", len(specs), "new lessons")
