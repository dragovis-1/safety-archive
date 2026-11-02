"""사고사례·법령 조문을 임베딩(문장 → 숫자 좌표)으로 바꿔 data/vectors.bin 으로 저장.

- 모델: intfloat/multilingual-e5-small (384차원, 한국어 지원)
  브라우저에서는 같은 모델의 ONNX 판(Xenova/multilingual-e5-small)으로 질문을 임베딩한다.
- e5 규칙: 문서는 "passage: ", 질문은 "query: " 를 앞에 붙인다.
- 저장 형식: int8(벡터×127)로 줄여서 저장. 순서는 vectors.json 의 ids 목록과 같다.
GitHub Actions(build-embeddings.yml)에서 사례·법령이 갱신될 때마다 실행.
"""
import json, os, sys, hashlib, datetime
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODEL = "intfloat/multilingual-e5-small"
OUT_BIN = os.path.join(ROOT, "data", "vectors.bin")
OUT_META = os.path.join(ROOT, "data", "vectors.json")


def load_docs():
    cases = json.load(open(os.path.join(ROOT, "data", "cases.json"), encoding="utf-8"))["cases"]
    laws = json.load(open(os.path.join(ROOT, "data", "laws.json"), encoding="utf-8"))["laws"]
    ids, texts = [], []
    for c in cases:
        ids.append("c:" + c["id"])
        texts.append(f"passage: {c['t']}. {c['c']}")
    for law in laws:
        for a in law["articles"]:
            ids.append("a:" + law["id"] + ":" + a["k"])
            texts.append(f"passage: {law['name']} {a['n']}({a.get('t') or ''}). {a['x'][:1200]}")
    return ids, texts


def encode(texts):
    if os.environ.get("FAKE_ENCODER"):  # 로컬 형식 점검용
        rng = np.random.default_rng(0)
        v = rng.normal(size=(len(texts), 384)).astype("float32")
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(MODEL, device="cpu")
    m.max_seq_length = 512
    return m.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True,
                    convert_to_numpy=True).astype("float32")


def main():
    ids, texts = load_docs()
    sig = hashlib.sha1("\n".join(texts).encode("utf-8")).hexdigest()
    if os.path.exists(OUT_META) and os.path.exists(OUT_BIN):
        old = json.load(open(OUT_META, encoding="utf-8"))
        if old.get("sig") == sig and old.get("model") == MODEL:
            print("내용 변화 없음 - 건너뜀"); return
    vec = encode(texts)
    q = np.clip(np.round(vec * 127), -127, 127).astype("int8")
    q.tofile(OUT_BIN)
    meta = {"model": MODEL, "browserModel": "Xenova/multilingual-e5-small", "dim": int(vec.shape[1]),
            "count": len(ids), "scale": 127, "sig": sig,
            "updated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
            "ids": ids}
    json.dump(meta, open(OUT_META, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(ids)}건 → {os.path.getsize(OUT_BIN)/1e6:.1f}MB")


if __name__ == "__main__":
    main()
