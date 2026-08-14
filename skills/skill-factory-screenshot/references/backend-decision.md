# 截图后端选择决策树

```
需要截图作为造技能输入
        │
        ├── 目标是"当前这台 Mac 的本机界面"？
        │        │
        │        ├── 是 ── 且 PATH 有 peekaboo + 已 TCC 授权？
        │        │            ├── 是 → 【后端 B: peekaboo】image / see --analyze
        │        │            └── 否 → 引导安装/授权；无法则退【后端 A】或纯文字
        │        │
        │        └── 否（是配对的手机/平板/另一台设备）
        │                     → 【后端 A: screen_snapshot tool】node=<配对节点>
        │
        └── 只需要一张静态图？ → snapshot；需要一段过程？ → record（受 300s 上限）
```

## 两条后端能力对比

| 维度 | 后端 A（nodes tool） | 后端 B（peekaboo skill） |
|------|----------------------|--------------------------|
| 平台 | iOS/Android/macOS companion 节点 | 仅 macOS 本机 |
| 调用 | 内置 tool `screen_snapshot`/`screen_record` | CLI `peekaboo image`/`see` |
| 授权 | `phone-control` arm/disarm + node-command-policy | macOS TCC + bridge.sock |
| 附加能力 | 录屏、摄像头、相册 | UI 元素定位、点击、`--analyze` 截图即分析 |
| 返回 | base64 → image content | 文件路径（+ 可选 analyze 文本） |
| eligibility | 需存在在线配对节点 | `os:darwin` + `requires.bins:[peekaboo]` |

## 选择原则

1. **优先复用内置能力**：后端 A 无需额外安装，跨端统一，是默认首选。
2. **本机 UI 深度理解选 B**：peekaboo 的 `see --annotate` 能给出可点击元素地图，`--analyze` 能截图即分析，适合"照着现有工具造 skill"。
3. **两者都不可用**：不要硬造截图能力；退回纯文字需求，直接进 `skill-generator`。截图是可选增强，不是造技能的硬前提。
