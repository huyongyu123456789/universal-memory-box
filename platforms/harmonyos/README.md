# Memory Box for HarmonyOS 0.14

这是 Memory Box 的 HarmonyOS 原生 Stage/ArkTS 工程，目标 API 26.0.0，适配 phone、tablet 和 2in1。

## 启动行为

`module.json5` 的 `EntryAbility` 声明了 `ohos.want.action.home + entity.system.home`，因此安装成功后，**点击桌面上的红色骑兵 Memory Box 图标即可直接进入主界面**。HarmonyOS 没有 Windows/macOS 的“双击 .app”概念，等价操作是点击应用图标。

## v0.14 首版能力

- 原生 ArkUI 首页
- 红色骑兵统一图标
- 本地快速保存
- 稳定 `M000001` 风格 ID
- 本地持久化
- 搜索与记忆列表
- phone / tablet / 2in1 自适应基础布局

HarmonyOS 版目前是原生 companion/core 版；桌面端已有的 MCP、Windows/macOS tray、完整 E2EE 同步和灾难恢复不会伪装成已经在 HarmonyOS 上完全等价实现。后续可以继续把 `.mboxpack/.mboxenc` 迁移协议和百度网盘 E2EE 逐步原生移植到 ArkTS/HUKS。

## 构建

推荐 DevEco Studio 6.1+，HarmonyOS SDK API 26.0.0。打开本目录后 Sync Project，然后：

```bash
hvigorw --mode project -p product=default -p buildMode=debug assembleApp
```

正式版本使用 `buildMode=release`，并在 DevEco Studio/AppGallery Connect 中配置签名。HAP/APP 必须经过有效签名才能在目标设备上按正常应用方式安装。
