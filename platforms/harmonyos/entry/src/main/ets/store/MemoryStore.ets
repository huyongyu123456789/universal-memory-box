import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export interface MemoryRecord {
  id: string;
  title: string;
  summary: string;
  category: string;
  updatedAt: number;
}

const PREF_NAME: string = 'memorybox_harmony';
const KEY_MEMORIES: string = 'memories';
const KEY_SEQUENCE: string = 'sequence';

export class MemoryStore {
  private context: common.UIAbilityContext;
  constructor(context: common.UIAbilityContext) {
    this.context = context;
  }

  async list(): Promise<Array<MemoryRecord>> {
    const pref = await preferences.getPreferences(this.context, PREF_NAME);
    const raw = await pref.get(KEY_MEMORIES, '[]') as string;
    try {
      const parsed = JSON.parse(raw) as Array<MemoryRecord>;
      return parsed.sort((a, b) => b.updatedAt - a.updatedAt);
    } catch (_) {
      return [];
    }
  }

  async save(title: string, summary: string, category: string = 'general'): Promise<MemoryRecord> {
    const pref = await preferences.getPreferences(this.context, PREF_NAME);
    const current = await this.list();
    const sequence = Number(await pref.get(KEY_SEQUENCE, 0)) + 1;
    const record: MemoryRecord = {
      id: `M${sequence.toString().padStart(6, '0')}`,
      title: title.trim() || '未命名记忆',
      summary: summary.trim(),
      category: category,
      updatedAt: Date.now()
    };
    current.unshift(record);
    await pref.put(KEY_MEMORIES, JSON.stringify(current));
    await pref.put(KEY_SEQUENCE, sequence);
    await pref.flush();
    return record;
  }

  async search(query: string): Promise<Array<MemoryRecord>> {
    const q = query.trim().toLowerCase();
    const all = await this.list();
    if (!q) return all;
    return all.filter((item) =>
      item.id.toLowerCase().includes(q) ||
      item.title.toLowerCase().includes(q) ||
      item.summary.toLowerCase().includes(q) ||
      item.category.toLowerCase().includes(q)
    );
  }
}
