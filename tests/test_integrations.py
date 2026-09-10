import json, os, sys, tempfile, threading, unittest, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import memorybox.agents as agents
from memorybox.webapp import Handler
from http.server import ThreadingHTTPServer

class T(unittest.TestCase):
 def test_json_agent_configs(self):
  with tempfile.TemporaryDirectory() as td:
   old=agents.Path.home
   agents.Path.home=classmethod(lambda cls: Path(td))
   try:
    for key,rel in [('cursor','.cursor/mcp.json'),('gemini-cli','.gemini/settings.json'),('kimi-code','.kimi-code/mcp.json')]:
     r=agents.connect_agent(key); self.assertTrue(r['connected']); d=json.loads((Path(td)/rel).read_text()); self.assertIn('memory-box',d['mcpServers'])
   finally: agents.Path.home=old
 def test_web_health_and_html(self):
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=td
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    health=json.loads(urllib.request.urlopen(base+'/api/health').read()); self.assertTrue(health['ok'])
    html=urllib.request.urlopen(base+'/').read().decode(); self.assertIn('Memory Box',html); self.assertNotIn('__CATEGORIES__',html)
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old

 def test_quick_save_browser_bridge(self):
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=td
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    body=json.dumps({'text':'CRAB biofilm discussion from Kimi Web','agent':'Kimi Web','url':'https://www.kimi.com/chat/test','tags':['browser-selection']}).encode()
    req=urllib.request.Request(base+'/api/quick-save',data=body,headers={'Content-Type':'application/json'},method='POST')
    card=json.loads(urllib.request.urlopen(req).read())
    self.assertEqual(card['memory_id'],'M000001'); self.assertEqual(card['source_agent'],'Kimi Web'); self.assertEqual(card['source_uri'],'https://www.kimi.com/chat/test')
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old

 def test_existing_agent_config_is_backed_up(self):
  with tempfile.TemporaryDirectory() as td:
   old=agents.Path.home; agents.Path.home=classmethod(lambda cls: Path(td))
   try:
    cfg=Path(td)/'.cursor/mcp.json'; cfg.parent.mkdir(parents=True); cfg.write_text(json.dumps({'mcpServers':{'keep-me':{'command':'x'}}}),encoding='utf-8')
    agents.connect_agent('cursor')
    data=json.loads(cfg.read_text(encoding='utf-8')); self.assertIn('keep-me',data['mcpServers']); self.assertIn('memory-box',data['mcpServers'])
    self.assertTrue(list(cfg.parent.glob('mcp.json.memorybox.bak.*')))
   finally: agents.Path.home=old

 def test_malformed_agent_config_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as td:
   old=agents.Path.home; agents.Path.home=classmethod(lambda cls: Path(td))
   try:
    cfg=Path(td)/'.cursor/mcp.json'; cfg.parent.mkdir(parents=True); cfg.write_text('{broken',encoding='utf-8')
    with self.assertRaises(ValueError): agents.connect_agent('cursor')
    self.assertEqual(cfg.read_text(encoding='utf-8'),'{broken')
   finally: agents.Path.home=old

 def test_server_command_avoids_pythonw_for_stdio(self):
  with tempfile.TemporaryDirectory() as td:
   td=Path(td); pyw=td/'pythonw.exe'; py=td/'python.exe'; pyw.write_bytes(b''); py.write_bytes(b'')
   old=agents.sys.executable; agents.sys.executable=str(pyw)
   try:
    cmd,args=agents.server_command(); self.assertEqual(Path(cmd),py); self.assertEqual(args[-1],'mcp')
   finally: agents.sys.executable=old

 def test_browser_extension_v05_contract(self):
  ext=ROOT/'integrations'/'browser-extension'
  manifest=json.loads((ext/'manifest.json').read_text(encoding='utf-8'))
  self.assertEqual(manifest['version'],'0.13.0')
  self.assertIn('scripting',manifest['permissions'])
  self.assertIn('save-selection',manifest['commands'])
  bg=(ext/'background.js').read_text(encoding='utf-8')
  self.assertIn("save-conversation",bg)
  self.assertIn("resume-to-chat",bg)
  self.assertIn("url: tab?.url", bg); self.assertIn("恢复到当前聊天", (ext/'popup.html').read_text(encoding='utf-8')); self.assertIn('chatFiles', (ext/'popup.html').read_text(encoding='utf-8')); self.assertIn('/attachments', (ext/'popup.js').read_text(encoding='utf-8'))

 def test_web_export_import_transfer(self):
  import base64
  from memorybox.db import save_memory
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=td
   save_memory('web transferable conversation')
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    body=json.dumps({}).encode(); req=urllib.request.Request(base+'/api/export-pack',data=body,headers={'Content-Type':'application/json'},method='POST')
    ex=json.loads(urllib.request.urlopen(req).read()); self.assertEqual(ex['memory_count'],1)
    raw=urllib.request.urlopen(base+'/api/exports/'+ex['filename']).read(); self.assertGreater(len(raw),100)
    body=json.dumps({'filename':'copy.mboxpack','data_base64':base64.b64encode(raw).decode()}).encode()
    req=urllib.request.Request(base+'/api/import-pack',data=body,headers={'Content-Type':'application/json'},method='POST')
    im=json.loads(urllib.request.urlopen(req).read()); self.assertGreaterEqual(im['skipped'],1)
    replay=urllib.request.urlopen(base+'/api/replay/'+im['transfer_id']).read().decode(); self.assertIn('Memory Box Replay',replay)
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old

 def test_web_attachment_upload_download(self):
  import base64
  from memorybox.db import save_memory
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=td
   m=save_memory('chat with pdf attachment')
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    raw=b'%PDF-1.4\nattachment-demo'
    body=json.dumps({'filename':'paper.pdf','mime_type':'application/pdf','data_base64':base64.b64encode(raw).decode()}).encode()
    req=urllib.request.Request(base+f'/api/memories/{m["memory_id"]}/attachments',data=body,headers={'Content-Type':'application/json'},method='POST')
    a=json.loads(urllib.request.urlopen(req).read()); self.assertEqual(a['original_name'],'paper.pdf')
    got=urllib.request.urlopen(base+f'/api/attachments/{a["sha256"]}?memory_id={m["memory_id"]}').read(); self.assertEqual(got,raw)
    card=json.loads(urllib.request.urlopen(base+f'/api/memories/{m["memory_id"]}').read()); self.assertEqual(len(card['attachments']),1)
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old


 def test_web_sync_baidu_endpoint(self):
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=str(Path(td)/'home')
   shared=Path(td)/'BaiduNetdisk'
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    body=json.dumps({'path':str(shared),'provider':'baidu-netdisk','name':'百度测试'}).encode(); req=urllib.request.Request(base+'/api/sync/add',data=body,headers={'Content-Type':'application/json'},method='POST')
    ep=json.loads(urllib.request.urlopen(req).read()); self.assertEqual(ep['provider'],'baidu-netdisk'); self.assertTrue(ep['e2ee']); self.assertEqual(ep['encryption_mode'],'e2ee'); self.assertTrue((shared/'MemoryBoxSync').exists())
    eps=json.loads(urllib.request.urlopen(base+'/api/sync/endpoints').read()); self.assertEqual(len(eps),1); self.assertEqual(eps[0]['provider_label'],'百度网盘 / Baidu Netdisk')
    ident=json.loads(urllib.request.urlopen(base+'/api/device/identity').read()); self.assertIn('fingerprint',ident)
    sec=json.loads(urllib.request.urlopen(base+'/api/sync/security?endpoint_id='+ep['endpoint_id']).read()); self.assertTrue(sec['e2ee'])
    html=urllib.request.urlopen(base+'/').read().decode(); self.assertIn('设备同步',html); self.assertIn('百度网盘',html); self.assertIn('端到端加密',html)
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old


 def test_mcp_device_sync_tools_present(self):
  from memorybox.mcp_server import TOOLS
  names={x['name'] for x in TOOLS}
  self.assertTrue({'memory_sync_add_folder','memory_sync_endpoints','memory_sync_detect','memory_sync_send','memory_sync_pull','memory_sync_devices','memory_lan_pair','memory_lan_discover','memory_lan_send_pack','memory_device_identity','memory_sync_trust_device','memory_sync_untrust_device','memory_sync_security','memory_sync_set_encryption'} <= names)

 def test_baidu_windows_setup_helper_is_packaged(self):
  ps=(ROOT/'Install-MemoryBox.ps1').read_text(encoding='utf-8')
  self.assertIn('Add-Baidu-Netdisk-Sync.cmd',ps)
  helper=(ROOT/'Add-Baidu-Netdisk-Sync.ps1').read_text(encoding='utf-8')
  self.assertIn('--provider baidu-netdisk',helper)
  self.assertNotIn('Cookie=',helper)


 def test_windows_installer_bootstraps_e2ee_runtime(self):
  ps=(ROOT/'Install-MemoryBox.ps1').read_text(encoding='utf-8')
  self.assertIn('cryptography>=46,<47',ps)
  self.assertIn('bootstrap.pypa.io/get-pip.py',ps)
  self.assertIn('.mboxenc',ps)
  self.assertIn('identity | Out-Null',ps)

 def test_windows_release_workflow_installs_project_dependencies(self):
  wf=(ROOT/'.github/workflows/build-windows.yml').read_text(encoding='utf-8')
  self.assertIn('python -m pip install --upgrade pip pyinstaller ".[desktop]"',wf)
  self.assertIn('pyinstaller',wf)

 def test_transfer_association_includes_encrypted_packages(self):
  ps=(ROOT/'Register-Transfer-Association.ps1').read_text(encoding='utf-8')
  cmd=(ROOT/'MemoryBox-Import.cmd').read_text(encoding='utf-8')
  self.assertIn('.mboxenc',ps); self.assertIn('import-encrypted',cmd)


 def test_web_recovery_v10_surface(self):
  import base64
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=td
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    st=json.loads(urllib.request.urlopen(base+'/api/recovery/status').read()); self.assertIn('fingerprint',st)
    req=urllib.request.Request(base+'/api/recovery/create',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
    kit=json.loads(urllib.request.urlopen(req).read()); self.assertTrue(kit['recovery_code'].startswith('MBR1-')); self.assertTrue(kit['filename'].endswith('.mbxrecovery'))
    raw=urllib.request.urlopen(base+kit['download_url']).read(); self.assertGreater(len(raw),100); self.assertNotIn(kit['recovery_code'].encode(),raw)
    html=urllib.request.urlopen(base+'/').read().decode(); self.assertIn('灾难恢复',html); self.assertIn('创建恢复保险箱',html); self.assertIn('.mbxrecovery',html)
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old

 def test_v10_recovery_is_not_exposed_as_mcp_secret_tool(self):
  from memorybox.mcp_server import TOOLS
  names={x['name'] for x in TOOLS}
  self.assertFalse(any(n.startswith('memory_recovery_create') or n.startswith('memory_recovery_restore') for n in names))
  root=(ROOT/'SKILL.md').read_text(encoding='utf-8'); self.assertIn('Never ask the user to paste a recovery code',root)

 def test_windows_v10_recovery_association(self):
  ps=(ROOT/'Register-Transfer-Association.ps1').read_text(encoding='utf-8')
  installer=(ROOT/'Install-MemoryBox.ps1').read_text(encoding='utf-8')
  helper=(ROOT/'MemoryBox-Recover.cmd').read_text(encoding='utf-8')
  self.assertIn('.mbxrecovery',ps); self.assertIn('MemoryBox-Recover.cmd',ps)
  self.assertIn('.mbxrecovery',installer); self.assertIn('MemoryBox-Recover.cmd',installer)
  self.assertIn('recovery-restore',helper); self.assertNotIn('--code ',helper)


 def test_v11_insurance_mcp_tools_present_without_recovery_secret(self):
  from memorybox.mcp_server import TOOLS
  names={x['name'] for x in TOOLS}
  self.assertTrue({'memory_insurance_status','memory_insurance_health','memory_insurance_run','memory_insurance_verify_latest'} <= names)
  self.assertFalse(any('recovery_code' in json.dumps(x) for x in TOOLS if x['name'].startswith('memory_insurance_')))

 def test_v11_web_insurance_surface(self):
  from memorybox.db import save_memory
  from memorybox.sync import configure_sync_folder
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=td
   configure_sync_folder(Path(td)/'BaiduNetdisk',provider='baidu-netdisk')
   save_memory('web insurance memory')
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    h=json.loads(urllib.request.urlopen(base+'/api/insurance/health').read()); self.assertIn(h['status'],{'RED','YELLOW','GREEN'})
    html=urllib.request.urlopen(base+'/').read().decode(); self.assertIn('自动保险',html); self.assertIn('灾难恢复自检',html); self.assertIn('恢复码自检',html)
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old


 def test_v11_windows_auto_insurance_task_is_opt_in_and_packaged(self):
  installer=(ROOT/'Install-MemoryBox.ps1').read_text(encoding='utf-8')
  enable=(ROOT/'Enable-Auto-Insurance.ps1').read_text(encoding='utf-8')
  runner=(ROOT/'MemoryBox-Auto-Insurance.cmd').read_text(encoding='utf-8')
  self.assertIn('Enable-Auto-Insurance.cmd',installer); self.assertIn('Memory Box - 启用自动保险',installer)
  self.assertIn('/SC HOURLY',enable); self.assertIn('insurance-run',runner)
  # Installer creates only a shortcut; it must not silently register the scheduled task.
  self.assertNotIn('/Create /TN "Memory Box Automatic Insurance"',installer)

 def test_v13_apple_inspired_desktop_surface(self):
  with tempfile.TemporaryDirectory() as td:
   old=os.environ.get('MEMORYBOX_HOME'); os.environ['MEMORYBOX_HOME']=td
   srv=ThreadingHTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
   try:
    base=f'http://127.0.0.1:{srv.server_address[1]}'
    html=urllib.request.urlopen(base+'/').read().decode()
    for token in ['Private AI memory hub','data-view="home"','自动保险','设备同步','灾难恢复','memorybox-theme','prefers-color-scheme:dark','v0.13.0']:
     self.assertIn(token,html)
    self.assertNotIn('__VERSION__',html)
   finally:
    srv.shutdown(); srv.server_close()
    if old is None: os.environ.pop('MEMORYBOX_HOME',None)
    else: os.environ['MEMORYBOX_HOME']=old


 def test_v13_native_desktop_contract(self):
  desktop=(ROOT/'memorybox'/'desktop.py').read_text(encoding='utf-8')
  pyproject=(ROOT/'pyproject.toml').read_text(encoding='utf-8')
  ui=(ROOT/'memorybox'/'ui.py').read_text(encoding='utf-8')
  for token in ['pystray','run_detached','minimize_to_tray','set_start_on_login','DOMEventHandler','pywebviewFullPath']:
   self.assertIn(token,desktop)
  self.assertIn('pywebview>=6.1,<7',pyproject); self.assertIn('pystray>=0.19.5,<0.20',pyproject)
  self.assertIn('window.pywebview',ui); self.assertIn('开机启动',ui); self.assertIn('最小化到托盘',ui)

 def test_v13_windows_build_creates_desktop_and_cli_exes(self):
  wf=(ROOT/'.github/workflows/build-windows.yml').read_text(encoding='utf-8')
  self.assertIn('--windowed',wf); self.assertIn('--name MemoryBox',wf)
  self.assertIn('--name MemoryBox-CLI',wf); self.assertIn('memorybox_desktop.py',wf)
  mcp=(ROOT/'MemoryBox-MCP.cmd').read_text(encoding='utf-8'); self.assertIn('MemoryBox-CLI.exe',mcp)
  imp=(ROOT/'MemoryBox-Import.cmd').read_text(encoding='utf-8'); self.assertIn('MemoryBox-CLI.exe',imp)

 def test_v13_desktop_settings_roundtrip(self):
  from memorybox.desktop import load_desktop_settings, save_desktop_settings
  with tempfile.TemporaryDirectory() as td:
   home=Path(td); d=load_desktop_settings(home); self.assertTrue(d['minimize_to_tray'])
   save_desktop_settings({'minimize_to_tray':False,'notifications':False},home)
   d=load_desktop_settings(home); self.assertFalse(d['minimize_to_tray']); self.assertFalse(d['notifications'])

 def test_v13_desktop_open_transfer_package(self):
  from memorybox.desktop import process_open_path
  from memorybox.transfer import export_transfer_bundle
  from memorybox.db import save_memory, get_memory
  with tempfile.TemporaryDirectory() as td:
   src=Path(td)/'src.db'; dst=Path(td)/'dst.db'; pack=Path(td)/'desktop.mboxpack'
   save_memory('desktop import memory',db_path=src); export_transfer_bundle(pack,db_path=src)
   r=process_open_path(pack,db_path=dst); self.assertEqual(r['kind'],'transfer')
   self.assertEqual(get_memory('M000001',dst)['content'],'desktop import memory')

 def test_v13_recovery_file_never_auto_consumes_secret(self):
  from memorybox.desktop import process_open_path
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'test.mbxrecovery'; p.write_bytes(b'placeholder')
   r=process_open_path(p); self.assertEqual(r['kind'],'recovery'); self.assertTrue(r['requires_user_secret'])

if __name__=='__main__': unittest.main()
