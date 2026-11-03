#!/usr/bin/env python3
"""Select the two validated output contracts without changing old baselines."""
from common import *
confirmation=json.loads((HERE/'confirm-summary.json').read_text())
for cc in ('clang','gcc'):
 for contract in ('reduced-zero','stock-exact'):
  assert all(b['change_percent']<0 for b in confirmation[cc][contract]['brackets'])
selections={}
for folder,binary,mode,contract in (
 ('mjpeg-chroma-zero-groups','clang-zero-groups',2,'Existing reduced UV approximation; exact previous output'),
 ('mjpeg-paired-fast-chroma','clang-uv-paired',3,'Stock IFAST NV12 byte-exact; not stock accurate IDCT')):
 target=WORK/'bin'/binary
 record=json.loads((HERE.parent/('chroma-zero-groups' if mode==2 else 'paired-fast-chroma')/'build-summary.json').read_text())
 assert sha(target)==record['binaries']['clang' if mode==2 else binary],target
 alias=Path('/tmp')/folder/'nv12';alias.parent.mkdir(parents=True,exist_ok=True)
 if alias.is_symlink():alias.unlink()
 assert not alias.exists(),alias
 alias.symlink_to(target)
 selections[folder]={'executable':str(alias),'target':str(target),'sha256':sha(target),'arguments':['fast',str(mode),'PASSES','JPEG...'],'contract':contract}
save(HERE/'selections.json',selections)
print(json.dumps(selections,indent=2))
