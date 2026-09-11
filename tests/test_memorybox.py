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
   self.assertEqual(con.execute("select value from meta where key='schema_version'").fetchone()[0],'10')
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
  a_on_b=[d for d in list_sync_devices(eb['endpoint_id'],db_path=b) if d['device_id']==device_id(a)][0]
  trust_sync_device(eb['endpoint_id'],a_on_b['device_id'],expected_fingerprint=a_on_b['e2ee_fingerprint'],db_path=b)
  # C creates a valid ciphertext addressed to B but lies that source_device_id is A.
  cm=save_memory('forged package',db_path=c); plain=Path(self.t.name)/'forged.mboxpack'; ex=export_transfer_bundle(plain,memory_ids=[cm['memory_id']],db_path=c)
  outdir=shared/'MemoryBoxSync'/'packages'/device_id(a); outdir.mkdir(parents=True,exist_ok=True); enc=outdir/(ex['transfer_id']+'.mboxenc')
  encrypt_file_for_recipients(plain,enc,recipients=[public_identity(b)],transfer_id=ex['transfer_id'],source_device_id=device_id(a),db_path=c)
  r=receive_from_sync(eb['endpoint_id'],db_path=b); self.assertEqual(r['imported_packages'],0); self.assertEqual(len(r['errors']),0); self.assertGreaterEqual(r['skipped_packages'],1)
  with self.assertRaises(KeyError): get_memory('M000001',b)

 def test_e2ee_endpoint_ignores_plaintext_downgrade(self):
  from memorybox.sync import configure_sync_folder, receive_from_sync
  from memorybox.transfer import export_transfer_bundle, device_id
  a=Path(self.t.name)/'da'/'box.db'; b=Path(self.t.name)/'dbb'/'box.db'; a.parent.mkdir(); b.parent.mkdir(); shared=Path(self.t.name)/'downgrade'
  configure_sync_folder(shared,db_path=a); eb=configure_sync_folder(shared,db_path=b)
  m=save_memory('plaintext downgrade attempt',db_path=a); packdir=shared/'MemoryBoxSync'/'packages'/device_id(a); packdir.mkdir(parents=True,exist_ok=True)
  export_transfer_bundle(packdir/'plain.mboxpack',memory_ids=[m['memory_id']],db_path=a)
  r=receive_from_sync(eb['endpoint_id'],db_path=b); self.assertEqual(r['imported_packages'],0); self.assertGreaterEqual(r['skipped_packages'],1)

 def test_device_key_file_is_private_on_posix(self):
  from memorybox.crypto import ensure_device_identity
  db=Path(self.t.name)/'keyhome'/'box.db'; db.parent.mkdir(); info=ensure_device_identity(db); p=Path(info['key_path']); self.assertTrue(p.exists())
  if os.name!='nt': self.assertEqual(p.stat().st_mode & 0o777,0o600)

 def test_recovery_kit_encrypts_identity_and_roundtrips(self):
  from memorybox.crypto import public_identity
  from memorybox.recovery import create_recovery_kit, inspect_recovery_kit, restore_recovery_kit
  a=Path(self.t.name)/'ra'/'box.db'; b=Path(self.t.name)/'rb'/'box.db'; a.parent.mkdir(); b.parent.mkdir()
  ident=public_identity(a); keydoc=json.loads((a.parent/'keys'/'device-x25519.json').read_text(encoding='utf-8'))
  kit=create_recovery_kit(Path(self.t.name)/'identity-backup',db_path=a)
  text=Path(kit['path']).read_text(encoding='utf-8')
  self.assertNotIn(keydoc['private_key'],text); self.assertNotIn(kit['recovery_code'],text)
  meta=inspect_recovery_kit(kit['path']); self.assertEqual(meta['fingerprint'],ident['fingerprint'])
  restored=restore_recovery_kit(kit['path'],kit['recovery_code'],db_path=b)
  self.assertTrue(restored['ok']); self.assertEqual(public_identity(b)['public_key'],ident['public_key']); self.assertEqual(public_identity(b)['device_id'],ident['device_id'])

 def test_recovered_identity_decrypts_historical_e2ee(self):
  from memorybox.crypto import public_identity, encrypt_file_for_recipients, decrypt_file_for_local_device
  from memorybox.recovery import create_recovery_kit, restore_recovery_kit
  old=Path(self.t.name)/'old'/'box.db'; sender=Path(self.t.name)/'sender'/'box.db'; new=Path(self.t.name)/'new'/'box.db'
  old.parent.mkdir(); sender.parent.mkdir(); new.parent.mkdir()
  old_ident=public_identity(old); sender_ident=public_identity(sender)
  kit=create_recovery_kit(Path(self.t.name)/'old.mbxrecovery',db_path=old)
  plain=Path(self.t.name)/'historical.mboxpack'; payload=b'HISTORICAL-SECRET-MEMORY'*1000; plain.write_bytes(payload)
  enc=Path(self.t.name)/'historical.mboxenc'
  encrypt_file_for_recipients(plain,enc,recipients=[old_ident],transfer_id='historical-transfer',source_device_id=sender_ident['device_id'],db_path=sender)
  with self.assertRaises(PermissionError): decrypt_file_for_local_device(enc,Path(self.t.name)/'before.bin',expected_sender_public_key=sender_ident['public_key'],db_path=new)
  restore_recovery_kit(kit['path'],kit['recovery_code'],db_path=new)
  out=Path(self.t.name)/'after.bin'; decrypt_file_for_local_device(enc,out,expected_sender_public_key=sender_ident['public_key'],db_path=new)
  self.assertEqual(out.read_bytes(),payload)

 def test_recovery_wrong_code_and_tamper_rejected(self):
  from memorybox.recovery import create_recovery_kit, restore_recovery_kit
  a=Path(self.t.name)/'rwa'/'box.db'; a.parent.mkdir(); kit=create_recovery_kit(Path(self.t.name)/'wrong.mbxrecovery',db_path=a)
  target=Path(self.t.name)/'rwb'/'box.db'; target.parent.mkdir()
  with self.assertRaises(PermissionError): restore_recovery_kit(kit['path'],'MBR1-AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH',db_path=target)
  doc=json.loads(Path(kit['path']).read_text(encoding='utf-8')); blob=doc['encrypted_identity']; doc['encrypted_identity']=blob[:-2]+('AA' if blob[-2:]!='AA' else 'BB')
  bad=Path(self.t.name)/'tampered.mbxrecovery'; bad.write_text(json.dumps(doc),encoding='utf-8')
  with self.assertRaises((PermissionError,ValueError,Exception)): restore_recovery_kit(bad,kit['recovery_code'],db_path=target)

 def test_recovery_replacement_protects_nonempty_box(self):
  from memorybox.crypto import public_identity
  from memorybox.recovery import create_recovery_kit, restore_recovery_kit
  a=Path(self.t.name)/'rpa'/'box.db'; b=Path(self.t.name)/'rpb'/'box.db'; a.parent.mkdir(); b.parent.mkdir()
  public_identity(a); kit=create_recovery_kit(Path(self.t.name)/'replace.mbxrecovery',db_path=a)
  public_identity(b); save_memory('local memory before disaster recovery',db_path=b)
  with self.assertRaises(FileExistsError): restore_recovery_kit(kit['path'],kit['recovery_code'],db_path=b)
  r=restore_recovery_kit(kit['path'],kit['recovery_code'],replace_existing=True,db_path=b)
  self.assertTrue(r['replaced']); self.assertTrue(Path(r['backup_path']).exists()); self.assertEqual(get_memory('M000001',b)['content'],'local memory before disaster recovery')

 def test_recovery_file_can_be_backed_up_to_baidu_without_code(self):
  from memorybox.recovery import create_recovery_kit, backup_recovery_file_to_sync
  from memorybox.sync import configure_sync_folder
  db=Path(self.t.name)/'cloudrec'/'box.db'; db.parent.mkdir(); shared=Path(self.t.name)/'BaiduNetdisk'
  kit=create_recovery_kit(Path(self.t.name)/'cloud.mbxrecovery',db_path=db)
  ep=configure_sync_folder(shared,provider='baidu-netdisk',db_path=db)
  r=backup_recovery_file_to_sync(kit['path'],ep['endpoint_id'],db_path=db)
  self.assertTrue(Path(r['path']).exists()); self.assertFalse(r['recovery_code_stored'])
  self.assertNotIn(kit['recovery_code'],Path(r['path']).read_text(encoding='utf-8'))

 def test_recovery_events_schema_and_status(self):
  from memorybox.recovery import create_recovery_kit, recovery_status
  db=Path(self.t.name)/'status'/'box.db'; db.parent.mkdir(); st0=recovery_status(db); self.assertEqual(st0['recovery_kits_created'],0)
  create_recovery_kit(Path(self.t.name)/'status.mbxrecovery',db_path=db); st=recovery_status(db); self.assertEqual(st['recovery_kits_created'],1); self.assertIsNotNone(st['last_recovery_event'])

 def test_recovery_code_verification_drill_does_not_replace_identity(self):
  from memorybox.crypto import public_identity
  from memorybox.recovery import create_recovery_kit, verify_recovery_kit
  before=public_identity(self.db); kitp=Path(self.t.name)/'safe.mbxrecovery'
  kit=create_recovery_kit(kitp,db_path=self.db)
  out=verify_recovery_kit(kitp,kit['recovery_code'],db_path=self.db)
  self.assertTrue(out['ok']); self.assertTrue(out['matches_current_identity']); self.assertEqual(public_identity(self.db)['fingerprint'],before['fingerprint'])
  raw=kitp.read_bytes(); self.assertNotIn(kit['recovery_code'].encode(),raw)
  with self.assertRaises(PermissionError): verify_recovery_kit(kitp,'MBR1-AAAA-AAAA-AAAA-AAAA-AAAA-AAAA-AAAA-AAAA',db_path=self.db)

 def test_automatic_insurance_encrypts_complete_library_and_verifies(self):
  from memorybox.attachments import add_attachment
  from memorybox.insurance import configure_insurance, run_insurance_backup, verify_latest_insurance
  from memorybox.sync import configure_sync_folder
  shared=Path(self.t.name)/'BaiduNetdisk'; ep=configure_sync_folder(shared,provider='baidu-netdisk',db_path=self.db)
  m=save_memory('highly secret CRAB insurance memory',db_path=self.db)
  f=Path(self.t.name)/'secret.csv'; f.write_text('secret,ast\nCRAB,42\n',encoding='utf-8'); add_attachment(m['memory_id'],f,db_path=self.db)
  configure_insurance(ep['endpoint_id'],interval_hours=24,retention=3,db_path=self.db)
  r=run_insurance_backup(force=True,db_path=self.db); self.assertTrue(r['encrypted']); self.assertEqual(r['memory_count'],1); self.assertEqual(r['attachment_count'],1)
  enc=Path(r['path']); self.assertTrue(enc.exists()); raw=enc.read_bytes(); self.assertNotIn(b'highly secret CRAB insurance memory',raw); self.assertNotIn(b'CRAB,42',raw)
  v=verify_latest_insurance(self.db); self.assertTrue(v['ok']); self.assertEqual(v['memory_count'],1); self.assertEqual(v['attachment_count'],1); self.assertTrue(v['database_snapshot_included']); self.assertTrue(v['attachment_index_included']); self.assertEqual(v['database_check'],'ok')

 def test_disaster_readiness_green_after_offsite_recovery_and_backup(self):
  from memorybox.insurance import configure_insurance, run_insurance_backup, disaster_readiness
  from memorybox.recovery import create_recovery_kit, verify_recovery_kit, backup_recovery_file_to_sync
  from memorybox.sync import configure_sync_folder
  shared=Path(self.t.name)/'BaiduNetdisk'; ep=configure_sync_folder(shared,provider='baidu-netdisk',db_path=self.db)
  save_memory('insured memory',db_path=self.db)
  kitp=Path(self.t.name)/'recovery.mbxrecovery'; kit=create_recovery_kit(kitp,db_path=self.db)
  backup_recovery_file_to_sync(kitp,ep['endpoint_id'],db_path=self.db)
  verify_recovery_kit(kitp,kit['recovery_code'],db_path=self.db)
  configure_insurance(ep['endpoint_id'],interval_hours=24,retention=3,deep_verify=True,db_path=self.db); run_insurance_backup(force=True,db_path=self.db)
  h=disaster_readiness(deep=True,db_path=self.db); self.assertEqual(h['status'],'GREEN',h); self.assertTrue(h['recoverable_if_recovery_code_available'])

 def test_disaster_readiness_red_on_missing_attachment(self):
  from memorybox.attachments import add_attachment
  from memorybox.insurance import disaster_readiness
  m=save_memory('memory with file',db_path=self.db); f=Path(self.t.name)/'x.txt'; f.write_text('x'); a=add_attachment(m['memory_id'],f,db_path=self.db)
  Path(a['local_path']).unlink()
  h=disaster_readiness(db_path=self.db); self.assertEqual(h['status'],'RED'); self.assertGreater(h['attachments']['missing_count'],0)

 def test_insurance_disaster_restore_on_new_machine_after_identity_recovery(self):
  from memorybox.insurance import configure_insurance, run_insurance_backup, restore_insurance_snapshot
  from memorybox.recovery import create_recovery_kit, restore_recovery_kit
  from memorybox.sync import configure_sync_folder
  src=Path(self.t.name)/'source/box.db'; dst=Path(self.t.name)/'dest/box.db'; shared=Path(self.t.name)/'BaiduNetdisk'
  save_memory('disaster-restorable complete library',title='Disaster demo',db_path=src)
  ep=configure_sync_folder(shared,provider='baidu-netdisk',db_path=src)
  kitp=Path(self.t.name)/'source-recovery.mbxrecovery'; kit=create_recovery_kit(kitp,db_path=src)
  configure_insurance(ep['endpoint_id'],deep_verify=True,db_path=src); backup=run_insurance_backup(force=True,db_path=src)
  restore_recovery_kit(kitp,kit['recovery_code'],db_path=dst)
  r=restore_insurance_snapshot(backup['path'],db_path=dst)
  self.assertEqual(r['import']['imported'],1); self.assertEqual(get_memory('M000001',dst)['title'],'Disaster demo')

 def test_insurance_retention_and_due_skip(self):
  from memorybox.insurance import configure_insurance, run_insurance_backup
  from memorybox.sync import configure_sync_folder
  shared=Path(self.t.name)/'OneDrive'; ep=configure_sync_folder(shared,provider='onedrive',db_path=self.db)
  save_memory('retention memory',db_path=self.db); configure_insurance(ep['endpoint_id'],interval_hours=24,retention=2,db_path=self.db)
  first=run_insurance_backup(force=True,db_path=self.db); skipped=run_insurance_backup(force=False,db_path=self.db)
  self.assertTrue(first['ok']); self.assertTrue(skipped['skipped']); self.assertEqual(skipped['reason'],'not_due')
  for _ in range(3): run_insurance_backup(force=True,db_path=self.db)
  files=list((shared/'MemoryBoxSync'/'insurance').glob('*/*.mboxenc')); self.assertEqual(len(files),2)

if __name__=='__main__': unittest.main()

# v0.14 Project Workspace + intelligent local retrieval
class ProjectWorkspaceT(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.db=Path(self.t.name)/'box.db'
 def tearDown(self): self.t.cleanup()
 def test_v14_project_workspace_resume(self):
  from memorybox.projects import create_project, add_memory_to_project, get_project, update_project, project_resume
  a=save_memory('CRAB Batch 2 completed; next verify Tier-A evidence',title='CRAB Stage 2 result',tags=['CRAB','Tier-A'],db_path=self.db)
  b=save_memory('Prepare JGAR manuscript discussion after audit',title='JGAR revision plan',tags=['CRAB','JGAR'],db_path=self.db)
  p=create_project('CRAB manuscript',summary='Move audited CRAB analysis toward publication',current_state='Stage 2 complete',next_action='Verify Tier-A evidence',db_path=self.db)
  add_memory_to_project(p['project_id'],a['memory_id'],role='evidence',db_path=self.db); add_memory_to_project(p['project_id'],b['memory_id'],role='next-step',db_path=self.db)
  update_project(p['project_id'],next_action='Draft results after Tier-A verification',db_path=self.db)
  got=get_project(p['project_id'],db_path=self.db); self.assertEqual(got['memory_count'],2); self.assertEqual(len(got['memories']),2)
  r=project_resume(p['project_id'],db_path=self.db); self.assertIn('Memory Box Project Resume',r['context']); self.assertIn('CRAB manuscript',r['context']); self.assertIn('Draft results',r['context']); self.assertGreaterEqual(len(r['memory_ids']),1)

 def test_v14_smart_search_ranking_and_project_filter(self):
  from memorybox.projects import create_project, add_memory_to_project
  from memorybox.retrieval import smart_search
  exact=save_memory('Important evidence about a resistance mechanism',title='OmpA docking mechanism',tags=['OmpA'],db_path=self.db)
  other=save_memory('OmpA appears once in a long generic note about many unrelated topics',title='General notes',db_path=self.db)
  unrelated=save_memory('Travel planning and hotel notes',title='Trip',db_path=self.db)
  hits=smart_search('OmpA docking mechanism',db_path=self.db,limit=10)
  self.assertEqual(hits[0]['memory_id'],exact['memory_id']); self.assertGreater(hits[0]['retrieval_score'],hits[-1]['retrieval_score'] if len(hits)>1 else 0)
  p=create_project('Mechanism paper',db_path=self.db); add_memory_to_project(p['project_id'],other['memory_id'],db_path=self.db)
  phits=smart_search('OmpA',project_id=p['project_id'],db_path=self.db); self.assertEqual([x['memory_id'] for x in phits],[other['memory_id']])
  self.assertNotIn(unrelated['memory_id'],[x['memory_id'] for x in hits])

 def test_v14_transfer_preserves_projects_and_links(self):
  from memorybox.projects import create_project, add_memory_to_project, get_project
  from memorybox.transfer import export_transfer_bundle, import_transfer_bundle, inspect_transfer_bundle
  src=Path(self.t.name)/'src.db'; dst=Path(self.t.name)/'dst.db'
  m=save_memory('portable project memory',title='Project decision',db_path=src)
  p=create_project('Portable Project',summary='Cross-device project workspace',current_state='ready',next_action='continue',db_path=src)
  add_memory_to_project(p['project_id'],m['memory_id'],role='decision',db_path=src)
  pack=Path(self.t.name)/'project.mboxpack'; ex=export_transfer_bundle(pack,memory_ids=[m['memory_id']],db_path=src)
  self.assertEqual(ex['project_count'],1); self.assertEqual(inspect_transfer_bundle(pack)['project_count'],1)
  r=import_transfer_bundle(pack,db_path=dst); self.assertEqual(r['projects_imported'],1)
  pid=r['project_mapping'][p['project_id']]; got=get_project(pid,db_path=dst); self.assertEqual(got['name'],'Portable Project'); self.assertEqual(got['memory_count'],1); self.assertEqual(got['memories'][0]['role'],'decision')
  r2=import_transfer_bundle(pack,db_path=dst); self.assertEqual(r2['projects_imported'],0); self.assertGreaterEqual(r2['projects_skipped'],1)


# v0.16 local vector retrieval, dedup review and derived project continuity
class SemanticMemoryT(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.db=Path(self.t.name)/'box.db'
 def tearDown(self): self.t.cleanup()

 def test_v15_vector_cache_and_search(self):
  from memorybox.semantic import backend_status, rebuild_vectors, vector_search
  a=save_memory('OmpA protein docking with berberine and molecular dynamics validation',title='OmpA docking mechanism',summary='Docking and MD mechanism',db_path=self.db)
  save_memory('Hotel itinerary and museum opening times in Datong',title='Datong trip',db_path=self.db)
  st=backend_status(); self.assertTrue(st['local_only'])
  built=rebuild_vectors(db_path=self.db); self.assertEqual(built['total'],2); self.assertGreaterEqual(built['dimension'],1)
  hits=vector_search('protein docking mechanism molecular dynamics',db_path=self.db,limit=2)
  self.assertEqual(hits[0]['memory_id'],a['memory_id']); self.assertGreater(hits[0]['vector_score'],hits[-1]['vector_score'])

 def test_v15_smart_search_exposes_vector_evidence(self):
  from memorybox.retrieval import smart_search
  a=save_memory('carbapenem resistance OmpA membrane mechanism and docking evidence',title='CRAB OmpA',db_path=self.db)
  hits=smart_search('OmpA membrane docking',db_path=self.db)
  self.assertEqual(hits[0]['memory_id'],a['memory_id']); self.assertIn('vector_score',hits[0]); self.assertGreater(hits[0]['vector_score'],0)

 def test_v15_dedup_suggests_but_does_not_mutate(self):
  from memorybox.dedup import find_duplicates
  a=save_memory('Final decision: use feature-specific observation masks for the CRAB audit.',title='CRAB audit decision',summary='Use feature-specific masks',db_path=self.db)
  b=save_memory('Final decision: use feature-specific observation masks for the CRAB audit.',title='CRAB audit decision copy',summary='Use feature-specific masks',db_path=self.db)
  xs=find_duplicates(a['memory_id'],db_path=self.db,threshold=.7)
  self.assertTrue(xs); self.assertEqual(xs[0]['memory_id'],b['memory_id']); self.assertTrue(xs[0]['exact'])
  self.assertFalse(get_memory(a['memory_id'],self.db)['archived']); self.assertFalse(get_memory(b['memory_id'],self.db)['archived'])

 def test_v15_explicit_dedup_merge_preserves_projects(self):
  from memorybox.dedup import merge_duplicate_memories
  from memorybox.projects import create_project, add_memory_to_project, get_project
  a=save_memory('same core evidence alpha',title='A',db_path=self.db); b=save_memory('same core evidence alpha',title='B',db_path=self.db)
  p=create_project('Evidence Project',db_path=self.db); add_memory_to_project(p['project_id'],a['memory_id'],role='evidence',db_path=self.db); add_memory_to_project(p['project_id'],b['memory_id'],role='evidence',db_path=self.db)
  m=merge_duplicate_memories([a['memory_id'],b['memory_id']],archive_sources=False,db_path=self.db)
  self.assertIn(p['project_id'],m['projects_preserved']); self.assertEqual(get_project(p['project_id'],db_path=self.db)['memory_count'],3)
  self.assertFalse(get_memory(a['memory_id'],self.db)['archived'])

 def test_v15_project_auto_insights_never_overwrite_manual_fields(self):
  from memorybox.projects import create_project, add_memory_to_project, get_project, refresh_project_insights
  p=create_project('CRAB paper',summary='Curated human summary',current_state='',next_action='',db_path=self.db)
  m=save_memory('Tier-A evidence verified. Next step draft the Results section.',title='Audit update',summary='Tier-A verified; next step draft Results',db_path=self.db)
  add_memory_to_project(p['project_id'],m['memory_id'],role='next-step',db_path=self.db)
  got=refresh_project_insights(p['project_id'],db_path=self.db)
  self.assertEqual(got['summary'],'Curated human summary'); self.assertTrue(got['auto_summary']); self.assertTrue(got['auto_next_action']); self.assertTrue(got['auto_updated_at'])

class PlatformV16CoreT(unittest.TestCase):
 def test_v16_model_status_is_safe_without_optional_runtime(self):
  from memorybox.model_manager import model_status, DEFAULT_MODEL_ID, DEFAULT_MODEL_DIM
  with tempfile.TemporaryDirectory() as td:
   st=model_status(Path(td))
   self.assertEqual(st['model_id'],DEFAULT_MODEL_ID)
   self.assertEqual(st['dimension'],DEFAULT_MODEL_DIM)
   self.assertTrue(st['local_only_after_install'])
   self.assertTrue(st['download_is_explicit'])

 def test_v16_webview_platform_selection(self):
  from memorybox.desktop import _webview_gui_for_platform
  self.assertEqual(_webview_gui_for_platform('Windows'),'edgechromium')
  self.assertEqual(_webview_gui_for_platform('Darwin'),'cocoa')
  self.assertIsNone(_webview_gui_for_platform('Linux'))

 def test_v16_mac_launch_agent_plist_is_per_user_and_minimized(self):
  import plistlib
  from memorybox.desktop import _mac_launch_agent_plist
  doc=plistlib.loads(_mac_launch_agent_plist('/Applications/MemoryBox.app/Contents/MacOS/MemoryBox'))
  self.assertEqual(doc['Label'],'com.memorybox.desktop')
  self.assertTrue(doc['RunAtLoad'])
  self.assertIn('--minimized',doc['ProgramArguments'])
