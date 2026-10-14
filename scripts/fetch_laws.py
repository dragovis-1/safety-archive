"""법제처 국가법령정보 Open API에서 scripts/laws_list.json의 현행 법령 조문을 받아 data/laws.json으로 저장.
GitHub Actions에서 실행. 인증값은 환경변수 LAW_OC (저장소 Secrets).
- LAW_OC가 없으면 아무것도 안 하고 끝냄(PDF 미리보기 자료 유지)
- 어떤 법령을 못 받으면 그 법령만 기존 자료를 유지"""
import json, os, re, sys, time, datetime, urllib.request, urllib.parse

BASE = "https://www.law.go.kr/DRF/"
HERE = os.path.dirname(__file__)
LIST = json.load(open(os.path.join(HERE, "laws_list.json"), encoding="utf-8"))
OUT = "data/laws.json"

def get(path, **q):
    url = BASE + path + "?" + urllib.parse.urlencode({"OC": OC, "type": "JSON", **q})
    last = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 safety-archive"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", "replace")
            try:
                d = json.loads(raw)
            except ValueError:
                raise RuntimeError("JSON 아님(인증·IP 문제일 수 있음): " + re.sub(r"\s+", " ", raw)[:200])
            if isinstance(d, dict) and ("result" in d or "msg" in d) and len(d) <= 3:
                raise RuntimeError(f"API 오류: {d}")
            return d
        except Exception as e:
            last = e; print(f"  {path} 재시도 {i+1}: {e}", file=sys.stderr); time.sleep(3)
    raise last

def as_list(v):
    if v is None: return []
    return v if isinstance(v, list) else [v]

def txt(v):
    """API 값은 문자열, 문자열 배열, {'content':..} 등 섞여 옴"""
    if v is None: return ""
    if isinstance(v, str): return v.strip()
    if isinstance(v, dict): return txt(v.get("content", ""))
    if isinstance(v, list): return "\n".join(t for t in (txt(x) for x in v) if t)
    return str(v)

def find_mst(name):
    d = get("lawSearch.do", target="law", query=name, display=100)
    rows = as_list((d.get("LawSearch") or {}).get("law"))
    exact = [r for r in rows if txt(r.get("법령명한글")) == name]
    cur = [r for r in exact if txt(r.get("현행연혁코드")) in ("현행", "")] or exact
    if not cur: raise RuntimeError(f"검색 결과에 '{name}' 없음 (후보: {[txt(r.get('법령명한글')) for r in rows[:5]]})")
    return txt(cur[0].get("법령일련번호")), cur[0]

def fmt_date(s):
    s = re.sub(r"\D", "", s or "")
    return f"{int(s[:4])}.{int(s[4:6])}.{int(s[6:8])}" if len(s) == 8 else s

def parse_articles(units):
    arts, ch = [], {}
    for u in as_list(units):
        body = txt(u.get("조문내용"))
        if txt(u.get("조문여부")) == "전문":  # 편·장·절 제목
            m = re.match(r"\s*제\d+(편|장|절|관)", body)
            if m:
                lvl = m.group(1); ch[lvl] = re.sub(r"\s+", " ", body.strip())
                for low in {"편": "장절관", "장": "절관", "절": "관", "관": ""}[lvl]: ch.pop(low, None)
            continue
        no, sub = txt(u.get("조문번호")), txt(u.get("조문가지번호"))
        if not no: continue
        title = txt(u.get("조문제목"))
        head = re.sub(r"^\s*제\d+조(의\d+)?\s*(\([^)]*\))?\s*", "", body)
        if re.match(r"^삭제", head) and not u.get("항"): continue
        lines = [head] if head else []
        for h in as_list(u.get("항")):
            if not isinstance(h, dict): continue
            if txt(h.get("항내용")): lines.append(txt(h.get("항내용")))
            for ho in as_list(h.get("호")):
                if not isinstance(ho, dict): continue
                if txt(ho.get("호내용")): lines.append(txt(ho.get("호내용")))
                for mok in as_list(ho.get("목")):
                    if isinstance(mok, dict) and txt(mok.get("목내용")): lines.append(txt(mok.get("목내용")))
        x = "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in lines if l.strip())
        if not x: continue
        arts.append({"k": no + ("-" + sub if sub and sub != "0" else ""),
                     "n": f"제{no}조" + (f"의{sub}" if sub and sub != "0" else ""),
                     "t": title, "ch": " · ".join(ch[l] for l in "편장절관" if l in ch), "x": x})
    return arts

def fetch_one(L):
    mst, row = find_mst(L["name"])
    d = get("lawService.do", target="law", MST=mst)
    law = d.get("법령") or d
    info = law.get("기본정보") or {}
    arts = parse_articles((law.get("조문") or {}).get("조문단위"))
    if len(arts) < 3: raise RuntimeError(f"조문이 너무 적음({len(arts)})")
    prom = f"{txt(info.get('법종구분')) or txt(row.get('법령구분명'))} 제{txt(info.get('공포번호')) or txt(row.get('공포번호'))}호, {fmt_date(txt(info.get('공포일자')) or txt(row.get('공포일자')))}"
    return {**L, "effective": fmt_date(txt(info.get("시행일자")) or txt(row.get("시행일자"))), "prom": prom,
            "dept": txt(info.get("소관부처")) or txt(row.get("소관부처명")), "mst": mst, "src": "api", "articles": arts}

def main():
    global OC
    OC = os.environ.get("LAW_OC", "").strip()
    if not OC:
        print("LAW_OC 없음 - 법령 갱신 건너뜀"); return
    old = {}
    if os.path.exists(OUT):
        old = {l["id"]: l for l in json.load(open(OUT, encoding="utf-8")).get("laws", [])}
    laws, ok = [], 0
    for L in LIST:
        try:
            got = fetch_one(L); laws.append(got); ok += 1
            print(f"{L['name']}: {len(got['articles'])}개 조문 (시행 {got['effective']})")
        except Exception as e:
            print(f"{L['name']}: 실패 - {e}", file=sys.stderr)
            if L["id"] in old: laws.append(old[L["id"]])
        time.sleep(0.5)
    if not ok: sys.exit("법령을 하나도 못 받음 - 기존 자료 유지 (OC 값, 신청한 API 종류, IP 등록 확인)")
    kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    json.dump({"updated": kst.strftime("%Y-%m-%d %H:%M"), "source": "api", "laws": laws},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"saved {ok}/{len(LIST)} laws")

OC = ""
if __name__ == "__main__": main()
