"""One-time read-only SSH capture; runs adapter in memory without deployment."""
import json
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
source=(root/'publisher/collect.py').read_text().replace("if __name__=='__main__':main()", "print(json.dumps(collect_server('/home/mrhea/HealysBacktester'),allow_nan=False))")
r=subprocess.run(['ssh','-o','BatchMode=yes','mrhea@62.238.20.66','./HealysBacktester/venv/bin/python -'],input=source,text=True,capture_output=True,check=True,timeout=60)
data=json.loads(r.stdout)
p=root/'private/server.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(data));p.chmod(0o600)
print(json.dumps({'scanners':len(data['scanners']),'signals':len(data['signals']),'positions':len(data['positions']),'issues':data['issues']}))
