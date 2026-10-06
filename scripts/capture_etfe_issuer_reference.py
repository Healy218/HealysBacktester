"""One bounded read-only issuer tax-reference capture; no market data replacement."""
import argparse,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import sha,save,write_new
URL='https://www.invesco.com/content/dam/invesco/us/en/documents/tax-document/ce-ici-primary-and-secondary-distribution-file-file-ivz-etf-2024-02-10-2025.xlsx'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('issuer-fresh-'):p.error('Isolated reference root required')
    root.mkdir(parents=True,exist_ok=False);write_new(root/'SOURCE.py',Path(__file__).read_bytes())
    started=datetime.now(timezone.utc).isoformat();clock=time.monotonic();raw=bytearray()
    with requests.get(URL,stream=True,timeout=(10,20),allow_redirects=False) as response:
        status=response.status_code
        for block in response.iter_content(65536):
            if len(raw)+len(block)>16*2**20 or time.monotonic()-clock>60:raise RuntimeError('Bounded issuer capture exceeded')
            raw.extend(block)
    write_new(root/'body.xlsx',bytes(raw));save(root/'RECEIPT.json',dict(url=URL,status=status,observed_at=started,received_at=datetime.now(timezone.utc).isoformat(),sha256=sha(raw),bytes=len(raw),source_sha256=sha(Path(__file__).read_bytes()),historical_publication_time_verified=False))
    print(json.dumps(dict(status=status,bytes=len(raw),sha256=sha(raw))))
    if status!=200:raise SystemExit(2)
