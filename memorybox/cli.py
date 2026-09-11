from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .agents import connect_agent, connect_all_detected, scan_agents
from .attachments import add_attachment, list_attachments, remove_attachment
from .db import append_memory, bundle_by_query, compose_context, get_memory, import_uam_json, init_db, list_memories, merge_memories, save_memory
from .mcp_server import run_stdio
from .transfer import export_transfer_bundle, import_transfer_bundle, inspect_transfer_bundle
from .sync import configure_sync_folder, detect_sync_folders, list_sync_devices, list_sync_endpoints, publish_to_sync, receive_from_sync, remove_sync_endpoint, sync_all, sync_now, trust_sync_device, revoke_sync_device, sync_security_status, set_sync_encryption
from .lan import discover_peers, pairing_status, send_pack, start_pairing, stop_pairing
from .webapp import serve
from .crypto import public_identity, inspect_encrypted_file, decrypt_file_for_local_device
from .recovery import backup_recovery_file_to_sync, create_recovery_kit, inspect_recovery_kit, recovery_status, restore_recovery_kit, verify_recovery_kit
from .insurance import configure_insurance, disable_insurance, insurance_settings, run_insurance_backup, disaster_readiness, verify_latest_insurance, restore_insurance_snapshot, restore_latest_insurance, list_insurance_snapshots
from .projects import create_project, list_projects, get_project, update_project, add_memory_to_project, remove_memory_from_project, project_resume, suggest_project_memories, refresh_project_insights
from .retrieval import smart_search
from .semantic import backend_status, rebuild_vectors, vector_search
from .model_manager import model_status, install_model, uninstall_model
from .dedup import find_duplicates, scan_duplicates, merge_duplicate_memories


def main(argv=None):
 raw = list(sys.argv[1:] if argv is None else argv)
 if raw:
  candidate=Path(raw[0]).expanduser()
  if candidate.exists() and (candidate.suffix.lower() in {'.mboxpack','.mboxenc','.mbxrecovery'} or (candidate.is_dir() and (candidate/'manifest.json').exists())):
   if candidate.suffix.lower()=='.mbxrecovery': raw=['recovery-restore',str(candidate),*raw[1:]]
   else: raw=[('import-encrypted' if candidate.suffix.lower()=='.mboxenc' else 'import-pack'),str(candidate),'--open',*raw[1:]]
 argv=raw
 p=argparse.ArgumentParser(prog='memorybox'); s=p.add_subparsers(dest='cmd')
 s.add_parser('app'); desk=s.add_parser('desktop'); desk.add_argument('paths',nargs='*'); desk.add_argument('--minimized',action='store_true'); s.add_parser('mcp'); s.add_parser('agents'); s.add_parser('connect-all')
 smart=s.add_parser('smart-search'); smart.add_argument('query'); smart.add_argument('--project'); smart.add_argument('--category'); smart.add_argument('--limit',type=int,default=20)
 sem=s.add_parser('semantic-status')
 ms=s.add_parser('model-status')
 mi=s.add_parser('model-install'); mi.add_argument('--from-dir',dest='source_dir')
 s.add_parser('model-remove')
 vr=s.add_parser('vectors-rebuild'); vr.add_argument('--id',dest='memory_ids',action='append',default=[])
 vs=s.add_parser('vector-search'); vs.add_argument('query'); vs.add_argument('--project'); vs.add_argument('--category'); vs.add_argument('--limit',type=int,default=20)
 df=s.add_parser('dedup-find'); df.add_argument('memory_id'); df.add_argument('--limit',type=int,default=12); df.add_argument('--threshold',type=float,default=0.72)
 ds=s.add_parser('dedup-scan'); ds.add_argument('--limit',type=int,default=100); ds.add_argument('--threshold',type=float,default=0.78)
 dm=s.add_parser('dedup-merge'); dm.add_argument('memory_ids',nargs='+'); dm.add_argument('--title'); dm.add_argument('--keep-sources',action='store_true')
 pc=s.add_parser('project-create'); pc.add_argument('name'); pc.add_argument('--summary',default=''); pc.add_argument('--current-state',default=''); pc.add_argument('--next-action',default=''); pc.add_argument('--status',default='active',choices=['active','paused','completed'])
 pl=s.add_parser('projects'); pl.add_argument('--status'); pl.add_argument('--limit',type=int,default=100)
 pg=s.add_parser('project-get'); pg.add_argument('project_id')
 pu=s.add_parser('project-update'); pu.add_argument('project_id'); pu.add_argument('--name'); pu.add_argument('--summary'); pu.add_argument('--current-state'); pu.add_argument('--next-action'); pu.add_argument('--status',choices=['active','paused','completed','archived'])
 pa=s.add_parser('project-add'); pa.add_argument('project_id'); pa.add_argument('memory_id'); pa.add_argument('--role',default='context')
 pr=s.add_parser('project-remove'); pr.add_argument('project_id'); pr.add_argument('memory_id')
 pres=s.add_parser('project-resume'); pres.add_argument('project_id'); pres.add_argument('--query',default=''); pres.add_argument('--limit',type=int,default=12)
 psug=s.add_parser('project-suggest'); psug.add_argument('project_id'); psug.add_argument('--limit',type=int,default=12)
 pref=s.add_parser('project-refresh'); pref.add_argument('project_id')
 s.add_parser('sync-endpoints'); s.add_parser('sync-detect'); s.add_parser('sync-all'); s.add_parser('lan-status'); s.add_parser('lan-discover'); s.add_parser('lan-stop'); s.add_parser('identity'); s.add_parser('recovery-status'); s.add_parser('insurance-status'); s.add_parser('insurance-disable')
 sf=s.add_parser('sync-add'); sf.add_argument('path'); sf.add_argument('--provider',default='generic-folder'); sf.add_argument('--name'); sf.add_argument('--no-auto-import',action='store_true'); sf.add_argument('--encryption-mode',default='e2ee',choices=['e2ee','legacy-plaintext'])
 sr=s.add_parser('sync-remove'); sr.add_argument('endpoint_id')
 ss=s.add_parser('sync-send'); ss.add_argument('endpoint_id'); ss.add_argument('--id',dest='memory_ids',action='append',default=[]); ss.add_argument('--query'); ss.add_argument('--category')
 sp=s.add_parser('sync-pull'); sp.add_argument('endpoint_id')
 sn=s.add_parser('sync-now'); sn.add_argument('endpoint_id'); sn.add_argument('--publish',action='store_true'); sn.add_argument('--id',dest='memory_ids',action='append',default=[]); sn.add_argument('--query'); sn.add_argument('--category')
 sd=s.add_parser('sync-devices'); sd.add_argument('endpoint_id')
 st=s.add_parser('sync-trust'); st.add_argument('endpoint_id'); st.add_argument('device_id'); st.add_argument('--fingerprint')
 su=s.add_parser('sync-untrust'); su.add_argument('endpoint_id'); su.add_argument('device_id')
 se=s.add_parser('sync-security'); se.add_argument('endpoint_id')
 sem=s.add_parser('sync-encryption'); sem.add_argument('endpoint_id'); sem.add_argument('mode',choices=['e2ee','legacy-plaintext'])
 lp=s.add_parser('lan-pair'); lp.add_argument('--port',type=int,default=0); lp.add_argument('--ttl',type=int,default=300)
 lsend=s.add_parser('lan-send'); lsend.add_argument('host'); lsend.add_argument('port',type=int); lsend.add_argument('code'); lsend.add_argument('package')
 c=s.add_parser('connect'); c.add_argument('agent')
 sv=s.add_parser('save'); sv.add_argument('content'); sv.add_argument('--title'); sv.add_argument('--category',default='auto'); sv.add_argument('--tag',action='append',default=[]); sv.add_argument('--attach',action='append',default=[]); sv.add_argument('--project')
 ls=s.add_parser('list'); ls.add_argument('--query'); ls.add_argument('--category'); ls.add_argument('--limit',type=int,default=50)
 g=s.add_parser('get'); g.add_argument('memory_id')
 a=s.add_parser('append'); a.add_argument('memory_id'); a.add_argument('content')
 at=s.add_parser('attach'); at.add_argument('memory_id'); at.add_argument('path'); at.add_argument('--role',default='attachment'); at.add_argument('--note',default='')
 atl=s.add_parser('attachments'); atl.add_argument('memory_id')
 dt=s.add_parser('detach'); dt.add_argument('memory_id'); dt.add_argument('sha256'); dt.add_argument('--delete-orphan',action='store_true')
 r=s.add_parser('resume'); r.add_argument('memory_ids',nargs='+')
 im=s.add_parser('import-uam'); im.add_argument('vault')
 b=s.add_parser('bundle'); b.add_argument('query'); b.add_argument('--category'); b.add_argument('--limit',type=int,default=10)
 mg=s.add_parser('merge'); mg.add_argument('memory_ids',nargs='+'); mg.add_argument('--title')
 ex=s.add_parser('export-pack'); ex.add_argument('output'); ex.add_argument('--id',dest='memory_ids',action='append',default=[]); ex.add_argument('--query'); ex.add_argument('--category'); ex.add_argument('--folder',action='store_true'); ex.add_argument('--active-only',action='store_true')
 cap=s.add_parser('session-pack'); cap.add_argument('output'); cap.add_argument('memory_ids',nargs='*'); cap.add_argument('--query'); cap.add_argument('--category'); cap.add_argument('--folder',action='store_true')
 ip=s.add_parser('import-pack'); ip.add_argument('path'); ip.add_argument('--open',action='store_true',dest='open_replay')
 ins=s.add_parser('inspect-pack'); ins.add_argument('path')
 ie=s.add_parser('inspect-encrypted'); ie.add_argument('path')
 impenc=s.add_parser('import-encrypted'); impenc.add_argument('path'); impenc.add_argument('--open',action='store_true',dest='open_replay')
 rc=s.add_parser('recovery-create'); rc.add_argument('output'); rc.add_argument('--code',help='Advanced/testing only; omit to generate a strong random recovery code')
 ri=s.add_parser('recovery-inspect'); ri.add_argument('path')
 rr=s.add_parser('recovery-restore'); rr.add_argument('path'); rr.add_argument('--code'); rr.add_argument('--code-stdin',action='store_true'); rr.add_argument('--replace-existing',action='store_true')
 rb=s.add_parser('recovery-backup'); rb.add_argument('path'); rb.add_argument('endpoint_id')
 rv=s.add_parser('recovery-verify'); rv.add_argument('path'); rv.add_argument('--code'); rv.add_argument('--code-stdin',action='store_true')
 ic=s.add_parser('insurance-configure'); ic.add_argument('endpoint_id'); ic.add_argument('--interval-hours',type=int,default=24); ic.add_argument('--retention',type=int,default=7); ic.add_argument('--deep-verify',action='store_true')
 ir=s.add_parser('insurance-run'); ir.add_argument('--force',action='store_true')
 ih=s.add_parser('insurance-health'); ih.add_argument('--deep',action='store_true'); ih.add_argument('--max-backup-age-hours',type=int,default=36)
 iv=s.add_parser('insurance-verify')
 il=s.add_parser('insurance-list'); il.add_argument('endpoint_id')
 ist=s.add_parser('insurance-restore'); ist.add_argument('path')
 isl=s.add_parser('insurance-restore-latest'); isl.add_argument('endpoint_id')
 args=p.parse_args(argv); cmd=args.cmd or 'app'; init_db()
 if cmd=='app': serve(); return 0
 if cmd=='desktop':
  from .desktop import run_desktop
  return run_desktop(args.paths,minimized=args.minimized)
 if cmd=='mcp': return run_stdio()
 if cmd=='smart-search': print(json.dumps(smart_search(args.query,project_id=args.project,category=args.category,limit=args.limit),ensure_ascii=False,indent=2)); return 0
 if cmd=='semantic-status': print(json.dumps(backend_status(),ensure_ascii=False,indent=2)); return 0
 if cmd=='model-status': print(json.dumps(model_status(),ensure_ascii=False,indent=2)); return 0
 if cmd=='model-install': print(json.dumps(install_model(source_dir=args.source_dir),ensure_ascii=False,indent=2)); return 0
 if cmd=='model-remove': print(json.dumps(uninstall_model(),ensure_ascii=False,indent=2)); return 0
 if cmd=='vectors-rebuild': print(json.dumps(rebuild_vectors(memory_ids=args.memory_ids or None),ensure_ascii=False,indent=2)); return 0
 if cmd=='vector-search': print(json.dumps(vector_search(args.query,project_id=args.project,category=args.category,limit=args.limit),ensure_ascii=False,indent=2)); return 0
 if cmd=='dedup-find': print(json.dumps(find_duplicates(args.memory_id,limit=args.limit,threshold=args.threshold),ensure_ascii=False,indent=2)); return 0
 if cmd=='dedup-scan': print(json.dumps(scan_duplicates(limit=args.limit,threshold=args.threshold),ensure_ascii=False,indent=2)); return 0
 if cmd=='dedup-merge': print(json.dumps(merge_duplicate_memories(args.memory_ids,title=args.title,archive_sources=not args.keep_sources),ensure_ascii=False,indent=2)); return 0
 if cmd=='project-create': print(json.dumps(create_project(args.name,summary=args.summary,current_state=args.current_state,next_action=args.next_action,status=args.status),ensure_ascii=False,indent=2)); return 0
 if cmd=='projects': print(json.dumps(list_projects(status=args.status,limit=args.limit),ensure_ascii=False,indent=2)); return 0
 if cmd=='project-get': print(json.dumps(get_project(args.project_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='project-update': print(json.dumps(update_project(args.project_id,name=args.name,summary=args.summary,current_state=args.current_state,next_action=args.next_action,status=args.status),ensure_ascii=False,indent=2)); return 0
 if cmd=='project-add': print(json.dumps(add_memory_to_project(args.project_id,args.memory_id,role=args.role),ensure_ascii=False,indent=2)); return 0
 if cmd=='project-remove': print(json.dumps(remove_memory_from_project(args.project_id,args.memory_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='project-resume': print(project_resume(args.project_id,query=args.query,limit=args.limit)['context']); return 0
 if cmd=='project-suggest': print(json.dumps(suggest_project_memories(args.project_id,limit=args.limit),ensure_ascii=False,indent=2)); return 0
 if cmd=='project-refresh': print(json.dumps(refresh_project_insights(args.project_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='agents': print(json.dumps(scan_agents(),ensure_ascii=False,indent=2)); return 0
 if cmd=='connect-all': print(json.dumps(connect_all_detected(),ensure_ascii=False,indent=2)); return 0
 if cmd=='connect': print(json.dumps(connect_agent(args.agent),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-endpoints': print(json.dumps(list_sync_endpoints(),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-detect': print(json.dumps(detect_sync_folders(),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-add': print(json.dumps(configure_sync_folder(args.path,provider=args.provider,name=args.name,auto_import=not args.no_auto_import,encryption_mode=args.encryption_mode),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-remove': print(json.dumps(remove_sync_endpoint(args.endpoint_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-send': print(json.dumps(publish_to_sync(args.endpoint_id,memory_ids=args.memory_ids or None,query=args.query,category=args.category),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-pull': print(json.dumps(receive_from_sync(args.endpoint_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-now': print(json.dumps(sync_now(args.endpoint_id,publish=args.publish,memory_ids=args.memory_ids or None,query=args.query,category=args.category),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-all': print(json.dumps(sync_all(),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-devices': print(json.dumps(list_sync_devices(args.endpoint_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-trust': print(json.dumps(trust_sync_device(args.endpoint_id,args.device_id,expected_fingerprint=args.fingerprint),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-untrust': print(json.dumps(revoke_sync_device(args.endpoint_id,args.device_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-security': print(json.dumps(sync_security_status(args.endpoint_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='sync-encryption': print(json.dumps(set_sync_encryption(args.endpoint_id,args.mode),ensure_ascii=False,indent=2)); return 0
 if cmd=='identity': print(json.dumps(public_identity(),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-status': print(json.dumps(insurance_settings(),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-disable': print(json.dumps(disable_insurance(),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-configure': print(json.dumps(configure_insurance(args.endpoint_id,interval_hours=args.interval_hours,retention=args.retention,deep_verify=args.deep_verify),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-run': print(json.dumps(run_insurance_backup(force=args.force),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-health': print(json.dumps(disaster_readiness(deep=args.deep,max_backup_age_hours=args.max_backup_age_hours),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-verify': print(json.dumps(verify_latest_insurance(),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-list': print(json.dumps(list_insurance_snapshots(args.endpoint_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-restore': print(json.dumps(restore_insurance_snapshot(args.path),ensure_ascii=False,indent=2)); return 0
 if cmd=='insurance-restore-latest': print(json.dumps(restore_latest_insurance(args.endpoint_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='recovery-status': print(json.dumps(recovery_status(),ensure_ascii=False,indent=2)); return 0
 if cmd=='recovery-create': print(json.dumps(create_recovery_kit(args.output,recovery_code=args.code),ensure_ascii=False,indent=2)); return 0
 if cmd=='recovery-inspect': print(json.dumps(inspect_recovery_kit(args.path),ensure_ascii=False,indent=2)); return 0
 if cmd=='recovery-backup': print(json.dumps(backup_recovery_file_to_sync(args.path,args.endpoint_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='recovery-verify':
  import getpass
  code=args.code
  if args.code_stdin: code=sys.stdin.readline().strip()
  if not code: code=getpass.getpass('Memory Box recovery code: ')
  print(json.dumps(verify_recovery_kit(args.path,code),ensure_ascii=False,indent=2)); return 0
 if cmd=='recovery-restore':
  import getpass
  code=args.code
  if args.code_stdin:
   code=sys.stdin.readline().strip()
  if not code:
   code=getpass.getpass('Memory Box recovery code: ')
  print(json.dumps(restore_recovery_kit(args.path,code,replace_existing=args.replace_existing),ensure_ascii=False,indent=2)); return 0
 if cmd=='lan-pair': print(json.dumps(start_pairing(port=args.port,ttl=args.ttl),ensure_ascii=False,indent=2)); return 0
 if cmd=='lan-status': print(json.dumps(pairing_status(),ensure_ascii=False,indent=2)); return 0
 if cmd=='lan-discover': print(json.dumps(discover_peers(),ensure_ascii=False,indent=2)); return 0
 if cmd=='lan-stop': print(json.dumps(stop_pairing(),ensure_ascii=False,indent=2)); return 0
 if cmd=='lan-send': print(json.dumps(send_pack(args.host,args.port,args.code,args.package),ensure_ascii=False,indent=2)); return 0
 if cmd=='save':
  card=save_memory(args.content,title=args.title,category=args.category,tags=args.tag,source_agent='cli')
  if args.project: add_memory_to_project(args.project,card['memory_id'])
  attached=[add_attachment(card['memory_id'],p) for p in args.attach]
  if attached or args.project: card=get_memory(card['memory_id'])
  print(json.dumps(card,ensure_ascii=False,indent=2)); return 0
 if cmd=='list': print(json.dumps(list_memories(query=args.query,category=args.category,limit=args.limit),ensure_ascii=False,indent=2)); return 0
 if cmd=='get': print(json.dumps(get_memory(args.memory_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='append': print(json.dumps(append_memory(args.memory_id,args.content),ensure_ascii=False,indent=2)); return 0
 if cmd=='attach': print(json.dumps(add_attachment(args.memory_id,args.path,role=args.role,note=args.note),ensure_ascii=False,indent=2)); return 0
 if cmd=='attachments': print(json.dumps(list_attachments(args.memory_id),ensure_ascii=False,indent=2)); return 0
 if cmd=='detach': print(json.dumps(remove_attachment(args.memory_id,args.sha256,delete_orphan_blob=args.delete_orphan),ensure_ascii=False,indent=2)); return 0
 if cmd=='resume': print(compose_context(args.memory_ids)); return 0
 if cmd=='import-uam': print(json.dumps(import_uam_json(args.vault),ensure_ascii=False,indent=2)); return 0
 if cmd=='bundle': print(json.dumps(bundle_by_query(args.query,category=args.category,limit=args.limit),ensure_ascii=False,indent=2)); return 0
 if cmd=='merge': print(json.dumps(merge_memories(args.memory_ids,title=args.title),ensure_ascii=False,indent=2)); return 0
 if cmd=='export-pack':
  print(json.dumps(export_transfer_bundle(args.output,memory_ids=args.memory_ids or None,query=args.query,category=args.category,as_folder=args.folder,include_archived=not args.active_only),ensure_ascii=False,indent=2)); return 0
 if cmd=='session-pack':
  print(json.dumps(export_transfer_bundle(args.output,memory_ids=args.memory_ids or None,query=args.query,category=args.category,as_folder=args.folder),ensure_ascii=False,indent=2)); return 0
 if cmd=='import-pack': print(json.dumps(import_transfer_bundle(args.path,open_replay=args.open_replay),ensure_ascii=False,indent=2)); return 0
 if cmd=='inspect-pack': print(json.dumps(inspect_transfer_bundle(args.path),ensure_ascii=False,indent=2)); return 0
 if cmd=='inspect-encrypted': print(json.dumps(inspect_encrypted_file(args.path)['header'],ensure_ascii=False,indent=2)); return 0
 if cmd=='import-encrypted':
  import tempfile
  with tempfile.TemporaryDirectory(prefix='memorybox-decrypt-') as td:
   dec=Path(td)/'decrypted.payload'; decrypt_file_for_local_device(args.path,dec)
   try: result=import_transfer_bundle(dec,open_replay=args.open_replay)
   except Exception:
    result=restore_insurance_snapshot(args.path)
   print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
 return 1
