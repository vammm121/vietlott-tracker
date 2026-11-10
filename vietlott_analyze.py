# -*- coding: utf-8 -*-
"""Vietlott Mega 6/45 - full statistical audit of vietlott_mega645_full_history.csv
Run: python vietlott_analyze.py
"""
import csv, math, itertools, zlib
from collections import Counter, defaultdict
from math import comb
import numpy as np
from scipy import stats, optimize

CSV="vietlott_mega645_full_history.csv"
raw=list(csv.DictReader(open(CSV,encoding="utf-8-sig")))
draws=[tuple(sorted(int(r["n%d"%i]) for i in range(1,7))) for r in raw]
N=len(draws)
jp=np.array([int(r["jackpot_vnd"]) for r in raw],float)
win=np.array([int(r["jackpot_winners"]) for r in raw])
g1=np.array([int(r["giai_nhat_winners"]) for r in raw],float)
g2=np.array([int(r["giai_nhi_winners"]) for r in raw],float)
g3=np.array([int(r["giai_ba_winners"]) for r in raw],float)
C=comb(45,6)
P1=6*39/C; P2=comb(6,4)*comb(39,2)/C; P3=comb(6,3)*comb(39,3)/C
line="-"*64

print(line);print("0. DU LIEU");print(line)
print("so ky:",N," tu",raw[0]["draw_date"],"den",raw[-1]["draw_date"])
print("ky loi:",sum(1 for d in draws if len(set(d))!=6 or min(d)<1 or max(d)>45))
print("C(45,6) =",C)

print(line);print("1. TINH DEU CUA 45 SO");print(line)
freq=Counter(n for d in draws for n in d)
obs=np.array([freq.get(i,0) for i in range(1,46)],float)
exp=np.full(45,N*6/45)
chi2=float(((obs-exp)**2/exp).sum())
print("chi2=%.2f df=44 p=%.4f | min=%d max=%d mean=%.2f sd=%.2f (ly thuyet sd=13.54)"%(chi2,stats.chi2.sf(chi2,44),obs.min(),obs.max(),obs.mean(),obs.std()))
print("nong:", sorted(freq,key=lambda n:-freq[n])[:8])
print("lanh:", sorted(freq,key=lambda n:freq[n])[:8])

print(line);print("2. THONG KE BAC (sorted columns) vs LY THUYET");print(line)
rng0=np.random.default_rng(2)
simall=np.sort(rng0.random((200000,45)).argsort(axis=1)[:,:6]+1,axis=1)
for pos in range(6):
    emp=np.array([d[pos] for d in draws])
    ks=stats.ks_2samp(emp,simall[:,pos])
    print("  bac%d mean=%.2f (lt %.2f) KS p=%.4f"%(pos+1,emp.mean(),simall[:,pos].mean(),ks.pvalue))
sums=np.array([sum(d) for d in draws])
sim=(np.random.default_rng(1).random((200000,45)).argsort(axis=1)[:,:6]+1).sum(1)
print("  tong: mean=%.2f (lt 138) sd=%.2f (lt 29.95) KS p=%.4f"%(sums.mean(),sums.std(),stats.ks_2samp(sums,sim).pvalue))

print(line);print("3. HINH DANG KET HOP");print(line)
print("  so le:",dict(sorted(Counter(sum(1 for x in d if x%2) for d in draws).items())))
print("  <=22 :",dict(sorted(Counter(sum(1 for x in d if x<=22) for d in draws).items())))
print("  lien tiep:",dict(sorted(Counter(sum(1 for x in set(d) if x+1 in set(d)) for d in draws).items())))

print(line);print("4. TINH DOC LAP GIUA CAC KY");print(line)
rep=Counter(len(set(a)&set(b)) for a,b in zip(draws[:-1],draws[1:]))
er=[(N-1)*stats.binom.pmf(k,6,6/45) for k in range(7)]
c2=sum((rep.get(k,0)-er[k])**2/er[k] for k in range(7))
print("  trung so voi ky truoc:",dict(sorted(rep.items())))
print("  chi2 vs Binom(6,6/45)=%.2f p=%.4f (mean %.3f vs 0.800)"%(c2,stats.chi2.sf(c2,6),np.mean([len(set(a)&set(b)) for a,b in zip(draws[:-1],draws[1:])])))
h=N//2
for nm,(A,B) in [("nua dau",(draws[:h],draws[1:h+1])),("nua sau",(draws[h:],draws[h+1:]))]:
    rc=Counter(len(set(a)&set(b)) for a,b in zip(A,B)); M=len(A)
    e=[M*stats.binom.pmf(k,6,6/45) for k in range(7)]
    cc=sum((rc.get(k,0)-e[k])**2/e[k] for k in range(7))
    print("  %s: p=%.4f"%(nm,stats.chi2.sf(cc,6)))
print("  -> khong on dinh giua 2 nua => nhieu ngau nhien, khong phai quy luat")

def acf(x,lags):
    x=np.asarray(x,float); x=x-x.mean(); d=np.sum(x*x)
    return [float(np.sum(x[:-l]*x[l:])/d) for l in lags]
print(line);print("5. TUONG QUAN CHUOI");print(line)
print("  ACF tong lag1..5:",["%.3f"%v for v in acf(sums,range(1,6))])
sign=sums>np.median(sums)
runs=1+sum(1 for a,b in zip(sign,sign[1:]) if a!=b); n1=int(sign.sum()); n2=len(sign)-n1
mu=2*n1*n2/(n1+n2)+1; var=2*n1*n2*(2*n1*n2-n1-n2)/((n1+n2)**2*(n1+n2-1))
z=(runs-mu)/math.sqrt(var)
print("  runs test p=%.4f"%(2*(1-stats.norm.cdf(abs(z)))))
acs=np.array([acf([1 if n in d else 0 for d in draws],range(1,4)) for n in range(1,46)])
print("  ACF chi bao tung so lag1..3:",["%.4f"%v for v in acs.mean(0)],"| vuot CI95:",[int((np.abs(acs[:,i])>1.96/math.sqrt(N)).sum()) for i in range(3)],"/45")
pairs=np.zeros((46,46))
for d in draws:
    for a,b in itertools.combinations(d,2): pairs[a][b]+=1; pairs[b][a]+=1
vals=np.array([pairs[a][b] for a in range(1,46) for b in range(a+1,46)])
ep=N*15/(45*44/2)
cp2=float(np.sum((vals-ep)**2/ep))
print("  cap so: chi2=%.2f df=%d p=%.4f mean=%.2f (lt %.2f)"%(cp2,len(vals)-1,stats.chi2.sf(cp2,len(vals)-1),vals.mean(),ep))

print(line);print("6. GAP (so ky vang mat)");print(line)
g=[]
for n in range(1,46):
    last=None
    for i,d in enumerate(draws):
        if n in d:
            if last is not None: g.append(i-last)
            last=i
g=np.array(g); p=6/45
ob=Counter(g.tolist()); ex={k:len(g)*((1-p)**(k-1))*p for k in range(1,20)}
cc=sum((ob.get(k,0)-ex[k])**2/ex[k] for k in range(1,20))
print("  n=%d mean=%.3f (lt 7.5) | chi2(1..19+)=%.2f df=18 p=%.4f"%(len(g),g.mean(),cc,stats.chi2.sf(cc,18)))
print("  P(gap>=20) obs=%.4f lt=%.4f (KS hinh hoc fail chi vi tinh roi rac)"%((g>=20).mean(),(1-p)**19))

print(line);print("7. BACKTEST DU DOAN (75% train -> 25% test)");print(line)
split=int(N*0.75)
def top6(sc): return set(sorted(range(1,46),key=lambda n:(-sc.get(n,0),n))[:6])
def bt(fn):
    hist=list(draws[:split]); hit=0; tot=0; anyh=0
    for i in range(split,N):
        pk=top6(fn(hist)); ac=set(draws[i])
        hit+=len(pk&ac); tot+=len(pk); anyh+=1 if pk&ac else 0
        hist.append(draws[i])
    return hit/tot, anyh/(N-split)
def scf(w=None):
    def f(h):
        hh=h[-w:] if w else h
        return Counter(n for d in hh for n in d)
    return f
def scm(h):
    tr=defaultdict(int); ct=defaultdict(int)
    for a,b in zip(h,h[1:]):
        for n in set(a):
            ct[n]+=1
            if n in set(b): tr[n]+=1
    return {n:tr[n]/ct[n] for n in ct if ct[n]>10}
def scr(h):
    import random; random.seed(999); return Counter({n:random.random() for n in range(1,46)})
def scn(w):
    def f(h): return {n:-v for n,v in scf(w)(h).items()}
    return f
print("  baseline (ngau nhien) = 6/45 = %.4f"%p)
for nm,fn in [("hot all",scf()),("hot 100",scf(100)),("hot 300",scf(300)),("cold 100",scn(100)),("markov",scm),("random",scr)]:
    hr,ar=bt(fn); print("  %-10s hit=%.4f any=%.4f"%(nm,hr,ar))

# logistic walk-forward
def build(b):
    X=[];Y=[];gp=defaultdict(lambda:99); fq=Counter(); seen=0
    for i in range(1,len(b)):
        s=set(b[i]); ps=[set(x) for x in b[i-5:i][::-1]]
        for n in range(1,46):
            f=[1.0 if k<len(ps) and n in ps[k] else 0.0 for k in range(5)]
            f+=[sum(1 for x in b[max(0,i-50):i] if n in x)/50.0, fq[n]/max(1,seen*6/45), math.log1p(gp[n])]
            X.append(f); Y.append(1.0 if n in s else 0.0)
        for n in s: gp[n]=0
        for n in range(1,46):
            if n not in s: gp[n]+=1
        for n in s: fq[n]+=1
        seen+=1
    return np.array(X),np.array(Y)
Xt,Yt=build(draws[:split]); Xe,Ye=build(draws[split:])
mu=Xt.mean(0); sd=Xt.std(0)+1e-9
A=np.hstack([np.ones((len(Xt),1)),(Xt-mu)/sd]); B=np.hstack([np.ones((len(Xe),1)),(Xe-mu)/sd])
def nll(w):
    z=A@w; q=1/(1+np.exp(-z))
    return -np.mean(Yt*np.log(q+1e-12)+(1-Yt)*np.log(1-q+1e-12))
w=optimize.minimize(nll,np.zeros(A.shape[1]),method="L-BFGS-B").x
pe=1/(1+np.exp(-(B@w)))
auc=lambda y,s:(stats.rankdata(np.concatenate([s[y==1],s[y==0]]))[:int(y.sum())].sum()-y.sum()*(y.sum()+1)/2)/(y.sum()*(len(y)-y.sum()))
print("  logistic AUC=%.4f  logloss lift=%+.6f nats (0 = vo dung)"%(auc(Ye,pe),
    -np.mean(Ye*np.log(Ye.mean())+(1-Ye)*np.log(1-Ye.mean()))+np.mean(Ye*np.log(pe+1e-12)+(1-Ye)*np.log(1-pe+1e-12))))

print(line);print("8. CONG THUC GIAI THUONG / VE BAN RA");print(line)
print("  bang giai: nhat=5/6 (10tr)  nhi=4/6 (300k)  ba=3/6 (30k)")
print("  ty le nhi/ba obs=%.5f vs lt %.5f | nhat/nhi obs=%.5f vs lt %.5f"%(g2.mean()/g3.mean(),P2/P3,g1.mean()/g2.mean(),P1/P2))
T=g3/P3
print("  ve ban ra/ky: mean=%.2fM median=%.2fM max=%.2fM"%(T.mean()/1e6,np.median(T)/1e6,T.max()/1e6))
print("  kiem chung: lambda=%.4f -> P(co jackpot)=%.4f vs thuc te %.4f"%(np.mean(T/C),np.mean(1-np.exp(-T/C)),(win>0).mean()))

print(line);print("9. CONG THUC JACKPOT (rollover)");print(line)
inc=jp[1:]-jp[:-1]; ok=(win[:-1]==0)
sl,ic,r_,_,_=stats.linregress(g2[1:][ok],inc[ok])
pred=jp[:-1]+sl*g2[1:]
print("  J[i+1] = J[i] + k*G2[i+1],  k=%.0f VND/1 nguoi giai nhi, R2=%.4f"%(sl,1-np.var(jp[1:][ok]-pred[ok])/np.var(jp[1:][ok])))
print("  reset: P(J giam | co winner)=%.2f, P(J giam | khong winner)=%.2f"%(np.mean([jp[i+1]<jp[i] for i in range(N-1) if win[i]>0]),np.mean([jp[i+1]<jp[i] for i in range(N-1) if win[i]==0])))
print("  ACF lag1=%.3f lag2=%.3f lag5=%.3f"%(np.corrcoef(jp[:-1],jp[1:])[0,1],np.corrcoef(jp[:-2],jp[2:])[0,1],np.corrcoef(jp[:-5],jp[5:])[0,1]))
print("  phan vi (B): p10=%.1f p50=%.1f p90=%.1f p99=%.1f max=%.1f"%tuple(list(np.percentile(jp,[10,50,90,99])/1e9)+[jp.max()/1e9]))

print(line);print("10. EV & DIEM HOA VON");print(line)
fix=P1*1e7+P2*3e5+P3*3e4
print("  EV phan co dinh = %.0f VND/ve (%.2f%%)"%(fix,100*fix/1e4))
print("  %-9s %-9s %-10s %s"%("J","ve ban","EV","+EV?"))
for J,tk in [(12e9,0.9e6),(30e9,1.2e6),(50e9,2.0e6),(80e9,3.5e6),(100e9,5.0e6),(150e9,7.5e6),(200e9,8.0e6)]:
    ev=fix+(1/C)*J/(1+tk/C)*0.9
    print("  %-9s %-9s %-10.0f %s"%("%.0fB"%(J/1e9),"%0.0fM"%(tk/1e6),ev,"YES" if ev>1e4 else "no"))
print("  diem hoa von: 1M ve -> %.0fB | 2M -> %.0fB | 4M -> %.0fB | 8M -> %.0fB"%(*( (1e4-fix)*(1+t/C)*C/0.9/1e9 for t in [1e6,2e6,4e6,8e6]),))

print(line);print("11. HINH DANG CO ANH HUONG CHIA GIAI?");print(line)
d=np.array(draws)
low31=(d<=31).sum(1)
cons=np.array([sum(1 for x in set(t) if x+1 in set(t)) for t in draws])
even=np.array([sum(1 for x in t if x%2==0) for t in draws])
m=win>0
for nm,f in [("low<=31",low31),("lien tiep",cons),("so chan",even),("tong",sums),("giai ba",g3)]:
    r1,p1=stats.spearmanr(f,win)
    print("  %-10s rho=%+.4f p=%.4f"%(nm,r1,p1))
print("  -> chi co luong ban ve (giai ba) tac dong, hinh dang khong")

last={n:max(i for i,d in enumerate(draws) if n in d) for n in range(1,46)}
prev=set(draws[-1])
def pen(c):
    s=set(c); sm=sum(c)
    odd=sum(1 for x in c if x%2); low=sum(1 for x in c if x<=22)
    cons=sum(1 for x in c if x+1 in s); span=max(c)-min(c)
    return ((sm-138)/29.0)**2*3.0+abs(odd-3)*.55+abs(low-3)*.55+max(0,cons-1)*.85+((span-32)/9.0)**2*.6+len(s&prev)*.35
def fs(c):
    z=sum((freq[n]-211.47)/11.41 for n in c)/6.0
    od=sum((N-1-last[n]) for n in c)/6.0
    return -0.9*z-0.006*od
combos=sorted(((pen(c)+fs(c),c) for c in itertools.combinations(range(1,46),6)),key=lambda t:(t[0],t[1]))
print(line);print("12. VE THAM KHAO (can bang, KHONG phai du doan)");print(line)
for sc,c in combos[:12]:
    s=set(c)
    print("  %s  tong=%d le=%d nho=%d lien=%d"%(("-".join("%02d"%x for x in c)),sum(c),sum(1 for x in c if x%2),sum(1 for x in c if x<=22),sum(1 for x in c if x+1 in s)))
print("  ky gan nhat:", "-".join("%02d"%x for x in draws[-1]), raw[-1]["draw_date"])