"""One-time import from the user's supplied specification; no generated facts."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'docs/implementation.md').read_text('utf-8')
for block in re.findall(r'```json\s*\n(.*?)```', source, re.S):
    try:
        value = json.loads(block)
    except ValueError:
        continue
    if 'skill' in value and 'course' in value:
        # No licensed video asset was supplied. Use real text lessons; no broken player.
        value['course']['media_path'] = None
        folder = root / 'data/courses'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'repotting-basics.zh-CN.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')
        break
else:
    raise RuntimeError('Course fixture not found')

decisions = [
('源码与资产', '发现 9.1/src/main.jsx 与 styles.css；旧树有未提交修改。新建独立 xiaoban-r1 工程，旧HTML仅参考，不修改旧树。'),
('角色隔离', '全局小伴负责操作，练习路由完全卸载小伴，独立私教只处理课程。路由切换停止音频。'),
('风险与确认', '明确可撤销加入直接执行；公开发布、支付不存在；删除个人数据须输入完整确认短语。'),
('认证', '本地短期HS256开发令牌；外部部署必须OIDC校验。OIDC浏览器登录选型未完成，公开发布阻断。'),
('模型与语音', '保留规范模型配置，真实OpenAI Responses严格函数参数由本地执行。Mock醒目标识且无隐式降级。无凭证不能验收。'),
('教学与证据', '仅用户自述完成；不观察视频、不认证动作质量。课程草稿限内部测试。'),
('恢复与幂等', '业务变更与工具记录同事务，唯一键去重，导航ACK前只说正在打开。超时动作UNKNOWN。'),
('本地数据库预览', '本机未发现Docker。正式默认PostgreSQL；显式 DATABASE_URL=sqlite:///... 仅限local/test。SQLite结果不能当成PostgreSQL并发验收证据。'),
('工程差异与缺口', '课程步骤和FAQ暂存版本化JSON，未按规范拆成两张表；无视频资产故使用文字步骤。迁移0001当前依赖ORM元数据，后续正式发布应冻结显式DDL。R1完整门禁尚未通过，详见验收报告。')]
for n, (title, body) in enumerate(decisions, 1):
    (root / f'docs/decisions/ADR-{n:03d}.md').write_text(f'# ADR-{n:03d} {title}\n\n日期：2026-11-11\n\n{body}\n', 'utf-8')
