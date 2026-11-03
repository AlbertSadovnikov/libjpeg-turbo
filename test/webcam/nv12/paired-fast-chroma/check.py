#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
w=Path('/tmp/mjpeg-paired-fast-chroma')
# Clang links the freshly compiled native checker and its no-PGO ThinLTO codec.
run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',here/'check.cc','-o',w/'check.o'])
run(['clang++','-O3','-flto=thin','-fuse-ld=gold',w/'check.o',OLD_COMMON/'frame.o',w/'fast.o',BASE/'clang/current/libjpeg.a','-lm','-o',w/'check'])
r=execute(w/'check');save(here/'kernel.json',r);print('All captured/synthetic UV pairs match two native IFAST calls + rounded byte averaging/interleave.')
