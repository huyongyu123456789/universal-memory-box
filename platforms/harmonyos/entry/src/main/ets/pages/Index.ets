import { common } from '@kit.AbilityKit';
import { MemoryRecord, MemoryStore } from '../store/MemoryStore';

@Entry
@Component
struct Index {
  @State memories: Array<MemoryRecord> = [];
  @State titleText: string = '';
  @State bodyText: string = '';
  @State query: string = '';
  @State statusText: string = '本地记忆已就绪';
  private store?: MemoryStore;

  aboutToAppear(): void {
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.store = new MemoryStore(context);
    this.reload();
  }

  async reload(): Promise<void> {
    if (!this.store) return;
    this.memories = await this.store.search(this.query);
  }

  async saveMemory(): Promise<void> {
    if (!this.store || (!this.titleText.trim() && !this.bodyText.trim())) return;
    const saved = await this.store.save(this.titleText, this.bodyText, 'general');
    this.titleText = '';
    this.bodyText = '';
    this.statusText = `已保存 ${saved.id}`;
    await this.reload();
  }

  @Builder
  Card(content: () => void) {
    Column() { content() }
      .width('100%')
      .padding(18)
      .borderRadius(20)
      .backgroundColor('#FFFFFFFF')
      .shadow({ radius: 18, color: '#14000000', offsetX: 0, offsetY: 5 })
  }

  build() {
    Scroll() {
      Column({ space: 16 }) {
        Row({ space: 12 }) {
          Image($r('app.media.memorybox_icon')).width(54).height(54).borderRadius(14)
          Column({ space: 4 }) {
            Text('Memory Box').fontSize(28).fontWeight(FontWeight.Bold).fontColor('#1D1D1F')
            Text('跨 Agent · 跨设备 · 本地优先').fontSize(14).fontColor('#6E6E73')
          }.alignItems(HorizontalAlign.Start).layoutWeight(1)
          Text('v0.14').fontSize(12).fontColor('#D91E2B').padding({ left: 10, right: 10, top: 6, bottom: 6 }).backgroundColor('#12D91E2B').borderRadius(20)
        }.width('100%')

        this.Card(() => {
          Row() {
            Column({ space: 5 }) {
              Text('设备状态').fontSize(13).fontColor('#6E6E73')
              Text(this.statusText).fontSize(20).fontWeight(FontWeight.Medium).fontColor('#1D1D1F')
            }.alignItems(HorizontalAlign.Start).layoutWeight(1)
            Text(`${this.memories.length}`).fontSize(34).fontWeight(FontWeight.Bold).fontColor('#D91E2B')
          }.width('100%')
        })

        this.Card(() => {
          Column({ space: 12 }) {
            Text('快速保存').fontSize(20).fontWeight(FontWeight.Bold).fontColor('#1D1D1F').width('100%').textAlign(TextAlign.Start)
            TextInput({ placeholder: '标题', text: this.titleText }).onChange((v: string) => this.titleText = v).height(46).backgroundColor('#F5F5F7').borderRadius(12)
            TextArea({ placeholder: '把需要继续使用的对话、决定或任务记在这里…', text: this.bodyText }).onChange((v: string) => this.bodyText = v).height(112).backgroundColor('#F5F5F7').borderRadius(12)
            Button('保存到 Memory Box').width('100%').height(46).borderRadius(14).backgroundColor('#D91E2B').fontColor(Color.White).onClick(() => this.saveMemory())
          }.width('100%')
        })

        TextInput({ placeholder: '搜索记忆', text: this.query })
          .onChange(async (v: string) => { this.query = v; await this.reload(); })
          .height(46).backgroundColor('#FFFFFFFF').borderRadius(14)

        Column({ space: 10 }) {
          ForEach(this.memories, (item: MemoryRecord) => {
            Row({ space: 12 }) {
              Column({ space: 4 }) {
                Row({ space: 8 }) {
                  Text(item.id).fontSize(12).fontColor('#D91E2B')
                  Text(item.category).fontSize(11).fontColor('#6E6E73')
                }
                Text(item.title).fontSize(17).fontWeight(FontWeight.Medium).fontColor('#1D1D1F').maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
                Text(item.summary || '无摘要').fontSize(13).fontColor('#6E6E73').maxLines(2).textOverflow({ overflow: TextOverflow.Ellipsis })
              }.alignItems(HorizontalAlign.Start).layoutWeight(1)
            }
            .width('100%').padding(16).borderRadius(18).backgroundColor('#FFFFFFFF')
          }, (item: MemoryRecord) => item.id)
        }.width('100%')
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 28, bottom: 40 })
    }
    .width('100%').height('100%').backgroundColor('#F5F5F7')
  }
}
