#!/usr/bin/env python3
"""Prefer the validated untuned Clang build; preserve tuned/GCC artifacts."""
from pathlib import Path
import json,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-no-mtune')
build=json.loads((here/'build-summary.json').read_text());audit=json.loads((here/'audit.json').read_text());summary=json.loads((here/'summary.json').read_text())
assert build['pgo'] is False and build['explicit_mtune'] is False and audit['pgo'] is False
case=build['cases']['clang']['current']
for filename,wanted in case['sha256'].items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==wanted,filename
assert summary['cases']['clang']['current_ms']<summary['cases']['gcc']['current_ms']
for name,target in [('candidate','clang/current'),('nv12','clang/current/nv12')]:
 link=work/name
 if link.is_symlink():link.unlink()
 elif link.exists():raise RuntimeError(f'Refusing to replace a regular file/directory: {link}')
 link.symlink_to(target)
selection={'binary':str(work/'nv12'),'artifact_directory':str(work/'candidate'),'compiler':'clang','pgo':False,'explicit_mtune':False,'codec_flags':case['codec_flags'],'entropy_extra_flags':case['entropy_extra_flags'],'components':['bulk scalar entropy reader','cached two-AC-symbol 10-bit LUT','pre-shifted long-code thresholds','precomputed coefficient span','register-rewritten paired fast Y','guarded inline AVX2 zeroing per user preference','existing reduced fused UV'],'quantizer_cache_selected':False,'sha256':case['sha256'],'reason':'Fastest of the two validated default-tuning compiler builds in this cohort. Direct no-PGO Clang default-versus-znver2 check shows no observed penalty; small differences remain noisy and workload-specific.'}
(here/'preferred-candidate.json').write_text(json.dumps(selection,indent=2)+'\n');print('Preferred no-PGO/default-tuning candidate:',work/'nv12')
