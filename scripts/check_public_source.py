"""Scan staged Git blobs, reporting file names and rule names, never matched secrets."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--staged',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
command=['git','ls-files','-z'] if args.staged else ['git','ls-files','--cached','--others','--exclude-standard','-z']
paths=[p for p in subprocess.check_output(command,cwd=root).decode().split('\0') if p]
if not args.staged:
    paths=list(dict.fromkeys(p for p in paths if (root/p).is_file()))
staged_blobs={}
if args.staged and paths:
    entries=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=root).decode().split('\0')
    objects=[]
    for entry in filter(None,entries):
        metadata,name=entry.split('\t',1)
        _,oid,stage=metadata.split(' ')
        if stage!='0':raise SystemExit('Resolve Git index conflicts before publication')
        objects.append((name,oid))
    output=subprocess.check_output(['git','cat-file','--batch'],input=''.join(oid+'\n' for _,oid in objects).encode(),cwd=root)
    cursor=0
    for name,oid in objects:
        end=output.index(b'\n',cursor)
        header=output[cursor:end].split()
        if len(header)!=3 or header[1]!=b'blob':raise SystemExit('Invalid staged Git object')
        size=int(header[2]);start=end+1
        staged_blobs[name]=output[start:start+size]
        cursor=start+size+1
secrets=[]
env=root/'.env'
if env.is_file():
    for line in env.read_text('utf-8-sig').splitlines():
        key,sep,value=line.partition('=')
        value=value.strip().strip('\"\'')
        if sep and any(k in key.upper() for k in ('KEY','TOKEN','SECRET','PASSWORD')) and len(value)>12:
            raw=value.encode();secrets.extend([raw,base64.b64encode(raw)])
rules={
    'private_key':rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA |)PRIVATE KEY-----',
    'github_token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'provider_key':rb'\bsk-[A-Za-z0-9_-]{24,}',
    'bearer_jwt':rb'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{20,}',
}
findings=[]
for name in paths:
    parts=Path(name).parts
    if (Path(name).name.startswith('.env') and Path(name).name!='.env.example') or any(p in ('backups','uploads','artifacts','.venv','node_modules','test-results','live-test-results') for p in parts) or name.endswith(('.db','.sqlite','.sqlite3','.pem','.key','.p12','.pfx','.dump','.log')):
        findings.append({'file':name,'rule':'private_runtime_file'})
    data=staged_blobs[name] if args.staged else (root/name).read_bytes()
    if any(secret in data for secret in secrets):findings.append({'file':name,'rule':'configured_secret'})
    for rule,pattern in rules.items():
        if re.search(pattern,data):findings.append({'file':name,'rule':rule})
print(json.dumps({'files_scanned':len(paths),'findings':findings},ensure_ascii=False,indent=2))
raise SystemExit(1 if findings else 0)
