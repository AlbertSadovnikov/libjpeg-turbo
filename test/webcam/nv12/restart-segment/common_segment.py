from pathlib import Path
import sys,os
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-restart-segment');TU=Path('/tmp/mjpeg-restart-tu');B=WORK/'bin'
def execute_segment(cc,enabled,*args):
 env=os.environ.copy();env['MJPEG_SEGMENT']='1' if enabled else '0'
 r=run(['taskset','-c','0',B/(cc+'-segment'),*args],text=True,env=env);assert not r.stderr,r.stderr
 return json.loads(r.stdout)

def execute_reference(cc,*args):
 env=os.environ.copy();env['MJPEG_SEGMENT']='1'
 r=run(['taskset','-c','0',B/(cc+'-tu-fast'),*args],text=True,env=env);assert not r.stderr
 return json.loads(r.stdout)
