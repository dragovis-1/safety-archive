"""국가법령정보센터 PDF(법제처 출력본)를 조문 단위로 잘라 data/laws.json을 만든다.
법제처 API 승인 전 미리보기용. API가 붙으면 fetch_laws.py가 같은 형식으로 덮어쓴다.
사용: python scripts/build_laws_from_pdf.py <PDF 폴더>   (pdftotext 필요)"""
import json, os, re, subprocess, sys, datetime

LIST = json.load(open(os.path.join(os.path.dirname(__file__), "laws_list.json"), encoding="utf-8"))
ART = re.compile(r"^제(\d+)조(?:의(\d+))?\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)\s?(.*)$")
HEAD = re.compile(r"^\s*제\d+(편|장|절|관)\s")
NEWLINE_START = re.compile(r"^([①-⑳]|\d{1,3}\.\s|\d{1,3}의\d+\.\s|[가-하]\.\s|\[|<|\d{1,2}\)\s)")

def text_of(pdf):
    return subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout

def parse(raw, name):
    m = re.search(r"\[시행\s*([\d.\s]+)\]\s*\[([^\]]+)\]", raw)
    eff = re.sub(r"\s", "", m.group(1)).rstrip(".") if m else ""
    prom = m.group(2).strip() if m else ""
    arts, cur, ch = [], None, {}
    for line in raw.split("\n"):
        s = line.rstrip()
        if not s.strip(): continue
        if re.match(r"^법제처\s+\d+\s+국가법령정보센터", s.strip()): continue
        if s.strip() == name or s.strip().startswith(name + " ("): continue
        if re.match(r"^\s*부\s*칙", s): break
        if HEAD.match(s) and not s.startswith("제"):
            lvl = HEAD.match(s).group(1); ch[lvl] = s.strip()
            for low in {"편": "장절관", "장": "절관", "절": "관", "관": ""}[lvl]: ch.pop(low, None)
            cur = None; continue
        a = ART.match(s)
        if a:
            no, sub, title, rest = a.groups()
            k = no + ("-" + sub if sub else "")
            cur = {"k": k, "n": f"제{no}조" + (f"의{sub}" if sub else ""), "t": title.strip(),
                   "ch": " · ".join(ch[l] for l in "편장절관" if l in ch), "lines": [rest.strip()] if rest.strip() else []}
            arts.append(cur); continue
        if re.match(r"^제\d+조(의\d+)?\s+삭제", s): cur = None; continue
        if cur is None: continue
        body = s.strip()
        prev = cur["lines"][-1] if cur["lines"] else ""
        # "…하여야 한\n다." 처럼 줄바꿈으로 잘린 어미는 목(가.나.다.)이 아님
        wrapped_da = body.startswith("다.") and re.search(r"[한된있없니았었였같않]$", prev)
        if not cur["lines"] or (NEWLINE_START.match(body) and not wrapped_da): cur["lines"].append(body)
        else:
            # PDF는 줄 끝 공백이 사라져서 조사로 끝난 줄만 띄어 붙인다(추정)
            sep = " " if re.search(r"([,.)」>\]을를은는및]|개정|신설)$", prev) or re.match(r"^[「“(<]", body) else ""
            cur["lines"][-1] = prev + sep + body
    seen, out = set(), []
    for a in arts:
        if a["k"] in seen: continue  # 목차 중복 방지
        seen.add(a["k"]); x = "\n".join(a.pop("lines")).strip()
        if not x: continue
        a["x"] = x; out.append(a)
    return eff, prom, out

def main():
    folder = sys.argv[1]
    files = os.listdir(folder); laws = []
    for L in LIST:
        f = next((f for f in files if f.lower().endswith(".pdf") and
                  re.sub(r"(\.pdf)+$", "", f.split("(")[0], flags=re.I).strip() == L["name"]), None)
        if not f: print("PDF 없음:", L["name"]); continue
        eff, prom, arts = parse(text_of(os.path.join(folder, f)), L["name"])
        print(f"{L['name']}: {len(arts)}개 조문 (시행 {eff})")
        laws.append({**L, "effective": eff, "prom": prom, "src": "pdf", "articles": arts})
    kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    json.dump({"updated": kst.strftime("%Y-%m-%d %H:%M"), "source": "pdf", "laws": laws},
              open("data/laws.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__": main()
