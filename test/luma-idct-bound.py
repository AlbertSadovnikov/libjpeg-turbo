#!/usr/bin/env python3
"""Prove the Q15 SIMD admission bound, using exact rational arithmetic.

Tracks every arithmetic operation, including fractional-multiply inputs.
The transpose merely permutes coordinates. No third-party packages needed.
"""
from fractions import Fraction as F
from pathlib import Path
import math
import re

nodes = []

class Affine:
    def __init__(self, coefficients, error=0):
        self.a = tuple(coefficients)
        self.error = F(error)
        nodes.append(self)

    def __add__(self, other):
        return Affine([a+b for a,b in zip(self.a, other.a)], self.error+other.error)

    def __sub__(self, other):
        return Affine([a-b for a,b in zip(self.a, other.a)], self.error+other.error)

    def frac(self, c):
        scale = F(c, 32768)
        return Affine([a*scale for a in self.a], self.error*scale+F(1,2))

def transform(x, rotation=False):
    root = lambda a: a+a.frac(13573)
    p=x[0]+x[4]; q=x[0]-x[4]; r=x[2]+x[6]
    t=root(x[2]-x[6])-r
    e0=p+r; e3=p-r; e1=q+t; e2=q-t
    a=x[5]+x[3]; b=x[5]-x[3]; c=x[1]+x[7]; d=x[1]-x[7]
    o7=c+a; u=root(c-a)
    if rotation=='lifting':
        d1=d-b.frac(6518)
        w=b+d1.frac(12540)
        v=d1-w.frac(6518)
        o6=(v+v)-o7
        o5=u-o6; o4=(w+w)-o5
    elif rotation:
        v=d.frac(30274)-b.frac(12540)
        w=b.frac(30274)+d.frac(12540)
        o6=(v+v)-o7
        o5=u-o6; o4=(w+w)-o5
    else:
        bd=b+d; z=bd+bd.frac(27779)
        o6=(z-((b+b)+b.frac(20091)))-o7
        o5=u-o6; o4=(z-(d+d.frac(2700)))-o5
    return [e0+o7,e1+o6,e2+o5,e3+o4,e3-o4,e2-o5,e1-o6,e0-o7]

def derive(rotation=False):
    nodes.clear()
    x=[[Affine([int(i==8*r+c) for i in range(64)]) for c in range(8)] for r in range(8)]
    for c in range(8):
        col=transform([x[r][c] for r in range(8)], rotation)
        for r in range(8): x[r][c]=col[r]
    for r in range(8): x[r]=transform(x[r], rotation)
    weights=[math.ceil(max(abs(n.a[k]) for n in nodes)) for k in range(64)]
    error=max(n.error for n in nodes)
    return weights, error, max(sum(abs(c) for c in n.a) for n in nodes)

def verify(rotation=False):
    weights, error, gain=derive(rotation)
    name='lifting' if rotation=='lifting' else 'rotation' if rotation else 'integer'
    header=Path(__file__).with_name(f'luma-idct-{name}.h').read_text()
    match=re.search(name+r'_weights\[64\]=\{(.*?)\};',header,re.S)
    assert weights==list(map(int,re.findall(r'\d+',match.group(1))))
    budget=110 if rotation=='lifting' else 113 if rotation else 93
    assert error<=budget
    assert gain<130  # Also bounds the 64-bit fallback for signed-short inputs.
    assert 130*(1<<30)*30274+(1<<15)<(1<<63)
    for bits in (2,3,4):
        bias=1<<(bits+2)
        limit=32767-budget-bias
        assert limit+error+bias<=32767
        assert -limit-error>=-32768
        print(f'{name} B={bits}: weighted input sum <= {limit} proves all operations and final rounding fit')
    print(f'Maximum rounding error bound: {error} = {float(error):.6f}')
    print(f'{name} header weights match the exact per-operation derivation')

class RoundedExpression:
    """Canonical integer-linear expression with opaque, exact rounding atoms."""
    seen=[]
    def __init__(self, terms=None):
        self.terms={k:v for k,v in (terms or {}).items() if v}
        self.key=tuple(sorted(self.terms.items(), key=lambda item:repr(item[0])))
        self.seen.append(self.key)
    def combine(self, other, sign):
        terms=dict(self.terms)
        for key,value in other.terms.items(): terms[key]=terms.get(key,0)+sign*value
        return RoundedExpression(terms)
    def __add__(self, other): return self.combine(other,1)
    def __sub__(self, other): return self.combine(other,-1)
    def frac(self, c):
        return RoundedExpression({('round',c,self.key):1}) if self.terms else RoundedExpression()

def verify_low4():
    x=[RoundedExpression({('input',k):1}) for k in range(4)]+[RoundedExpression() for _ in range(4)]
    RoundedExpression.seen=[]
    full=transform(x,True)
    original_nodes=set(RoundedExpression.seen+[a.key for a in x])
    RoundedExpression.seen=[]
    t=x[2].frac(13573)
    e0=x[0]+x[2]; e3=x[0]-x[2]; e1=x[0]+t; e2=x[0]-t
    b=x[4]-x[3]; o7=x[1]+x[3]
    delta=x[1]-x[3]; u=delta+delta.frac(13573)
    v=x[1].frac(30274)-b.frac(12540)
    w=b.frac(30274)+x[1].frac(12540)
    o6=(v+v)-o7; o5=u-o6; o4=(w+w)-o5
    reduced=[e0+o7,e1+o6,e2+o5,e3+o4,e3-o4,e2-o5,e1-o6,e0-o7]
    assert [a.key for a in full]==[a.key for a in reduced]
    assert set(RoundedExpression.seen)<=original_nodes
    print('low4: exact rounded outputs match; every reduced arithmetic node occurs in full rotation')

if __name__=='__main__':
    verify()
    verify(True)
    verify('lifting')
    verify_low4()
