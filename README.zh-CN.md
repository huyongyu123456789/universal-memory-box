# Memory Box（记忆盒子）

**本地优先、SQLite 驱动、跨 AI Agent 与网页 AI 的长期记忆盒。**

Memory Box 把聊天中的关键上下文保存到你自己的电脑，并通过 MCP / CLI / 本地 REST 接口提供给不同 AI Agent。目标是让你只说一句“把这段保存下来”，以后换 Agent、换会话、换项目时仍可调出并继续。



## v0.13：真正的 Windows 桌面程序壳

v0.13 把 v0.12 的控制中心装进原生 Windows 窗口：正常打开不再需要浏览器地址，也不会弹黑色命令行窗口。桌面壳使用 pywebview/WebView2，系统托盘使用 pystray；Memory Box 的数据库、MCP、百度网盘 E2EE、保险和恢复逻辑仍然是原来的本地后端，因此这不是另一套静态桌面样机。

默认关闭/最小化主窗口时可继续留在系统托盘；托盘菜单提供“打开 Memory Box / 立即同步 / 立即保险 / 退出”。设置页在桌面模式下新增“最小化到托盘 / Windows 登录后启动 / 系统通知”。Windows Release 会同时生成 `MemoryBox.exe`（无控制台桌面程序）和 `MemoryBox-CLI.exe`（MCP/导入/恢复命令），保证普通用户不看到黑框，同时不破坏 Agent 的 stdio MCP。支持把 `.mboxpack` / `.mboxenc` 拖进桌面窗口导入；`.mbxrecovery` 仍使用独立本地恢复助手输入恢复码，避免恢复码进入 AI/JS bridge。详见 `docs/DESKTOP.md`。

## v0.12：桌面控制中心 + 简洁苹果风格界面

v0.12 把原来偏工程工具的本地 Web UI 重构成桌面控制中心：新增首页健康概览、全局记忆搜索、最近记忆、快捷恢复、E2EE 同步概览，并统一重做记忆、Agent、同步、自动保险、灾难恢复和迁移页面。视觉采用苹果系统常见的克制设计语言——大留白、轻毛玻璃、圆角、薄分隔线、低阴影和单一强调色，但不复制苹果官方界面。

界面支持 **浅色 / 深色 / 跟随系统**，桌面端使用侧边栏，窄屏自动折叠，移动宽度切换为底部导航。全部 UI 仍直接调用现有 Memory Box 本地 API，不是静态样机；默认网络边界仍是 `127.0.0.1`。详见 `docs/UI.md`。

## v0.11：自动保险 + 灾难恢复自检

Memory Box 现在可以按周期把**整个记忆库、历史版本、元数据和全部托管附件**生成完整快照，并在离开本机之前进行 E2EE 加密，然后写入百度网盘、OneDrive、NAS 或其他同步目录。

本地界面新增“自动保险”页面，提供 **GREEN / YELLOW / RED** 灾难恢复状态：检查 SQLite 完整性、附件是否缺失、E2EE 保险快照是否存在/过期、`.mbxrecovery` 是否有异地副本，以及恢复码自检是否做过。

恢复码自检只在本机进行，不会暴露给 MCP 或 AI Agent。Windows 可选运行 `Enable-Auto-Insurance.cmd` 创建每小时唤醒一次的计划任务；真正是否需要备份仍由你设定的 24h/48h 等保险周期决定，安装时不会静默创建计划任务。详见 `docs/INSURANCE.md`。


## 现在能做什么

- 一键保存聊天：标题可自动生成，分类可自动判断
- 记忆列表：稳定 ID（`M000001`）+ 分类 + 标签 + 更新时间
- 分类：科研、论文、编程、数据分析、教学、项目、旅行、个人、其他
- 搜索：SQLite FTS5（不可用时自动退回 LIKE 搜索）
- 置顶 / 收藏 / 归档
- 追加记忆并保留版本快照
- 查找相关记忆
- 合并多条记忆
- “把与某项目有关的记忆都调出来”并自动组合成 Resume Context
- 从 Universal Agent Memory v0.3 的 JSON vault 导入
- MCP Server：Agent 可直接调用保存、列表、打开、追加、恢复、合并等工具
- Browser Bridge v0.13：ChatGPT/Kimi/Claude/Gemini/DeepSeek/豆包/元宝网页端可选中保存、保存当前聊天、选择本地附件、搜索旧记忆并把 Resume Context 填回当前聊天输入框
- 完整会话胶囊：PDF、Word、图片、CSV、代码、日志等附件与记忆一起打包迁移
- 附件去重：按 SHA-256 内容寻址，同一文件被多条记忆引用时只存一份
- 网页来源追溯：保存 `source_agent + source_uri`，旧数据库自动迁移到 schema v8

## Windows 最简单安装

1. 下载并解压发行包。
2. 双击 `Install-MemoryBox.cmd`。安装器会初始化本地数据库，并询问是否立即关联检测到的本地 Agent。
3. 首次安装会下载一个私有 Python 运行时到 `%LOCALAPPDATA%\MemoryBox\runtime`，不污染系统 Python。
4. 安装完成后自动打开 Memory Box。本地数据库默认位于 `%LOCALAPPDATA%\MemoryBox\memorybox.db`。
5. **首次打开会自动扫描并关联检测到的本地 MCP Agent**；结果写入本地 `autolink.json`，以后不会反复修改。设置环境变量 `MEMORYBOX_NO_AUTOLINK=1` 可关闭自动关联。
6. 之后可从开始菜单直接打开 **Memory Box**。

> 源码桌面版可运行：`python memorybox_main.py desktop`；只需要浏览器模式时仍可运行 `python memorybox_main.py app`。

## 在聊天里怎么用

只要 Agent 已连接 Memory Box MCP：

- `把刚才这段对话保存到记忆盒子。`
- `打开记忆盒子，列出我的记忆。`
- `打开论文分类。`
- `打开 M000007。`
- `把刚才的新内容追加到 M000007。`
- `恢复 M000007，继续上次任务。`
- `把和 CRAB 项目有关的记忆全部调出来，然后继续。`

Agent 会调用对应 MCP 工具，不需要你自己写 JSON 或执行命令。




## v0.10：密钥保险箱 + 灾难恢复

Memory Box 现在可以为本机 X25519 设备身份生成一个加密的 `*.mbxrecovery` 恢复保险箱，同时随机生成一次性显示的 `MBR1-...` 恢复码。恢复文件使用 **scrypt + AES-256-GCM** 保护设备私钥；恢复码不会写入 SQLite、记忆正文、MCP、百度网盘同步元数据或恢复文件本身。

推荐做法：把 `.mbxrecovery` 放到百度网盘/OneDrive/NAS 或离线 U 盘，把恢复码打印或抄写在另一个位置。两者不要放在同一个云目录。

如果旧电脑损坏，在新电脑安装 Memory Box 后进入 **安全/恢复 → 恢复旧电脑身份**，选择恢复文件并在本机输入恢复码。成功后会恢复原设备 ID 和加密身份，旧 `.mboxenc` 历史密文可以重新解开。

恢复码属于总钥匙，**不要贴进 ChatGPT、Kimi、WorkBuddy、Codex 或任何 AI 聊天框**。Memory Box 故意不把创建/恢复私钥的能力暴露为 MCP 工具。详见 `docs/RECOVERY.md`。

## v0.9：端到端加密设备同步 + 百度网盘

新建的百度网盘、OneDrive、NAS、Syncthing 等同步端点默认使用 **E2EE**。Memory Box 在本机先生成普通 `.mboxpack`，随后只把 `.mboxenc` 密文写入同步目录；云盘或 NAS 看不到对话正文和附件内容。

加密方案：

- 每台 Memory Box 生成独立 **X25519** 设备密钥；私钥只保存在本机 `keys/device-x25519.json`。
- 设备之间使用 X25519 共享秘密 + **HKDF-SHA-256** 派生密钥包装密钥。
- 会话包正文使用随机 256-bit 内容密钥和 **AES-256-GCM** 认证加密。
- 云同步要求**双向可信设备**：A 必须信任 B 才会给 B 封装解密密钥；B 也必须信任 A 才会接受 A 的包。
- 首次信任前，在两台电脑上核对完整设备指纹。撤销信任后，未来新包不再为该设备封装解密密钥。
- v0.8 已存在的同步端点升级后保持 `legacy-plaintext`，避免静默破坏旧工作流；界面会提供“升级加密”。新端点默认 `e2ee`。
- 局域网直传也改为 E2EE，同时保留一次性 6 位配对码用于会话认证。

百度网盘模式仍然只使用你选择的**本地同步文件夹**，Memory Box 不需要百度账号密码、Cookie 或 Token：

```text
电脑 A Memory Box
  ↓ 生成 .mboxenc（本机完成加密）
百度网盘同步目录 / MemoryBoxSync / packages
  ↓ 百度网盘客户端只同步密文
电脑 B Memory Box
  ↓ 验证可信发送者 → 解密 → 校验 .mboxpack → 导入
恢复记忆 + 附件
```

第一次配置两台电脑时：

1. 两台电脑都配置同一个百度网盘同步目录。
2. 打开“设备同步 → 可信设备”，两边都能看到对方的设备 ID 和 X25519 指纹。
3. 对照两台屏幕上的完整指纹，确认一致后分别点击“核对后信任”。
4. 之后可直接说：`把 M000027 加密发到百度网盘同步盒。`
5. 另一台电脑可自动接收，或说：`检查百度网盘有没有新的加密记忆。`

> `.mboxpack` 是用户主动导出的可携带明文会话包；`.mboxenc` 是 v0.9 云/局域网同步使用的端到端加密封装。不要把这两种格式混为一谈。


## v0.7：完整会话胶囊 / 跨电脑复现

Memory Box 现在可以把**对话记忆 + 真实附件文件**一起导出为 `.mboxpack`。附件先复制到 Memory Box 自己的内容寻址仓库，以 SHA-256 去重，因此原电脑的 `C:\` / `F:\` 路径在另一台电脑不存在也不影响恢复。

迁移包内部包含：

```text
manifest.json       # 来源设备、版本、完整性校验
memories.json       # 对话记忆、分类、标签、来源、版本历史
resume.md           # 给 AI Agent 的跨设备恢复上下文
viewer.html         # 离线对话复现页
README.txt
attachments/
  index.json         # 附件名称/MIME/大小/记忆关联
  blobs/<sha256>     # PDF/Word/图片/代码等真实文件本体
```

在电脑 B 安装 Memory Box 后，直接双击 `.mboxpack`：**校验 → 导入记忆 → 恢复附件 → 处理 ID 冲突 → 生成目标电脑本地路径 → 打开复现页**。已有 v0.6 纯文字 `.mboxpack` 仍可导入。

如果电脑 A 与电脑 B 都有 `M000007`，不会覆盖。远端记忆会按需要重编号，附件关联会跟着映射后的新 ID 自动重建。同一个包重复导入不会重复创建记忆或附件。

使用本地 Agent/MCP 给记忆附加文件：

```bash
memorybox attach M000007 "F:\Project\paper.pdf" --note "关键文献"
memorybox attachments M000007
```

直接生成完整会话胶囊：

```bash
memorybox session-pack CRAB-Session.mboxpack M000007 M000012
```

也支持文件夹：

```bash
memorybox session-pack TransferFolder M000007 --folder
```

> `.mboxpack` v2 是纯数据格式，不执行包内代码。附件和元数据都会校验 SHA-256，且默认不导出原电脑绝对路径。当前版本未加密，敏感包仍应按私密文件处理。

## Browser Bridge v0.13：网页 AI + 附件

网页端继续支持“保存选中对话 / 保存当前聊天 / 搜索 / 恢复到当前输入框”，并新增**本地附件选择**。你可以在扩展中选 PDF、Word、图片、CSV、代码文件等，然后点击“保存当前聊天”，文件会挂在新建记忆下并进入同一个本地附件库。

由于浏览器和各 AI 网站的权限模型不同，扩展不会声称能自动下载每个平台服务器上的所有云端附件。可靠流程是：选择/下载你要保留的文件后，在 Browser Bridge 的附件选择框中一起保存。

安装：先启动 Memory Box，然后双击 `Install-Browser-Bridge.cmd`。脚本会打开扩展目录和 Chrome/Edge 扩展管理页；最后仍需由用户点击“加载已解压的扩展程序”。

## Agent 接入矩阵

| Agent | 本地自动/半自动接入 | 方式 |
|---|---:|---|
| Kimi Code / Kimi CLI | ✅ | MCP stdio；以官方 `~/.kimi-code/mcp.json` 为主；若检测到旧 `~/.kimi/mcp.json` 则兼容更新 |
| WorkBuddy | ✅ 连接器包 | `integrations/workbuddy/`，MCP + Skill |
| Cursor | ✅ | `~/.cursor/mcp.json` |
| Gemini CLI | ✅ | `~/.gemini/settings.json` |
| Claude Code | ✅（检测到 CLI 时） | `claude mcp add --scope user ...` |
| OpenAI Codex CLI | ✅/半自动 | `codex mcp add ...`；失败时给出手工命令 |
| Windsurf | ⚠️ | 提供通用 MCP stdio 配置；不同版本配置位置可能变化 |
| Tencent CodeBuddy | ✅（检测到 CLI 时） | `codebuddy mcp add --scope user ...` |
| Qoder / Qoder CN | ✅（检测到 CLI 时） | `qoder/qodercn mcp add ...` |
| TRAE / TraeWork | ⚠️ | 支持 MCP，但本地/云端配置取决于客户端形态 |
| ChatGPT Web/App | ✅ Browser Bridge / ⚠️ MCP | 网页端可通过 Browser Bridge 本地保存与恢复；直接 localhost MCP 仍受平台限制 |
| 其他 Agent | ✅ 通用 | 任何支持 MCP stdio 的客户端；否则用 CLI/REST/Skill |

在 Memory Box 页面点击 **AI Agent 连接 → 一键连接检测到的本地 Agent**，程序会扫描本机并写入已知安全配置。不会绕过平台权限，也不会在你没有点击连接时偷偷改 Agent 配置。

## WorkBuddy

项目内已经附带符合 WorkBuddy 连接器结构的：

```text
integrations/workbuddy/
├── connector-meta.json
├── mcp.json
├── icon.svg
└── skills/memory-box/SKILL.md
```

安装 Memory Box 到默认目录后，WorkBuddy 连接器通过：

```text
%LOCALAPPDATA%\MemoryBox\MemoryBox-MCP.cmd
```

连接本地 MCP Server。

## Kimi

同时附带 `integrations/kimi-plugin/`，用于 Kimi Code/Work 支持本地插件运行的环境。


Memory Box 同时兼容 Kimi Code 新旧配置目录。连接后 Kimi 可看到 `memory_save`、`memory_list`、`memory_get`、`memory_bundle` 等 MCP 工具。Kimi Web/Work 是否能直接连接本机进程取决于其客户端/插件运行环境；无法触达本机时，需要使用其支持的插件/远程 MCP 方式。

## 数据与隐私

Memory Box 默认完全本地：

```text
Windows: %LOCALAPPDATA%\MemoryBox\memorybox.db
macOS/Linux: ~/.memorybox/memorybox.db
```

SQLite 使用 WAL 模式。Memory Box 不要求云账号，不内置遥测，不上传记忆。公开 GitHub 仓库只放程序代码，不放你的数据库。

## MCP 工具

- `memory_save`
- `memory_list`
- `memory_get`
- `memory_append`
- `memory_categories`
- `memory_resume`
- `memory_related`
- `memory_bundle`
- `memory_merge`
- `memory_pin`
- `memory_favorite`
- `memory_export_pack`
- `memory_import_pack`
- `memory_inspect_pack`
- `memory_attach_file`
- `memory_list_attachments`
- `memory_detach_file`
- `memory_sync_add_folder`
- `memory_sync_endpoints`
- `memory_sync_detect`
- `memory_sync_send`
- `memory_sync_pull`
- `memory_sync_devices`
- `memory_lan_pair`
- `memory_lan_discover`
- `memory_lan_send_pack`

## 与 Universal Agent Memory Skill 的关系

`universal-agent-memory` 是开放 Skill/文件协议；**Memory Box 是独立本地程序**。两者可以并存：

- Skill 适合放进项目、被 Agent 直接读取。
- Memory Box 适合作为跨项目、跨 Agent 的全局记忆仓库。
- `memorybox import-uam ~/.uam` 可把旧 UAM v0.3 记忆迁入 SQLite。

## 开发

```bash
python -m unittest discover -s tests -v
python memorybox_main.py app
python memorybox_main.py mcp
```

MIT License。
