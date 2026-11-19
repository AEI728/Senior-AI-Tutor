---
name: course-recommendation
description: 用户主动询问学什么或推荐课程时，从真实可访问课程中排序最多两个选择；不用于首页社区作品推荐。
metadata:
  version: "1.1.0"
---

# Skill 02 · 课程推荐

## 触发与边界
仅处理 RECOMMEND_COURSE。明确开课、浏览课程不触发；首页“今日推荐”仍是别人分享的社区作品。
这是规则实现的只读 Skill，不为排序额外调用模型，不写学习库、进度或发布内容。

## 输入与输出
输入：当前用户、真实 Course/Library/Progress、已解析技能、用户明确的条件。
输出：recommendations（最多两个，包含 course_id、skill_id、title、score、reason_codes、reason_text）、source_count、missing_conditions。
score 是规则排序分数，不是模型置信度。理由必须来自实际字段，不保证效果。

## 筛选和排序
生产环境只使用审核通过课程；本地/测试允许现有测试课程，与目录接口一致。
先过滤明确技能；用户要求“简单/入门”时必须有 difficulty=beginner；明确分钟上限必须有真实 duration_seconds 且满足上限。
缺少这些元数据时返回 missing_conditions，说明无法核对，不编造“8分钟”“适合入门”等信息，也不忽略硬约束强推。
按明确兴趣、真实学习进度、已加入技能加权；分数相同用课程 ID 稳定排序。权重和数量上限在 [运行策略](references/policy.json)。
没有匹配项返回空列表，不产生业务操作。给出候选不意味着用户已选择。
用户随后明确说“打开第一门/打开某真实标题”时，由会话中的真实候选绑定，再交给操作执行校验。

## 评测
检查课程可访问、条件满足、最多两项、理由来自真实记录、空候选不虚构，以及推荐本身不增加学习库。
