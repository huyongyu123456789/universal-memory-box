import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from memorybox.db import *
import sqlite3

class T(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.db=Path(self.t.name)/'box.db'
 def tearDown(self): self.t.cleanup()
 def test_save_list_get(self):
  x=save_memory('CRAB 抗菌实验 MIC 与基因组研究',db_path=self.db)
  self.assertEqual(x['memory_id'],'M000001'); self.assertEqual(x['category'],'research'); self.assertEqual(get_memory('M000001',self.db)['title'],x['title'])
 def test_category_manuscript(self):
  x=save_memory('JGAR 论文投稿 reviewer revision 参考文献',db_path=self.db); self.assertEqual(x['category'],'manuscript')
 def test_append_version(self):
  x=save_memory('first',db_path=self.db); y=append_memory(x['memory_id'],'second',db_path=self.db); self.assertIn('second',y['content'])
  con=sqlite3.connect(self.db)
  try: self.assertEqual(con.execute('select count(*) from memory_versions').fetchone()[0],1)
  finally: con.close()
 def test_flags(self):
  x=save_memory('abc',db_path=self.db); self.assertTrue(set_flag(x['memory_id'],'pinned',True,self.db)['pinned'])
 def test_search(self):
  save_memory('Python MCP adapter for Kimi',tags=['Kimi'],db_path=self.db); self.assertTrue(list_memories(query='Kimi',db_path=self.db))
 def test_resume(self):
  a=save_memory('A context',db_path=self.db); b=save_memory('B context',db_path=self.db); out=compose_context([a['memory_id'],b['memory_id']],self.db); self.assertIn('A context',out); self.assertIn('B context',out)

 def test_merge_bundle(self):
  a=save_memory('CRAB genome stage one',tags=['CRAB'],db_path=self.db); b=save_memory('CRAB genome stage two',tags=['CRAB'],db_path=self.db)
  m=merge_memories([a['memory_id'],b['memory_id']],db_path=self.db); self.assertIn('merged',m['tags'])
  bundle=bundle_by_query('CRAB',db_path=self.db); self.assertGreaterEqual(bundle['count'],2); self.assertIn('Resume Context',bundle['context'])
 def test_date_filter(self):
  save_memory('dated',db_path=self.db); self.assertEqual(len(list_memories(updated_after='2999-01-01T00:00:00Z',db_path=self.db)),0)
 def test_import_uam(self):
  vault=Path(self.t.name)/'uam'; (vault/'memories').mkdir(parents=True)
  (vault/'memories'/'M000123.json').write_text(json.dumps({'memory_id':'M000123','title':'old','summary':'old summary','narrative':'old research memory','tags':['legacy'],'source':{'agent':'uam'}}),encoding='utf-8')
  st=import_uam_json(vault,self.db); self.assertEqual(st['imported'],1); self.assertEqual(get_memory('M000123',self.db)['title'],'old')

 def test_mcp_stdio(self):
  env=os.environ.copy(); env['MEMORYBOX_HOME']=self.t.name
  req='\n'.join([json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}}),json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})])+'\n'
  cp=subprocess.run([sys.executable,str(ROOT/'memorybox_main.py'),'mcp'],input=req,text=True,capture_output=True,env=env,timeout=10)
  self.assertEqual(cp.returncode,0,cp.stderr); lines=[json.loads(x) for x in cp.stdout.splitlines() if x.strip()]; self.assertEqual(lines[0]['result']['serverInfo']['name'],'Memory Box'); self.assertGreaterEqual(len(lines[1]['result']['tools']),6)

 def test_concurrent_saves_get_unique_ids(self):
  from concurrent.futures import ThreadPoolExecutor
  def work(i): return save_memory(f'parallel memory {i}',db_path=self.db)['memory_id']
  with ThreadPoolExecutor(max_workers=8) as ex:
   ids=list(ex.map(work,range(20)))
  self.assertEqual(len(ids),20); self.assertEqual(len(set(ids)),20)
  self.assertEqual(sorted(ids)[0],'M000001'); self.assertEqual(sorted(ids)[-1],'M000020')

 def test_schema_v1_migrates_source_uri(self):
  con=sqlite3.connect(self.db)
  con.executescript("""
  CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE memories(
    id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT UNIQUE, title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '', content TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'general',
    source_agent TEXT NOT NULL DEFAULT 'unknown', source_type TEXT NOT NULL DEFAULT 'conversation',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0,
    favorite INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0
  );
  """)
  con.close()
  init_db(self.db)
  con=sqlite3.connect(self.db)
  try:
   cols=[r[1] for r in con.execute('pragma table_info(memories)')]
   self.assertIn('source_uri',cols)
   self.assertEqual(con.execute("select value from meta where key='schema_version'").fetchone()[0],'8')
  finally: con.close()
  x=save_memory('web memory',source_agent='ChatGPT Web',source_uri='https://chatgpt.com/c/test',db_path=self.db)
  self.assertEqual(x['source_uri'],'https://chatgpt.com/c/test'); self.assertIn('https://chatgpt.com/c/test',compose_context([x['memory_id']],self.db))

 def test_transfer_pack_roundtrip(self):
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle, inspect_transfer_bundle
  a=save_memory('完整聊天：用户问 CRAB，Agent 给出 Stage 2 方案',title='CRAB 对话',tags=['chat'],source_agent='ChatGPT Web',source_uri='https://chatgpt.com/c/example',db_path=self.db)
  append_memory(a['memory_id'],'后续决定：继续 Batch 2',db_path=self.db)
  pack=Path(self.t.name)/'chat.mboxpack'
  ex=export_transfer_bundle(pack,memory_ids=[a['memory_id']],db_path=self.db)
  self.assertTrue(pack.exists()); self.assertEqual(ex['memory_count'],1)
  ins=inspect_transfer_bundle(pack); self.assertEqual(ins['memory_count'],1); self.assertEqual(ins['titles'][0]['memory_id'],'M000001')
  other=Path(self.t.name)/'other.db'
  im=import_transfer_bundle(pack,db_path=other)
  self.assertEqual(im['imported'],1); self.assertEqual(get_memory('M000001',other)['source_agent'],'ChatGPT Web')
  self.assertTrue(Path(im['replay_path']).exists())

 def test_transfer_conflict_remaps_and_is_idempotent(self):
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle, device_id
  src=Path(self.t.name)/'src.db'; dst=Path(self.t.name)/'dst.db'
  save_memory('remote content',db_path=src); save_memory('local different content',db_path=dst)
  self.assertNotEqual(device_id(src),device_id(dst))
  pack=Path(self.t.name)/'conflict.mboxpack'; export_transfer_bundle(pack,db_path=src)
  first=import_transfer_bundle(pack,db_path=dst)
  self.assertEqual(first['imported'],1); self.assertEqual(first['remapped'],1); self.assertEqual(first['mapping']['M000001'],'M000002')
  self.assertEqual(get_memory('M000001',dst)['content'],'local different content'); self.assertEqual(get_memory('M000002',dst)['content'],'remote content')
  second=import_transfer_bundle(pack,db_path=dst); self.assertEqual(second['imported'],0); self.assertGreaterEqual(second['skipped'],1)

 def test_transfer_folder_roundtrip(self):
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle
  save_memory('folder portable memory',db_path=self.db)
  folder=Path(self.t.name)/'TransferFolder'
  export_transfer_bundle(folder,as_folder=True,db_path=self.db)
  for name in ['manifest.json','memories.json','resume.md','viewer.html','README.txt']: self.assertTrue((folder/name).exists())
  dst=Path(self.t.name)/'folder-dst.db'; r=import_transfer_bundle(folder,db_path=dst); self.assertEqual(r['imported'],1)

 def test_transfer_checksum_rejects_tamper(self):
  import zipfile
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle
  save_memory('tamper target',db_path=self.db)
  pack=Path(self.t.name)/'tamper.mboxpack'; export_transfer_bundle(pack,db_path=self.db)
  bad=Path(self.t.name)/'bad.mboxpack'
  with zipfile.ZipFile(pack,'r') as zin, zipfile.ZipFile(bad,'w') as zout:
   for info in zin.infolist():
    data=zin.read(info.filename)
    if info.filename=='memories.json': data=data+b' '
    zout.writestr(info.filename,data)
  with self.assertRaisesRegex(ValueError,'checksum mismatch'):
   import_transfer_bundle(bad,db_path=Path(self.t.name)/'bad.db')

 def test_transfer_ignores_unknown_zip_paths(self):
  import zipfile
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle
  save_memory('safe archive',db_path=self.db)
  pack=Path(self.t.name)/'safe.mboxpack'; export_transfer_bundle(pack,db_path=self.db)
  with zipfile.ZipFile(pack,'a') as zf: zf.writestr('../../evil.txt','evil')
  outside=Path(self.t.name).parent/'evil.txt'
  if outside.exists(): outside.unlink()
  r=import_transfer_bundle(pack,db_path=Path(self.t.name)/'safe2.db')
  self.assertEqual(r['imported'],1); self.assertFalse(outside.exists())

 def test_attachment_store_dedup_and_resume(self):
  from memorybox.attachments import add_attachment, list_attachments
  f=Path(self.t.name)/'report.pdf'; f.write_bytes(b'%PDF-demo-same-content')
  a=save_memory('memory A',db_path=self.db); b=save_memory('memory B',db_path=self.db)
  x=add_attachment(a['memory_id'],f,note='primary paper',db_path=self.db); y=add_attachment(b['memory_id'],f,db_path=self.db)
  self.assertEqual(x['sha256'],y['sha256']); self.assertEqual(len(list_attachments(a['memory_id'],self.db)),1)
  con=sqlite3.connect(self.db)
  try: self.assertEqual(con.execute('select count(*) from attachments').fetchone()[0],1)
  finally: con.close()
  ctx=compose_context([a['memory_id']],self.db); self.assertIn('report.pdf',ctx); self.assertIn('Local path:',ctx)

 def test_transfer_with_attachment_roundtrip_between_devices(self):
  from memorybox.attachments import add_attachment
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle, inspect_transfer_bundle
  srcdir=Path(self.t.name)/'src'; dstdir=Path(self.t.name)/'dst'; srcdir.mkdir(); dstdir.mkdir()
  srcdb=srcdir/'box.db'; dstdb=dstdir/'box.db'; f=srcdir/'figure.png'; raw=b'\x89PNG\r\ncomplete-session-image'; f.write_bytes(raw)
  m=save_memory('chat with figure',source_agent='Kimi Web',db_path=srcdb); add_attachment(m['memory_id'],f,note='Figure 1',db_path=srcdb)
  pack=Path(self.t.name)/'session.mboxpack'; ex=export_transfer_bundle(pack,memory_ids=[m['memory_id']],db_path=srcdb)
  self.assertEqual(ex['attachment_count'],1); self.assertEqual(inspect_transfer_bundle(pack)['attachment_count'],1)
  im=import_transfer_bundle(pack,db_path=dstdb); self.assertEqual(im['attachments_imported'],1); self.assertEqual(im['attachments_linked'],1)
  got=get_memory('M000001',dstdb); self.assertEqual(got['attachments'][0]['original_name'],'figure.png'); self.assertEqual(Path(got['attachments'][0]['local_path']).read_bytes(),raw)
  self.assertTrue((Path(im['replay_path']).parent/'attachments'/'blobs'/got['attachments'][0]['sha256']).exists())

 def test_transfer_attachment_tamper_is_rejected(self):
  import zipfile
  from memorybox.attachments import add_attachment
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle
  f=Path(self.t.name)/'x.txt'; f.write_text('trusted attachment',encoding='utf-8'); m=save_memory('with file',db_path=self.db); a=add_attachment(m['memory_id'],f,db_path=self.db)
  pack=Path(self.t.name)/'ok.mboxpack'; export_transfer_bundle(pack,db_path=self.db); bad=Path(self.t.name)/'bad-att.mboxpack'
  target='attachments/blobs/'+a['sha256']
  with zipfile.ZipFile(pack) as zin, zipfile.ZipFile(bad,'w') as zout:
   for info in zin.infolist():
    data=zin.read(info.filename)
    if info.filename==target: data=b'tampered'
    zout.writestr(info.filename,data)
  with self.assertRaisesRegex(ValueError,'checksum mismatch'):
   import_transfer_bundle(bad,db_path=Path(self.t.name)/'tamper-dst'/'box.db')

 def test_import_legacy_transfer_v1(self):
  import hashlib, zipfile, uuid
  from memorybox.transfer import import_transfer_bundle
  card={'memory_id':'M000123','title':'legacy v1','summary':'old','content':'old package content','category':'general','source_agent':'old','source_type':'conversation','source_uri':'','created_at':'2026-01-01T00:00:00Z','updated_at':'2026-01-01T00:00:00Z','pinned':False,'favorite':False,'archived':False,'tags':[],'versions':[]}
  mb=json.dumps({'memories':[card]},ensure_ascii=False,indent=2,sort_keys=True).encode(); manifest={'format':'memorybox-transfer','format_version':1,'transfer_id':str(uuid.uuid4()),'created_at':'2026-01-01T00:00:00Z','memorybox_version':'0.6.0','source_device_id':str(uuid.uuid4()),'memory_count':1,'checksums':{'memories.json':hashlib.sha256(mb).hexdigest()}}
  pack=Path(self.t.name)/'legacy.mboxpack'
  with zipfile.ZipFile(pack,'w') as zf: zf.writestr('manifest.json',json.dumps(manifest).encode()); zf.writestr('memories.json',mb)
  dst=Path(self.t.name)/'legacy-dst'/'box.db'; r=import_transfer_bundle(pack,db_path=dst); self.assertEqual(r['imported'],1); self.assertEqual(get_memory('M000123',dst)['title'],'legacy v1')


 def test_baidu_sync_folder_roundtrip_and_idempotence(self):
  from memorybox.sync import configure_sync_folder, publish_to_sync, receive_from_sync, list_sync_devices, trust_sync_device
  from memorybox.attachments import add_attachment
  shared=Path(self.t.name)/'baidu-synced-folder'; db_a=Path(self.t.name)/'A'/'box.db'; db_b=Path(self.t.name)/'B'/'box.db'
  m=save_memory('CRAB session sent through Baidu Netdisk synchronized folder',title='Baidu sync memory',db_path=db_a)
  f=Path(self.t.name)/'paper.pdf'; f.write_bytes(b'%PDF-1.4\nBaidu-sync-demo'); add_attachment(m['memory_id'],f,db_path=db_a)
  a=configure_sync_folder(shared,provider='baidu-netdisk',name='我的百度网盘',db_path=db_a)
  b=configure_sync_folder(shared,provider='baidu-netdisk',name='我的百度网盘',db_path=db_b)
  # E2EE cloud sync is mutual trust: sender authorizes recipient and recipient authorizes sender.
  seen_a=[d for d in list_sync_devices(a['endpoint_id'],db_path=db_a) if not d['is_local']][0]
  seen_b=[d for d in list_sync_devices(b['endpoint_id'],db_path=db_b) if not d['is_local']][0]
  trust_sync_device(a['endpoint_id'],seen_a['device_id'],expected_fingerprint=seen_a['e2ee_fingerprint'],db_path=db_a)
  trust_sync_device(b['endpoint_id'],seen_b['device_id'],expected_fingerprint=seen_b['e2ee_fingerprint'],db_path=db_b)
  sent=publish_to_sync(a['endpoint_id'],memory_ids=[m['memory_id']],db_path=db_a); self.assertEqual(sent['memory_count'],1); self.assertTrue(sent['encrypted']); self.assertTrue(sent['path'].endswith('.mboxenc'))
  pulled=receive_from_sync(b['endpoint_id'],db_path=db_b); self.assertEqual(pulled['imported_packages'],1); self.assertEqual(pulled['encrypted_imports'],1); self.assertEqual(pulled['memories_imported'],1)
  got=get_memory('M000001',db_b); self.assertEqual(got['title'],'Baidu sync memory'); self.assertEqual(got['attachments'][0]['original_name'],'paper.pdf')
  again=receive_from_sync(b['endpoint_id'],db_path=db_b); self.assertEqual(again['imported_packages'],0); self.assertGreaterEqual(again['skipped_packages'],1)
  devices=list_sync_devices(b['endpoint_id'],db_path=db_b); self.assertGreaterEqual(len(devices),2)

 def test_sync_remove_never_deletes_cloud_files(self):
  from memorybox.sync import configure_sync_folder, publish_to_sync, remove_sync_endpoint
  shared=Path(self.t.name)/'cloud'; db=Path(self.t.name)/'box.db'; m=save_memory('keep cloud file',db_path=db)
  ep=configure_sync_folder(shared,provider='baidu-netdisk',db_path=db); sent=publish_to_sync(ep['endpoint_id'],memory_ids=[m['memory_id']],db_path=db)
  pack=Path(sent['path']); self.assertTrue(pack.exists()); r=remove_sync_endpoint(ep['endpoint_id'],db_path=db); self.assertFalse(r['cloud_files_deleted']); self.assertTrue(pack.exists())

 def test_lan_pair_send_roundtrip(self):
  from memorybox.transfer import export_transfer_bundle
  from memorybox.lan import start_pairing, send_pack, stop_pairing
  db_a=Path(self.t.name)/'la'/'box.db'; db_b=Path(self.t.name)/'lb'/'box.db'; m=save_memory('LAN direct transfer memory',db_path=db_a)
  pack=Path(self.t.name)/'lan.mboxpack'; export_transfer_bundle(pack,memory_ids=[m['memory_id']],db_path=db_a)
  st=start_pairing(port=0,db_path=db_b)
  try:
   r=send_pack('127.0.0.1',st['port'],st['code'],pack,db_path=db_a); self.assertTrue(r['ok']); self.assertTrue(r['encrypted']); self.assertTrue(r['e2ee']); self.assertEqual(get_memory('M000001',db_b)['content'],'LAN direct transfer memory')
  finally: stop_pairing()

 def test_lan_wrong_pairing_code_rejected(self):
  from memorybox.transfer import export_transfer_bundle
  from memorybox.lan import start_pairing, send_pack, stop_pairing
  db_a=Path(self.t.name)/'wa'/'box.db'; db_b=Path(self.t.name)/'wb'/'box.db'; m=save_memory('secret',db_path=db_a)
  pack=Path(self.t.name)/'wrong.mboxpack'; export_transfer_bundle(pack,memory_ids=[m['memory_id']],db_path=db_a); st=start_pairing(port=0,db_path=db_b)
  try:
   with self.assertRaisesRegex(RuntimeError,'LAN transfer failed'): send_pack('127.0.0.1',st['port'],'000000' if st['code']!='000000' else '999999',pack,db_path=db_a)
  finally: stop_pairing()


 def test_e2ee_package_confidentiality_and_tamper_detection(self):
  from memorybox.crypto import public_identity, encrypt_file_for_recipients, decrypt_file_for_local_device
  from memorybox.transfer import device_id
  a=Path(self.t.name)/'ea'/'box.db'; b=Path(self.t.name)/'eb'/'box.db'; c=Path(self.t.name)/'ec'/'box.db'
  a.parent.mkdir(); b.parent.mkdir(); c.parent.mkdir()
  raw=b'SUPER-SECRET-MEMORY-'*5000; src=Path(self.t.name)/'plain.mboxpack'; src.write_bytes(raw)
  enc=Path(self.t.name)/'secret.mboxenc'; encrypt_file_for_recipients(src,enc,recipients=[public_identity(b)],transfer_id='transfer-secret',source_device_id=device_id(a),db_path=a)
  ciphertext=enc.read_bytes(); self.assertNotIn(b'SUPER-SECRET-MEMORY-',ciphertext)
  out=Path(self.t.name)/'decoded.bin'; decrypt_file_for_local_device(enc,out,expected_sender_public_key=public_identity(a)['public_key'],db_path=b); self.assertEqual(out.read_bytes(),raw)
  with self.assertRaises(PermissionError): decrypt_file_for_local_device(enc,Path(self.t.name)/'wrong.bin',db_path=c)
  bad=Path(self.t.name)/'tampered.mboxenc'; changed=bytearray(ciphertext); changed[-20]^=1; bad.write_bytes(changed)
  with self.assertRaises(Exception): decrypt_file_for_local_device(bad,Path(self.t.name)/'tampered.bin',expected_sender_public_key=public_identity(a)['public_key'],db_path=b)

 def test_e2ee_sync_rejects_untrusted_sender_then_accepts_after_mutual_trust(self):
  from memorybox.sync import configure_sync_folder, list_sync_devices, trust_sync_device, publish_to_sync, receive_from_sync
  shared=Path(self.t.name)/'secure-cloud'; a=Path(self.t.name)/'sa'/'box.db'; b=Path(self.t.name)/'sb'/'box.db'; a.parent.mkdir(); b.parent.mkdir()
  ea=configure_sync_folder(shared,provider='baidu-netdisk',db_path=a); eb=configure_sync_folder(shared,provider='baidu-netdisk',db_path=b)
  b_on_a=[d for d in list_sync_devices(ea['endpoint_id'],db_path=a) if not d['is_local']][0]
  a_on_b=[d for d in list_sync_devices(eb['endpoint_id'],db_path=b) if not d['is_local']][0]
  trust_sync_device(ea['endpoint_id'],b_on_a['device_id'],expected_fingerprint=b_on_a['e2ee_fingerprint'],db_path=a)
  m=save_memory('mutually authenticated cloud memory',db_path=a); publish_to_sync(ea['endpoint_id'],memory_ids=[m['memory_id']],db_path=a)
  pre=receive_from_sync(eb['endpoint_id'],db_path=b); self.assertEqual(pre['imported_packages'],0); self.assertGreaterEqual(pre['skipped_packages'],1)
  trust_sync_device(eb['endpoint_id'],a_on_b['device_id'],expected_fingerprint=a_on_b['e2ee_fingerprint'],db_path=b)
  post=receive_from_sync(eb['endpoint_id'],db_path=b); self.assertEqual(post['imported_packages'],1); self.assertEqual(get_memory('M000001',b)['content'],'mutually authenticated cloud memory')

 def test_trust_fingerprint_mismatch_is_rejected(self):
  from memorybox.sync import configure_sync_folder, list_sync_devices, trust_sync_device
  shared=Path(self.t.name)/'fp'; a=Path(self.t.name)/'fa'/'box.db'; b=Path(self.t.name)/'fb'/'box.db'; a.parent.mkdir(); b.parent.mkdir()
  ea=configure_sync_folder(shared,db_path=a); configure_sync_folder(shared,db_path=b)
  remote=[d for d in list_sync_devices(ea['endpoint_id'],db_path=a) if not d['is_local']][0]
  with self.assertRaisesRegex(ValueError,'fingerprint confirmation failed'):
   trust_sync_device(ea['endpoint_id'],remote['device_id'],expected_fingerprint='0000:0000',db_path=a)

 def test_v08_sync_endpoint_migrates_as_legacy_plaintext(self):
  db=Path(self.t.name)/'legacy-sync.db'; con=sqlite3.connect(db)
  con.executescript("""
  CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE sync_endpoints(endpoint_id TEXT PRIMARY KEY,name TEXT NOT NULL,provider TEXT NOT NULL,root_path TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,auto_import INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
  INSERT INTO sync_endpoints VALUES('old','old baidu','baidu-netdisk','/tmp/old',1,1,'2026-01-01','2026-01-01');
  """); con.close(); init_db(db)
  con=sqlite3.connect(db)
  try: self.assertEqual(con.execute("select encryption_mode from sync_endpoints where endpoint_id='old'").fetchone()[0],'legacy-plaintext')
  finally: con.close()


 def test_e2ee_spoofed_sender_key_is_rejected(self):
  from memorybox.crypto import public_identity, encrypt_file_for_recipients
  from memorybox.sync import configure_sync_folder, list_sync_devices, trust_sync_device, receive_from_sync
  from memorybox.transfer import export_transfer_bundle, device_id
  shared=Path(self.t.name)/'spoof-cloud'; a=Path(self.t.name)/'spa'/'box.db'; b=Path(self.t.name)/'spb'/'box.db'; c=Path(self.t.name)/'spc'/'box.db'
  a.parent.mkdir(); b.parent.mkdir(); c.parent.mkdir()
  ea=configure_sync_folder(shared,db_path=a); eb=configure_sync_folder(shared,db_path=b); configure_sync_folder(shared,db_path=c)
  # B trusts the genuine A key.
