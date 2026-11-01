#!/usr/bin/env python3
"""Render signed NV12 sample errors and display-only RGB comparisons."""
import json
import os
from pathlib import Path
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run import compile_driver

here=Path(__file__).resolve().parent
out=here/'error-delta'
out.mkdir(exist_ok=True)
width,height=1920,1080  # The documented embedded webcam fixture.
binary=compile_driver('pair10')
result=subprocess.run([str(binary),'--benchmark_filter=PackOnly_SIMD',
                       '--benchmark_min_time=0.001s','--benchmark_min_warmup_time=0'],
                      env=dict(os.environ,MJPEG_NV12_DUMP=str(out/'frame')),
                      capture_output=True,text=True,check=True)
(out/'decode.log').write_text(result.stdout+result.stderr)
def load(kind):
    b=np.fromfile(out/f'frame.{kind}.nv12',dtype=np.uint8)
    assert b.size==width*height*3//2
    y=b[:width*height].reshape(height,width)
    uv=b[width*height:].reshape(height//2,width//2,2)
    return y,uv[:,:,0],uv[:,:,1]
accurate,fast=load('accurate'),load('fast')
delta=[b.astype(np.int16)-a.astype(np.int16) for a,b in zip(accurate,fast)]
def rgb(planes):
    y,u,v=planes
    u=np.repeat(np.repeat(u,2,axis=0),2,axis=1).astype(float)-128
    v=np.repeat(np.repeat(v,2,axis=0),2,axis=1).astype(float)-128
    y=y.astype(float)
    return np.clip(np.stack((y+1.402*v,y-.344136*u-.714136*v,y+1.772*u),axis=-1),0,255)/255
a,b=rgb(accurate),rgb(fast)
metrics={}
for name,d in zip(('Y','U','V'),delta):
    values,counts=np.unique(d,return_counts=True)
    mse=float(np.mean(d.astype(float)**2))
    metrics[name]=dict(max_abs=int(np.abs(d).max()),mean_abs=float(np.abs(d).mean()),mean_signed=float(d.mean()),
                       changed_percent=float(np.mean(d!=0)*100),
                       psnr_db=float(10*np.log10(255**2/mse)) if mse else None,
                       signed_histogram={str(int(v)):int(c) for v,c in zip(values,counts)})

# Full-frame overview: chroma maps stay at native resolution (no error resampling).
fig,axes=plt.subplots(2,3,figsize=(18,10),layout='constrained')
for ax,pixels,title in zip(axes[0],(a,b,np.clip(np.abs(b-a)*16,0,1)),
                          ('Accurate IDCT','Fast IDCT','Absolute display RGB difference x16')):
    ax.imshow(pixels); ax.set_title(title); ax.axis('off')
for ax,d,name in zip(axes[1],delta,('Y (1920 x 1080)','U (960 x 540)','V (960 x 540)')):
    peak=max(1,int(np.abs(d).max()))
    im=ax.imshow(d,cmap='RdBu_r',vmin=-peak,vmax=peak,interpolation='nearest')
    ax.set_title(f'Signed {name}: fast - accurate'); ax.axis('off')
    fig.colorbar(im,ax=ax,shrink=.65,label='8-bit sample levels')
fig.suptitle('Same JPEG, same full-range NV12 conversion; only IDCT method differs\n'
             'RGB previews use nearest chroma expansion; heatmaps use exact native-plane samples')
fig.savefig(out/'overview.png',dpi=160); plt.close(fig)

# Select a reproducible high-error 128x128 luma region, checking a 16px grid.
size=128
error=np.abs(delta[0]).astype(np.int64)
integral=np.pad(error,((1,0),(1,0))).cumsum(0).cumsum(1)
best=(-1,0,0)
for y in range(0,height-size+1,16):
    for x in range(0,width-size+1,16):
        score=integral[y+size,x+size]-integral[y,x+size]-integral[y+size,x]+integral[y,x]
        if score>best[0]: best=(int(score),y,x)
_,y,x=best
fig,axes=plt.subplots(1,4,figsize=(16,5),layout='constrained')
for ax,pixels,title in zip(axes[:3],(a[y:y+size,x:x+size],b[y:y+size,x:x+size],
                           np.clip(np.abs(b-a)[y:y+size,x:x+size]*16,0,1)),
                          ('Accurate','Fast','Absolute display RGB difference x16')):
    ax.imshow(pixels,interpolation='nearest'); ax.set_title(title); ax.axis('off')
im=axes[3].imshow(delta[0][y:y+size,x:x+size],cmap='RdBu_r',vmin=-5,vmax=5,interpolation='nearest')
axes[3].set_title('Signed Y difference'); axes[3].axis('off')
fig.colorbar(im,ax=axes[3],shrink=.65,label='Sample levels')
fig.suptitle(f'128 x 128 high-error crop at x={x}, y={y}; chosen by luma absolute-error sum')
fig.savefig(out/'crop.png',dpi=160); plt.close(fig)

fig,axes=plt.subplots(1,3,figsize=(12,3),layout='constrained')
for ax,d,name in zip(axes,delta,('Y','U','V')):
    values,counts=np.unique(d,return_counts=True)
    ax.bar(values,counts/d.size*100); ax.set_title(name)
    ax.set_xlabel('Fast - accurate (sample levels)'); ax.set_ylabel('% of samples')
fig.savefig(out/'histograms.png',dpi=160); plt.close(fig)
metrics['crop']=dict(x=x,y=y,width=size,height=size)
metrics['definition']='Signed errors are fast minus accurate NV12 samples; RGB difference is a display aid, not the sample-error metric.'
(out/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
print(json.dumps(metrics,indent=2))
