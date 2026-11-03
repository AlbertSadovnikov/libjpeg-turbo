#!/usr/bin/env python3
"""Select the validated span candidate; preserve older experiment baselines."""
from pathlib import Path
import json,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-entropy-span')
build=json.loads((here/'build-summary.json').read_text())['cases']['span']
confirmation=json.loads((here/'confirm-summary.json').read_text())
artifacts=build['sha256']
for filename,wanted in artifacts.items():
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==wanted,filename
assert confirmation['candidate_sha256']==artifacts[str(work/'span/nv12')]
for name,target in [('candidate','span'),('nv12','span/nv12')]:
    link=work/name
    if link.is_symlink():link.unlink()
    elif link.exists():raise RuntimeError(f'Refusing to replace a regular file/directory: {link}')
    link.symlink_to(target)
selection={
    'variant':'precomputed entropy span',
    'binary':str(work/'nv12'),
    'artifact_directory':str(work/'candidate'),
    'components':['scalar bulk entropy reader','cached 10-bit two-AC-symbol LUT with precomputed span','shifted long-code thresholds','register-rewritten paired Y','guarded inline AVX2 zeroing per user preference','existing reduced fused UV'],
    'quantizer_cache_selected':False,
    'entropy_build':'native Clang PGO object; per-source fresh profile; other codec members retain original ThinLTO/PGO',
    'matched_source_change_percent':json.loads((here/'summary.json').read_text())['cases']['span']['change_percent'],
    'direct_previous_selection_change_percent':confirmation['cases']['span']['change_percent'],
    'limitation':'One CPU/scene, noisy rounds retained. Direct comparison includes fresh-profile/native-object regime; it is not pure source attribution.',
    'sha256':artifacts,
    'previous_selection':'/tmp/mjpeg-memset-call/nv12 (preserved for reproduction)',
}
(here/'preferred-candidate.json').write_text(json.dumps(selection,indent=2)+'\n')
print('Preferred experimental NV12 candidate:',work/'nv12')
