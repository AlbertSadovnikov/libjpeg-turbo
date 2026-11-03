#!/usr/bin/env python3
from common import *
import statistics
B=WORK/'bin'
expected=json.loads((HERE.parent/'no-mtune/validation.json').read_text())
validation={};counters={};stages={};records=[];brackets=[]
for cc in ('clang','gcc'):
 validation[cc]={}
 for label,files in [('capture',FRAMES),*[(p.stem,[p]) for p in FIXTURES]]:
  oracle=expected[cc]['current'][label]
  for variant in ('control','span-off','unpaired'):
   r=execute(B/(cc+'-'+variant),'validate',*files);assert r==oracle,(cc,variant,label)
  validation[cc][label]=oracle
 print(cc,'baseline and two ablations preserve all capture/fixture outputs.',flush=True)
 counters[cc]={}
 for label,files in [('capture',FRAMES),*[(p.stem,[p]) for p in FIXTURES if p.stem in ('dense','zeroac','optimized')]]:
  counters[cc][label]=execute(B/(cc+'-diagnostic-probe'),'count',*files)
 counters[cc]['names']=['fast_mcus','single_hits','pair_hits','lut_fallbacks','refills','clean_bulk_refills','ff_guard_refills','fast_marker_retries','slow_mcus','stuffed_ff_observations','marker_observations']
 save(HERE/'phase-a-counters.json',counters)
 stages[cc]={'entropy':execute(B/(cc+'-probe'),'entropy',*FRAMES[30:]),'kernels':execute(B/(cc+'-probe'),'kernels',FRAMES[60])}
 print(cc,'fresh stages and untimed real-MCU counters collected.',flush=True)
save(HERE/'phase-a-validation.json',validation);save(HERE/'phase-a-stages.json',stages)
# Same-binary repeat is an explicit noise control, not an implementation.
for trial in range(3):
 for cc in (('clang','gcc') if trial%2==0 else ('gcc','clang')):
  for candidate in (('span-off','unpaired','control') if trial%2==0 else ('control','unpaired','span-off')):
   group=[]
   for variant in ('control',candidate,'control'):
    r=execute(B/(cc+'-'+variant),'fast',2,3,*FRAMES[30:]);r.update(trial=trial,compiler=cc,variant=variant,candidate=candidate);records.append(r);group.append(r)
   assert len({v['hash'] for v in group})==1
   a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);v=group[1]['mean_ms']
   brackets.append({'trial':trial,'compiler':cc,'variant':candidate,'control_ms':a,'candidate_ms':v,'change_percent':100*(v/a-1)})
   save(HERE/'phase-a-results.json',{'records':records,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for cc in ('clang','gcc'):
 summary[cc]={}
 for name in ('span-off','unpaired','control'):
  r=[v for v in brackets if v['compiler']==cc and v['variant']==name];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
  summary[cc][name]={'control_ms':a,'candidate_ms':b,'change_percent':100*(b/a-1),'brackets':r}
save(HERE/'phase-a-summary.json',summary)
