"""안전보건공단 국내재해사례 API에서 전체 사례를 받아 data/cases.json으로 저장.
GitHub Actions에서 매일 실행. 인증키는 환경변수 DATA_GO_KR_KEY (저장소 Secrets)."""
import json,re,sys,os,time,urllib.request,urllib.parse,datetime,collections
REG=[('서울','서울'),('부산','부산'),('대구','대구'),('인천','인천'),('광주','광주'),('대전','대전'),('울산','울산'),('세종','세종'),('경기','경기'),('강원','강원'),
('충청북','충북'),('충북','충북'),('충청남','충남'),('충남','충남'),('전라북','전북'),('전북','전북'),('전라남','전남'),('전남','전남'),('경상북','경북'),('경북','경북'),('경상남','경남'),('경남','경남'),('제주','제주')]
TYPES=[('떨어짐',['떨어짐','추락','떨어져','떨어지']),('끼임',['끼임','협착','끼여','끼어','말려']),('깔림',['깔림','깔려','전도되','넘어지면서']),
('무너짐',['무너짐','붕괴','무너져','매몰']),('맞음',['맞음','맞아','낙하','날아온','비래']),('부딪힘',['부딪힘','충돌','부딪','치임','받힘','치여']),
('화재·폭발',['화재','폭발','파열','화상']),('질식·중독',['질식','중독','가스','산소결핍','밀폐']),('감전',['감전','전류','충전부']),
('넘어짐',['넘어짐','미끄러','전도']),('절단·베임',['절단','베임','베여','잘림']),('익사',['익사','물에 빠'])]
TAGS={'크레인':['크레인','기중기','호이스트','양중','인양','줄걸이','타워크레인','카고크레인'],'지게차':['지게차'],'고소작업대':['고소작업대','시저','스카이'],
'사다리':['사다리','말비계'],'비계':['비계','작업발판'],'굴착기':['굴착기','굴삭기','포크레인','백호'],'화물차':['화물차','화물자동차','트럭','덤프'],
'컨베이어':['컨베이어'],'프레스':['프레스'],'롤러':['롤러','롤'],'밀폐공간':['밀폐공간','맨홀','탱크 내부','저장조','정화조','오수','집수정'],
'지붕':['지붕','썬라이트','슬레이트','채광창'],'개구부':['개구부','단부','엘리베이터 피트','승강로'],'해체':['해체','철거'],
'용접':['용접','용단','절단기'],'벌목':['벌목','수목','나무','가지치기'],'정비·수리':['정비','수리','보수','점검','청소'],'중량물':['중량물','철골','강관','자재','판넬','코일'],
'선박':['선박','블록','도장','선체'],'전기':['전기','배전','분전반','전선','충전부'],'거푸집':['거푸집','동바리','데크플레이트'],'차량':['차량','후진','승용차']}
def first(text,pairs):
    for k,v in pairs:
        if k in text: return v

API="https://apis.data.go.kr/B552468/disaster_api02/getdisaster_api02"
def page(key,n,rows=1000):
    q=urllib.parse.urlencode({"serviceKey":key,"callApiId":"1060","pageNo":n,"numOfRows":rows})
    for i in range(3):
        try:
            with urllib.request.urlopen(API+"?"+q,timeout=60) as r: raw=r.read().decode("utf-8")
            d=json.loads(raw); b=d.get("body") or d.get("response",{}).get("body")
            if not b: raise ValueError(raw[:300])
            it=(b.get("items") or {}).get("item") or []
            return (it if isinstance(it,list) else [it]), int(b.get("totalCount",0))
        except Exception as e:
            print(f"page {n} try {i+1} failed: {e}",file=sys.stderr); time.sleep(5)
    raise SystemExit(f"page {n} failed")
def main():
    key=os.environ.get("DATA_GO_KR_KEY") or sys.exit("DATA_GO_KR_KEY 없음")
    items,total=page(key,1); n=2
    while len(items)<total and n<=50:
        more,_=page(key,n)
        if not more: break
        items+=more; n+=1
    if len(items)<100: sys.exit(f"너무 적게 받음({len(items)}건) - 기존 자료 유지")
    out=[];seen=set()
    for it in items:
        if it.get("boardno") in seen: continue
        seen.add(it.get("boardno"))
        t=(it.get('keyword') or '').strip(); c=re.sub(r'\s+',' ',(it.get('contents') or '').strip())
        bn=it.get('boardno','')
        m=re.search(r'(20\d\d)\s*[.년]\s*(\d{1,2})',c)
        y=int(m.group(1)) if m else int(bn[:4]); mo=int(m.group(2)) if m and 1<=int(m.group(2))<=12 else 0
        if y>datetime.date.today().year or y<2010: y=int(bn[:4])
        reg=first(c,REG) or ''
        ty='기타'
        for src in (t,c):
            for k,ws in TYPES:
                if any(w in src for w in ws): ty=k;break
            if ty!='기타':break
        tg=[k for k,ws in TAGS.items() if any(w in t+' '+c for w in ws)][:5]
        out.append({'id':bn,'b':it.get('business',''),'t':t,'c':c,'y':y,'m':mo,'r':reg,'ty':ty,'tg':tg,'p':bn[:8]})
    kst=datetime.datetime.utcnow()+datetime.timedelta(hours=9)
    os.makedirs("data",exist_ok=True)
    json.dump({"updated":kst.strftime("%Y-%m-%d %H:%M"),"apiTotal":total,"cases":out},open("data/cases.json","w"),ensure_ascii=False,separators=(",",":"))
    print(f"saved {len(out)} / total {total}")
if __name__=="__main__": main()
