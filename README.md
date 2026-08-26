# 글로벌 스크리닝 30 — 모의 포트폴리오 자동 트래킹

**사이트: https://jungjun2016-create.github.io/portfolio/**

나스닥 시총 Top 300 · 한국 Top 100 · 홍콩 Top 300에서 차트를 1차 기준으로 고르고
밸류·성장을 가점으로 얹어 국가별 10종목씩 30종목을 담은 $100,000 모의 포트폴리오.
V3 개시 2026-08-21.

## 자동 갱신
GitHub Actions가 **평일 07:30 / 17:30 KST**에 Yahoo Finance에서 종가·환율·벤치마크를 받아
스냅샷을 추가하고 `index.html`을 다시 만들어 커밋한다. 월요일 회차엔 주봉 60주 차트도 갱신한다.

즉시 갱신이 필요하면 Actions 탭 → `포트폴리오 갱신` → **Run workflow**.
(`weekly` 체크 시 주봉 차트까지)

## 구성
| 경로 | 역할 |
|---|---|
| `data/state.json` | 정본 데이터 — meta / holdings 30 / snapshots / details |
| `build/fetch_prices.py` | 시세 수집 → 스냅샷 추가 (`--weekly`로 주봉도) |
| `build/render.py` | `state.json` → `index.html` |
| `build/css.txt`, `build/app.js` | 스타일 / 차트·상세 패널 스크립트 |
| `.github/workflows/update.yml` | 스케줄 + 수동 실행 |
| `index.html` | **산출물. 직접 편집하지 말 것** |

## 안전장치
- 30종목 전부 양수 가격일 때만 저장
- 직전 종가 대비 **50% 이상 급변**이면 데이터 오류로 보고 저장 중단
- 같은 날짜 재실행은 마지막 스냅샷만 덮어쓰고 과거 이력은 지우지 않음
- Yahoo가 데이터센터 IP를 429로 막는 데 대비해 쿠키+crumb → 일괄 quote → 개별 chart → stooq 4단 폴백

## 수동으로 손봐야 하는 것
재무제표·사업부문·비즈니스 모델·뉴스(`details`)는 자동화 대상이 아니다. 분기 실적 시즌에 `data/state.json`을 교체한다.

> 실제 투자 포트폴리오가 아니라 스크리닝 모델을 추적하기 위한 모의 포트폴리오다.
