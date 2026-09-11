import { common } from '@kit.AbilityKit';
import { UIContext } from '@kit.ArkUI';
import { MemoryRow, MemoryStore } from '../services/MemoryStore';

@Entry
@Component
struct Index {
  @State active: string = 'home';
  @State memories: MemoryRow[] = [];
  @State ready: boolean = false;
  private store: MemoryStore = new MemoryStore();

  aboutToAppear(): void {
    this.bootstrap();
  }

  async bootstrap(): Promise<void> {
    try {
      const context = new UIContext().getHostContext() as common.UIAbilityContext;
      await this.store.open(context);
      this.memories = await this.store.list();
      this.ready = true;
    } catch (_) {
      this.ready = false;
    }
  }

  @Builder
  Card(title: string, value: string, detail: string) {
    Column({ space: 8 }) {
      Text(title).fontSize(14).fontColor('#6E6E73')
      Text(value).fontSize(30).fontWeight(FontWeight.Bold).fontColor('#1D1D1F')
      Text(detail).fontSize(13).fontColor('#86868B').lineHeight(19)
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%').padding(20).backgroundColor('#FFFFFF').borderRadius(20)
  }

  build() {
    Navigation() {
      Scroll() {
        Column({ space: 16 }) {
          Row({ space: 12 }) {
            Image($r('app.media.app_icon')).width(52).height(52).borderRadius(13)
            Column({ space: 3 }) {
              Text('Memory Box').fontSize(28).fontWeight(FontWeight.Bold).fontColor('#1D1D1F')
              Text('跨 Agent · 跨设备 · 本地优先').fontSize(13).fontColor('#86868B')
            }.alignItems(HorizontalAlign.Start)
          }.width('100%')

          this.Card('本地记忆', `${this.memories.length}`, this.ready ? 'HarmonyOS 本地 RDB 已连接' : '正在初始化本地数据库')
          this.Card('安全同步', 'E2EE', '桌面端可信设备与云同步协议兼容层')

          Column({ space: 10 }) {
            Text('最近记忆').fontSize(20).fontWeight(FontWeight.Bold).width('100%')
            if (this.memories.length === 0) {
              Text('还没有本地记忆。后续可通过迁移包或可信设备同步导入。')
                .fontSize(14).fontColor('#86868B').padding(18).width('100%')
                .backgroundColor('#FFFFFF').borderRadius(18)
            } else {
              ForEach(this.memories, (m: MemoryRow) => {
                Column({ space: 4 }) {
                  Text(m.title).fontSize(16).fontWeight(FontWeight.Medium)
                  Text(`${m.memoryId} · ${m.category}`).fontSize(12).fontColor('#86868B')
                  Text(m.summary).fontSize(13).fontColor('#6E6E73').maxLines(2)
                }.alignItems(HorizontalAlign.Start).width('100%').padding(16).backgroundColor('#FFFFFF').borderRadius(18)
              }, (m: MemoryRow) => m.memoryId)
            }
          }.width('100%')

          Text('v0.16.0 · HarmonyOS native foundation')
            .fontSize(12).fontColor('#A1A1A6').margin({ top: 8, bottom: 18 })
        }
        .width('100%').padding({ left: 18, right: 18, top: 20 }).backgroundColor('#F5F5F7')
      }.edgeEffect(EdgeEffect.Spring)
    }.hideTitleBar(true)
  }
}
