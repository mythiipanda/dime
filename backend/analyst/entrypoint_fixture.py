"""Start the actual Node host with its generated manifest and an owned warehouse."""
import json,os,shutil,socket,subprocess,sys,time,urllib.request
from pathlib import Path
module=Path(__file__).resolve().parent
root=Path(os.environ['DIME_PI_TEST_ROOT'])
env={**os.environ,'DIME_PI_PYTHON':sys.executable}
node=shutil.which('node')
manifest=root/'entrypoint-manifest.json'
subprocess.run([node,str(module/'dist/host.js'),'manifest',str(manifest)],env=env,check=True)
with socket.socket() as sock:
 sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env['PORT']=str(port);env['DIME_EXPECTED_ASSET_MANIFEST']=str(manifest)
source='import {main} from '+json.dumps((module/'dist/host.js').as_uri())+'; process.stdin.on("data",()=>process.emit("SIGTERM")); try {await main([]);} finally {process.stdin.pause();}'
process=subprocess.Popen([node,'--input-type=module','-e',source],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 for _ in range(150):
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/revision',timeout=.25) as response:observed=json.load(response)
   break
  except (OSError,TimeoutError):
   if process.poll() is not None:raise RuntimeError('Node host exited before listening')
   time.sleep(.05)
 else:raise TimeoutError('Node host did not listen')
 assert observed==json.loads(manifest.read_text())
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=2) as response:assert json.load(response)['ok']
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=2) as response:assert json.load(response)['runtime']=='v2'
 for path in ('/openapi.json','/docs','/redoc','/docs/oauth2-redirect'):
  with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=2) as response:assert response.status==200 and response.read()
 process.stdin.write(b'\n');process.stdin.flush();stdout,stderr=process.communicate(timeout=8)
 assert process.returncode==0,(stdout,stderr)
 print('Actual Node host entrypoint: generated preflight manifest, HTTP revision/health/root and graceful data MCP shutdown passed')
finally:
 if process.poll() is None:
  process.kill();process.communicate()
