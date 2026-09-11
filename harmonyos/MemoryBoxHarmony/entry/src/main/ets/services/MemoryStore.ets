import { relationalStore } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface MemoryRow {
  memoryId: string;
  title: string;
  summary: string;
  category: string;
  updatedAt: string;
}

export class MemoryStore {
  private store?: relationalStore.RdbStore;

  async open(context: common.UIAbilityContext): Promise<void> {
    this.store = await relationalStore.getRdbStore(context, {
      name: 'memorybox_harmony.db',
      securityLevel: relationalStore.SecurityLevel.S1
    });
    await this.store.execute(
      'CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT UNIQUE, title TEXT, summary TEXT, category TEXT, updated_at TEXT)',
      0
    );
  }

  async list(): Promise<MemoryRow[]> {
    if (!this.store) return [];
    const rs = await this.store.querySql('SELECT memory_id,title,summary,category,updated_at FROM memories ORDER BY updated_at DESC LIMIT 100');
    const out: MemoryRow[] = [];
    while (rs.goToNextRow()) {
      out.push({
        memoryId: rs.getString(rs.getColumnIndex('memory_id')),
        title: rs.getString(rs.getColumnIndex('title')),
        summary: rs.getString(rs.getColumnIndex('summary')),
        category: rs.getString(rs.getColumnIndex('category')),
        updatedAt: rs.getString(rs.getColumnIndex('updated_at'))
      });
    }
    rs.close();
    return out;
  }
}
