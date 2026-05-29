# Harness Engine 口播稿

你让 AI 写代码，然后呢？没人管，它就翻车。

---

改错文件。scope 扩散，动了不该动的东西。

---

"跑通了。"验证没跑，gate 没过，review 没有。它自己觉得行就行。

---

harness 就是给 AI 上工程纪律。scope 锁在 task brief，质量卡在 gate，结果交给 review。

---

Dev Harness 管执行。一个 loop 转下来：写 task brief，干活，跑 gate，review，提交。一圈都有脚本盯着。

---

双模型分工。高配模型当 architect，写 task、审 review。低配模型当 implementer，领 task 干活。一个管方向，一个管执行。token 省，质量不丢。

---

gate 有十几个。scope_diff_gate 查你改的文件跟 task 对不对得上。dev_gate 跑整体质量。write_task_gate 连 task 本身写得合不合格都查。剩下的查 receipt、查 memory、查 epic 对齐，各有各的检查域。

---

五层验收模型。从页面能不能打开，到 API 状态对不对，到控制台有没有报错，到元素在不在，到数据刷了还在不在。层层过关。

---

task brief 里有 scope contract。能改哪些文件、验收标准、验证命令、停的条件。全写死。你领 task 的时候 scope 就锁了。干完交 receipt 回来。

---

harness 自己写得好不好，谁来查？Meta Harness。它只看不动手。

---

读 dev harness 的产出物，找质量缺口。七步 pipeline，采集、分析、打包、分诊、提修复、回放、出报告。前四步找问题，后三步出方案。

---

找什么？四类问题。比如 token 浪费，同样的模板写了一遍又一遍没复用。再比如 AI 指引缺口，scope 写得含糊，验收条件也含糊。还有 review 不带 diff 就交了，BLOCKED 任务没人管。

---

关键机制是预测合约。每个提案都带承诺："改这条规则后 token 浪费率降到多少。"不是"建议改进"，是可量化预测。

---

回放验证。拿基线数据对比，真变好了才往上升。candidate，validated，active。没变好就隔离。它只提建议，不直接改 dev harness 的文件。

---

两层叠起来就是自进化闭环。dev harness 干活留痕迹。meta harness 读痕迹，找缺口，提修复。验证过了再写回 dev harness。

---

每次任务结束都回答一个问题：harness 哪没拦住？该加规则、加 checker、还是加 memory？规则要有 rationale，要写清楚为什么存在、什么时候不该用。

---

规则不能"听起来有道理"就上线。三级晋升，每升一级都要证据和回放。harness 改进 harness 自己。觉得有意思，去 GitHub 搜 harness-engine 看源码。
