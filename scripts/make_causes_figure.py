"""28개 사인 지도 SVG를 만든다. 사용: python3 scripts/make_causes_figure.py data/checkup/causes.json docs/figures/causes28.svg"""
import json,sys
from xml.sax.saxutils import escape as e
d=json.load(open(sys.argv[1]))['causes']
MENU={2:"규제팡 (라)란",4:"개인정보·데이터",7:"거래·자금",8:"거래·자금",9:"설립·지배구조",10:"노무 검진",11:"설립·지배구조",
13:"투자계약 검진",14:"투자계약 검진",15:"거래·자금",16:"노무 검진",17:"거래·자금",19:"개인정보·데이터",20:"개인정보·데이터",
21:"노무 검진",22:"규제팡",23:"규제팡",24:"규제팡",25:"규제팡",26:"규제팡",27:"투자계약 검진",28:"규제팡"}
ST={}
for n in [22,23,24,25,26]: ST[n]="impl"
for n in [2,28]: ST[n]="part"
for n in [10,13,14,16,21,27]: ST[n]="demo"
for n in [4,7,8,9,11,15,17,19,20]: ST[n]="road"
for n in [1,3,5,6,12,18]: ST[n]="none"
C="#A51C30"
def wrap(s,n):
    out=[];cur=""
    for w in s.split(" "):
        if cur and len(cur)+1+len(w)>n: out.append(cur);cur=w
        else: cur=(cur+" "+w).strip()
    out.append(cur)
    res=[]
    for l in out:
        while len(l)>n: res.append(l[:n]); l=l[n:]
        res.append(l)
    return res
def card(x,y,w,h,c):
    n=c['no']; st=ST[n]; name=c['name']
    main,_,sub=name.partition(" — ")
    part=c['part'].split("·")[-1]
    if st=="impl": fill,stroke,sw,num,tx,mx=C,C,0,"#fff","#fff","#F6E1E5"
    elif st=="part": fill,stroke,sw,num,tx,mx="#FBF2F3",C,3,C,"#1b1f24",C
    elif st=="demo": fill,stroke,sw,num,tx,mx="#fff",C,3,C,"#1b1f24",C
    elif st=="road": fill,stroke,sw,num,tx,mx="#fff","#adb5bd",2,"#5b6573","#343a40","#5b6573"
    else: fill,stroke,sw,num,tx,mx="#f1f3f5","#f1f3f5",0,"#adb5bd","#868e96","#adb5bd"
    dash=' stroke-dasharray="8 5"' if st=="part" else ""
    s=[f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>']
    s.append(f'<text x="{x+16}" y="{y+40}" font-size="30" font-weight="700" fill="{num}">{n}</text>')
    if n>12: s.append(f'<text x="{x+w-14}" y="{y+34}" font-size="15" text-anchor="end" fill="{mx}">{e(part)}</text>')
    lines=wrap(main,int((w-30)/21))
    yy=y+74
    for l in lines[:2]:
        s.append(f'<text x="{x+16}" y="{yy}" font-size="21" font-weight="700" fill="{tx}">{e(l)}</text>'); yy+=27
    if sub:
        for l in wrap(sub,int((w-30)/15.5))[:2]:
            s.append(f'<text x="{x+16}" y="{yy-2}" font-size="15" fill="{tx}" opacity="0.85">{e(l)}</text>'); yy+=20
    lab={"impl":MENU.get(n,""),"part":MENU.get(n,"")+" · 일부","demo":MENU.get(n,""),"road":MENU.get(n,"")+" · 로드맵","none":"경영 사인 · 검진 대상 아님"}[st]
    s.append(f'<text x="{x+16}" y="{y+h-16}" font-size="15" font-weight="600" fill="{mx}">{e(lab)}</text>')
    return "\n".join(s)
o=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080" font-family="\'Noto Sans KR\',\'Pretendard\',\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif">','<rect width="1920" height="1080" fill="#fff"/>',
f'<text x="60" y="88" font-size="44" font-weight="700" fill="#1b1f24">스타트업이 죽는 28가지 사인, <tspan fill="{C}">스타트업 리걸닥터</tspan>가 죽기 전에 검진함</text>',
'<text x="62" y="132" font-size="23" fill="#5b6573">「스타트업 부검보고서」 사인 체계 · 법률 사인 22개 가운데 13개를 지금 검진하고 9개는 같은 엔진으로 넓힘</text>']
by={c['no']:c for c in d}
# left panel 병사
o.append('<rect x="60" y="160" width="690" height="800" rx="22" fill="#f8f9fa"/>')
o.append('<text x="84" y="202" font-size="24" font-weight="700" fill="#343a40">병사 <tspan font-size="18" font-weight="400" fill="#5b6573">회사 안에서 생긴 원인 · 12</tspan></text>')
W,H,G=206,172,14
for i,n in enumerate(range(1,13)):
    r,cc=divmod(i,3); o.append(card(80+cc*(W+G),222+r*(H+G),W,H,by[n]))
o.append('<rect x="770" y="160" width="1090" height="800" rx="22" fill="#FBF2F3"/>')
o.append(f'<text x="794" y="202" font-size="24" font-weight="700" fill="{C}">외인사 <tspan font-size="18" font-weight="400" fill="#5b6573">계약 상대방·사고·규제가 원인 · 16 (타살 13–17 · 사고사 18–19 · 복합 20–21 · 의원성 22–28)</tspan></text>')
W2=253
for i,n in enumerate(range(13,29)):
    r,cc=divmod(i,4); o.append(card(790+cc*(W2+G),222+r*(H+G),W2,H,by[n]))
# legend
lx=60;ly=1012
items=[("impl","구현 5"),("part","구현(일부) 2"),("demo","시연 구현 6"),("road","로드맵 9"),("none","법률 검진 대상 아님 6")]
sty={"impl":(C,C,0,""),"part":("#FBF2F3",C,3,' stroke-dasharray="6 4"'),"demo":("#fff",C,3,""),"road":("#fff","#adb5bd",2,""),"none":("#f1f3f5","#f1f3f5",0,"")}
x=lx
for k,lab in items:
    f,s,sw,da=sty[k]
    o.append(f'<rect x="{x}" y="{ly-22}" width="34" height="26" rx="6" fill="{f}" stroke="{s}" stroke-width="{sw}"{da}/>')
    o.append(f'<text x="{x+44}" y="{ly-1}" font-size="20" fill="#343a40">{e(lab)}</text>')
    x+=44+len(lab)*20+40
o.append(f'<text x="1860" y="{ly-1}" font-size="20" text-anchor="end" fill="{C}" font-weight="700">위험이 높으면 변호사 심화자문으로 연결</text>')
o.append('</svg>')
open(sys.argv[2],'w').write("\n".join(o))
