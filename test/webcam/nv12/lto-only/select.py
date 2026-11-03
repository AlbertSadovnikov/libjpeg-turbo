#!/usr/bin/env python3
"""Select the validated no-PGO, ThinLTO experimental pipeline."""
from pathlib import Path
import json,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-lto-only')
build=json.loads((here/'build-summary.json').read_text());audit=json.loads((here/'no-pgo-audit.json').read_text());summary=json.loads((here/'summary.json').read_text())
assert build['pgo'] is False and audit['pgo'] is False and summary['pgo'] is False
case=build['cases']['current'];binary=work/'current/nv12';hashes={str(binary):case['binary_sha256'],**case['archive_sha256']}
for filename,wanted in hashes.items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==wanted,filename
assert summary['current_binary_sha256']==case['binary_sha256']
for name,target in [('candidate','current'),('nv12','current/nv12')]:
 link=work/name
 if link.is_symlink():link.unlink()
 elif link.exists():raise RuntimeError(f'Refusing to replace a regular file/directory: {link}')
 link.symlink_to(target)
selection={'binary':str(work/'nv12'),'artifact_directory':str(work/'candidate'),'pgo':False,'lto':'ThinLTO, complete fresh codec rebuild','codec_flags':case['codec_flags'],'entropy_extra_flags':case['entropy_extra_flags'],'components':['scalar bulk reader','cached two-AC-symbol 10-bit LUT','pre-shifted long-code thresholds','precomputed coefficient span','register-rewritten paired fast Y','guarded inline AVX2 zeroing per user preference','existing reduced fused UV'],'quantizer_cache_selected':False,'sha256':hashes,'comparison_policy':'No PGO in comparisons; LTO is allowed and matched. Previous PGO-assisted cohorts are historical only.'}
(here/'preferred-candidate.json').write_text(json.dumps(selection,indent=2)+'\n');print('Preferred no-PGO NV12 candidate:',work/'nv12')
