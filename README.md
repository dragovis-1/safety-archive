# safety-archive

사고사례 아카이브 — https://dragovis-1.github.io/safety-archive/

- `data/cases.json` — 안전보건공단 국내재해사례 (매일 자동 갱신, `update-cases.yml`, Secret `DATA_GO_KR_KEY`)
- `data/laws.json` — 법령 조문 (매일 자동 갱신, `update-laws.yml`, Secret `LAW_OC`)
  - 수록 법령 목록: `scripts/laws_list.json` (여기에 추가하면 다음 갱신 때 반영)
  - `LAW_OC`가 없거나 API 호출이 실패하면 기존 자료 유지
  - 처음 자료는 국가법령정보센터 PDF를 `scripts/build_laws_from_pdf.py`로 나눈 미리보기
- `data/law_links.json` — 사고유형·설비태그 → 관련 조문 매핑 (참고용, 직접 수정)
