# 截图授权与门控检查清单（Phase 0 强制执行）

> 本清单直接对应插件可行性调研的"第五点注意事项"，任何截图动作前必须逐项确认。

## 一、eligibility 只读判定（约束 1）

- [ ] 判定后端 B 是否可用：`[ "$(uname)" = "Darwin" ]` 且 `command -v peekaboo`
- [ ] 判定后端 A 是否可用：`openclaw nodes list` 至少有一个在线节点
- [ ] 若两者都不可用 → **不报错造截图**，改走纯文字需求进 skill-generator
- [ ] 判定过程 **只读**，不修改任何配置、不改 per-agent skills 白名单

## 二、授权 arm（约束 3，仅后端 A 的高风险命令）

高风险命令：`camera.snap` / `camera.clip` / `screen.record`（`ArmGroup: camera|screen|writes|all`）。

- [ ] 已获得用户**明确授权**后才 arm
- [ ] arm 带自动过期 TTL：`openclaw nodes arm --node <id> --group screen --ttl 10m`
- [ ] 截图完成后 disarm：`openclaw nodes disarm --node <id> --group screen`
- [ ] 不在未授权状态下静默调用任何屏幕/摄像头命令

## 三、TCC 授权（约束 3，仅后端 B / macOS）

- [ ] 设置 bridge socket：`export PEEKABOO_BRIDGE_SOCKET="$HOME/Library/Application Support/OpenClaw/bridge.sock"`
- [ ] `peekaboo bridge status --json` → `hostKind` 为 `gui`，socket 路径以 `OpenClaw/bridge.sock` 结尾
- [ ] `peekaboo permissions status --json` → Screen Recording + Accessibility 均已授权
- [ ] 缺授权时**引导用户在系统设置中开启**，不绕过、不使用 `--no-remote`（除非调用进程自有授权）

## 四、边界约束（约束 2 与约束 4）

- [ ] 本 skill 全程只用 Markdown 工作流 + 内置 tool/CLI，**无 TS 运行时代码**，不 import 核心 `src/**`
- [ ] 全程**不写治理注册表**（那是编排器收尾阶段的事）
- [ ] eligible（能不能截）与治理登记（用哪个版本造过）两个事实源严格分离

## 快速自检脚本（只读，不改状态）

```bash
echo "OS: $(uname)"
command -v peekaboo >/dev/null 2>&1 && echo "peekaboo: yes" || echo "peekaboo: no"
openclaw nodes list 2>/dev/null || echo "no nodes / openclaw not on PATH"
```
