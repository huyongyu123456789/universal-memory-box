from __future__ import annotations
import json
from pathlib import Path

root = Path(__file__).resolve().parent
required = [
    'AppScope/app.json5',
    'build-profile.json5',
    'hvigorfile.ts',
    'entry/src/main/module.json5',
    'entry/src/main/ets/entryability/EntryAbility.ets',
    'entry/src/main/ets/pages/Index.ets',
    'entry/src/main/resources/base/profile/main_pages.json',
    'entry/src/main/resources/base/media/memorybox_icon.png',
]
for rel in required:
    p = root / rel
    if not p.exists() or p.stat().st_size == 0:
        raise SystemExit(f'missing: {rel}')
app = json.loads((root/'AppScope/app.json5').read_text())['app']
module = json.loads((root/'entry/src/main/module.json5').read_text())['module']
profile = json.loads((root/'build-profile.json5').read_text())
assert app['bundleName'] == 'com.memorybox.harmony'
assert app['versionName'] == '0.14.0'
assert app['icon'] == '$media:memorybox_icon'
assert profile['app']['products'][0]['compileSdkVersion'] == '26.0.0'
ability = module['abilities'][0]
assert ability['name'] == 'EntryAbility'
assert ability['launchType'] == 'singleton'
skills = ability['skills'][0]
assert 'entity.system.home' in skills['entities']
assert 'ohos.want.action.home' in skills['actions']
assert module['pages'] == '$profile:main_pages'
print('HarmonyOS project contract: PASS')
