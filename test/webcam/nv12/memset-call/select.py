#!/usr/bin/env python3
"""Select the existing inline AVX2 candidate without changing measured binaries."""
from pathlib import Path
import hashlib
import json

here = Path(__file__).resolve().parent
work = Path('/tmp/mjpeg-memset-call')
variant = 'avx2'
build = json.loads((here / 'build-summary.json').read_text())
artifacts = build['variants'][variant]['sha256']
for filename, expected in artifacts.items():
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == expected, filename

for name, target in [('candidate', variant), ('nv12', variant + '/nv12')]:
    link = work / name
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        raise RuntimeError(f'Refusing to replace a regular file/directory: {link}')
    link.symlink_to(target)

selection = {
    'variant': variant,
    'reason': 'User prefers inline zeroing even without a proven speedup.',
    'clear': '512 bytes inline using AVX2; existing fallback for other sizes/CPUs',
    'speedup_proven': False,
    'binary': str(work / 'nv12'),
    'artifact_directory': str(work / 'candidate'),
    'sha256': artifacts,
}
(here / 'preferred-candidate.json').write_text(json.dumps(selection, indent=2) + '\n')
print(f'Preferred NV12 candidate: {work / "nv12"} ({variant})')
