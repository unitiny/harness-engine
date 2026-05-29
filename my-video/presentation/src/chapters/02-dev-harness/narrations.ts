export const narrations = [
  "Dev Harness 管执行。一个 loop 转下来：写 task brief，干活，跑 gate，review，提交。一圈都有脚本盯着。",
  "双模型分工。高配模型当 architect，写 task、审 review。低配模型当 implementer，领 task 干活。一个管方向，一个管执行。token 省，质量不丢。",
  "gate 有十几个。scope_diff_gate 查你改的文件跟 task 对不对得上。dev_gate 跑整体质量。write_task_gate 连 task 本身写得合不合格都查。剩下的查 receipt、查 memory、查 epic 对齐，各有各的检查域。",
  "五层验收模型。从页面能不能打开，到 API 状态对不对，到控制台有没有报错，到元素在不在，到数据刷了还在不在。层层过关。",
  "task brief 里有 scope contract。能改哪些文件、验收标准、验证命令、停的条件。全写死。你领 task 的时候 scope 就锁了。干完交 receipt 回来。",
];
