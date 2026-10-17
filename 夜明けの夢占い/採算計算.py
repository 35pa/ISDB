import math
MAU_STD=[0,0,500,1500,3000,5000,8000,11000,15000,20000,26000,33000]
PRICE=680; SPOT=900; FEE=0.036
FREE_USES=4; HAIKU=0.16
PAID_USES=20; OPUS=6.3; REPORT=15; SPOT_AI=15
RPM=200; PV_PER_MAU=15
def line_cost(n):
    msgs=n*30
    if n==0: return 0
    if msgs<=5000: return 5000*1.1
    if msgs<=30000: return 15000*1.1
    return (15000+(msgs-30000)*3)*1.1
def host(m,mau): return 1000 if mau<=3000 else (4000 if mau<=10000 else 8000)
def run(scale,conv,spot_rate,ad_from=7,ad=30000,label=""):
    cum=0; rows=[]; be=None
    for i,base in enumerate(MAU_STD):
        m=i+1; mau=int(base*scale)
        paid=int(mau*conv) if m>=5 else 0
        spot=int(mau*spot_rate) if m>=5 else 0
        free=mau-paid
        rev_sub=paid*PRICE; rev_spot=spot*SPOT; rev_ad=mau*PV_PER_MAU/1000*RPM
        rev=rev_sub+rev_spot+rev_ad
        ai=free*FREE_USES*HAIKU+paid*(PAID_USES*OPUS+REPORT)+spot*SPOT_AI+(5000 if m<=2 else 0)
        stripe=(rev_sub+rev_spot)*FEE
        ln=line_cost(paid)
        hs=host(m,mau)+150
        adv=ad if m>=ad_from else 0
        cost=ai+stripe+ln+hs+adv
        prof=rev-cost; cum+=prof
        if be is None and prof>0 and m>=5: be=m
        rows.append((m,mau,paid,spot,rev,ai,stripe,ln,hs,adv,cost,prof,cum))
    print("==",label)
    for r in rows: print("%2d mau%6d paid%5d spot%4d rev%9.0f ai%8.0f str%7.0f line%7.0f host%6.0f adv%6.0f cost%9.0f prof%9.0f cum%10.0f"%r)
    mincum=min(r[12] for r in rows)
    print("break-even month",be,"min cum",round(mincum), "year profit", round(rows[-1][12]))
run(1,0.03,0.0076,label="std")
run(0.5,0.02,0.005,label="cons")
run(1.5,0.04,0.01,label="opt")
# unit economics
per=PRICE-PRICE*FEE-(PAID_USES*OPUS+REPORT)
print("per member margin",per)
