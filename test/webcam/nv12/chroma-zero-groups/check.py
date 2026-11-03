#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',here/'check.cc','-o',WORK/'zero-check.o'])
run(['clang++','-O3','-flto=thin','-fuse-ld=gold',WORK/'zero-check.o',WORK/'zero-check-ref.o',WORK/'zero-check-zero.o',OLD_COMMON/'registers.o',OLD_COMMON/'exact.o',OLD_COMMON/'frame.o',BASE/'clang/current/libjpeg.a','-lm','-o',WORK/'zero-check'])
r=execute(WORK/'zero-check');save(here/'kernel.json',r);print('Reduced UV zero-skipping is byte-exact on captured/synthetic/table-change checks.')
