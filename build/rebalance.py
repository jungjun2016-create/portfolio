#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""월요일 아침 자동 리밸런싱 — 차트가 훼손된 보유 종목을 유니버스 상위 후보로 교체한다.

    python3 build/rebalance.py            # 판정 → 필요하면 교체하고 state.json 저장
    python3 build/rebalance.py --dry-run  # 판정만 하고 저장하지 않음
    python3 build/rebalance.py --force    # 요일 상관없이 실행

설계 원칙
  1) 필요할 때만 — 훼손 판정을 통과한 종목이 하나도 없으면 아무것도 바꾸지 않고 종료한다.
  2) 국가당 한 주 최대 10종목까지만 교체한다 (MAX_PER_MARKET).
  3) 교체는 자리 바꿔치기(in-place)다. 보유 종목 수·국가별 비중·총 평가액은 그대로다.
     매도 종목의 현재 평가액(USD)을 그대로 신규 종목에 넣어 수량을 계산하므로
     교체 순간 포트폴리오 평가액은 변하지 않는다.
  4) 과거 스냅샷은 절대 건드리지 않는다. 신규 종목에는 since(편입 스냅샷 인덱스)를 달아
     스파크라인이 이전 종목의 가격 이력을 물려받지 않게 한다.

판정 규칙 (Yahoo 주봉 60주로 계산 — 전부 시세만으로 재현 가능한 지표다)
    ma20 / ma40   20주·40주 이동평균
    dd            52주 고점 대비 낙폭
    mom12 / mom26 12주·26주 모멘텀
  훼손 점수 = 아래 항목 합산, DAMAGE_MIN 이상이면 교체 대상
    현재가 < ma40                     +2
    현재가 < ma20                     +1
    dd <= -25%                        +2   (-25% < dd <= -15% 이면 +1)
    mom12 <= -10%                     +2   (-10% < mom12 <= 0 이면 +1)
    ma40 하락 전환                    +1

후보 하드 게이트 — 하나라도 못 넘으면 편입하지 않는다
    현재가 > ma20 > ma40 / dd > -15% / mom12 > 0 / 시총 >= MIN_MCAP_USD / 주봉 40주 이상
"""
import json, os, sys, time, statistics
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_prices as fp  # 쿠키·crumb·폴백이 들어 있는 기존 수집기를 그대로 재사용한다

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'data', 'state.json')
UNIV = os.path.join(ROOT, 'data', 'universe.json')
KST = timezone(timedelta(hours=9))

MAX_PER_MARKET = int(os.environ.get('REBAL_MAX_PER_MARKET', 10))   # 국가당 주간 교체 상한
DAMAGE_MIN     = int(os.environ.get('REBAL_DAMAGE_MIN', 4))        # 훼손 판정 임계 점수
MIN_MCAP_USD   = float(os.environ.get('REBAL_MIN_MCAP_B', 1.0)) * 1e9
CAND_DEPTH     = int(os.environ.get('REBAL_CAND_DEPTH', 60))       # 시장별로 훑어볼 후보 수
MIN_SCORE_GAIN = float(os.environ.get('REBAL_MIN_SCORE_GAIN', 10)) # 후보가 이 점수 이상 앞서야 교체


# ────────────────────────────── 지표 ──────────────────────────────
def bars(sym, n=64):
    """주봉 종가 리스트. 실패하면 None."""
    res = fp.chart(sym, '2y', '1wk')['chart']['result'][0]
    cl = [c for c in res['indicators']['quote'][0]['close'] if c is not None]
    return cl[-n:] if len(cl) >= 40 else None


def metrics(cl):
    px = cl[-1]
    ma20 = statistics.fmean(cl[-20:])
    ma40 = statistics.fmean(cl[-40:])
    ma40_prev = statistics.fmean(cl[-44:-4]) if len(cl) >= 44 else ma40
    hi52 = max(cl[-52:]) if len(cl) >= 52 else max(cl)
    dd = px / hi52 - 1
    mom12 = px / cl[-13] - 1 if len(cl) >= 13 else 0.0
    mom26 = px / cl[-27] - 1 if len(cl) >= 27 else mom12
    return dict(px=px, ma20=ma20, ma40=ma40, rising=ma40 > ma40_prev,
                dd=dd, mom12=mom12, mom26=mom26)


def clip(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def chart_score(m):
    """0~100. 값이 클수록 차트가 건강하다. 후보 랭킹과 holdings.chart 갱신에 함께 쓴다."""
    if m['px'] > m['ma20'] > m['ma40']:
        s_trend = 25.0
    elif m['px'] > m['ma40']:
        s_trend = 15.0
    else:
        s_trend = 0.0
    s = (s_trend
         + 25.0 * clip((m['mom12'] + 0.10) / 0.60)
         + 20.0 * clip((m['mom26'] + 0.15) / 0.85)
         + 20.0 * clip((m['dd'] + 0.35) / 0.35)
         + (10.0 if m['rising'] else 0.0))
    return round(s, 1)


def damage(m):
    """훼손 점수와 사람이 읽을 사유 목록."""
    pts, why = 0, []
    if m['px'] < m['ma40']:
        pts += 2; why.append('40주선 이탈')
    if m['px'] < m['ma20']:
        pts += 1; why.append('20주선 이탈')
    if m['dd'] <= -0.25:
        pts += 2; why.append(f"52주 고점 대비 {m['dd']*100:.0f}%")
    elif m['dd'] <= -0.15:
        pts += 1; why.append(f"52주 고점 대비 {m['dd']*100:.0f}%")
    if m['mom12'] <= -0.10:
        pts += 2; why.append(f"12주 모멘텀 {m['mom12']*100:+.0f}%")
    elif m['mom12'] <= 0:
        pts += 1; why.append(f"12주 모멘텀 {m['mom12']*100:+.0f}%")
    if not m['rising']:
        pts += 1; why.append('40주선 하락 전환')
    return pts, why


def gate_ok(m, mcap):
    return (m['px'] > m['ma20'] > m['ma40']
            and m['dd'] > -0.15
            and m['mom12'] > 0
            and (mcap or 0) >= MIN_MCAP_USD)


# ────────────────────────────── 심볼 ──────────────────────────────
def yahoo_symbol(mkt, code, U):
    cfg = U['markets'][mkt]
    pad, suf = cfg.get('pad', 0), cfg.get('suffix', '')
    c = str(code).zfill(pad) if pad else str(code)
    return c + suf


def resolve(mkt, code, U):
    """한국은 .KS → 실패하면 .KQ 로 한 번 더 시도한다."""
    cfg = U['markets'][mkt]
    cands = [yahoo_symbol(mkt, code, U)]
    if cfg.get('alt_suffix'):
        cands.append(str(code).zfill(cfg.get('pad', 0)) + cfg['alt_suffix'])
    for s in cands:
        try:
            cl = bars(s)
            if cl:
                return s, cl
        except Exception:
            continue
    return None, None


# ────────────────────────────── 본체 ──────────────────────────────
def main():
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    now = datetime.now(KST)
    if not force and now.weekday() != 0:
        print(f'월요일이 아니므로 건너뜀 ({now:%Y-%m-%d %a})')
        return

    S = json.load(open(STATE, encoding='utf-8'))
    U = json.load(open(UNIV, encoding='utf-8'))
    H, M, SN = S['holdings'], S['meta'], S['snapshots']
    cur = SN[-1]
    fx = cur['fx']
    held = {h['yahoo'] for h in H}
    held_codes = {h['tk'] for h in H}

    # 1) 보유 종목 진단 ------------------------------------------------------
    diag = []
    for i, h in enumerate(H):
        try:
            cl = bars(h['yahoo'])
        except Exception as e:
            print(f"  주봉 실패 {h['tk']}: {e}")
            cl = None
        if not cl:
            continue
        m = metrics(cl)
        pts, why = damage(m)
        diag.append(dict(i=i, h=h, m=m, pts=pts, why=why, score=chart_score(m)))
        time.sleep(0.4)

    if not diag:
        print('진단 데이터를 하나도 받지 못했다. 저장하지 않고 종료.')
        return

    # 차트 점수는 교체 여부와 무관하게 최신값으로 갱신한다
    for d in diag:
        d['h']['chart'] = d['score']
        d['h']['tot'] = round(d['score'] + d['h'].get('prem', 0), 1)

    dmg = [d for d in diag if d['pts'] >= DAMAGE_MIN]
    print(f'진단 {len(diag)}종목 · 훼손 판정 {len(dmg)}종목 (임계 {DAMAGE_MIN}점)')
    for d in sorted(dmg, key=lambda x: -x['pts']):
        print(f"   {d['h']['mkt']} {d['h']['tk']} {d['h']['nm']} — {d['pts']}점 · {', '.join(d['why'])}")

    if not dmg:
        print('교체 대상 없음 — 포트폴리오를 그대로 둔다.')
        if not dry:
            json.dump(S, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('차트 점수만 갱신해서 저장했다.')
        return

    # 2) 시장별로 후보를 훑는다 (훼손 종목이 있는 시장만) ----------------------
    by_mkt = {}
    for d in dmg:
        by_mkt.setdefault(d['h']['mkt'], []).append(d)

    swaps = []
    for mkt, ds in by_mkt.items():
        ds.sort(key=lambda x: (-x['pts'], x['score']))
        need = min(len(ds), MAX_PER_MARKET)
        pool = [c for c in U['markets'][mkt]['tickers'][:CAND_DEPTH]
                if str(c) not in held_codes]
        print(f'[{mkt}] 훼손 {len(ds)}종목 → 최대 {need}종목 교체, 후보 {len(pool)}개 조회')

        fp.session()
        cands = []
        for code in pool:
            if len(cands) >= need * 3:      # 충분히 모이면 조기 종료 — 요청 수를 아낀다
                break
            sym, cl = resolve(mkt, code, U)
            if not cl:
                continue
            m = metrics(cl)
            info = quote_info(sym)
            if not gate_ok(m, info.get('mcap')):
                continue
            cands.append(dict(code=str(code), sym=sym, m=m, cl=cl,
                              score=chart_score(m), info=info))
            time.sleep(0.4)
        cands.sort(key=lambda x: -x['score'])
        print(f'   게이트 통과 후보 {len(cands)}개')

        used = 0
        for d in ds[:need]:
            if used >= len(cands):
                break
            c = cands[used]
            if c['score'] < d['score'] + MIN_SCORE_GAIN:
                print(f"   {d['h']['tk']} 교체 보류 — 후보 점수 우위 부족 ({c['score']} vs {d['score']})")
                continue
            used += 1
            swaps.append((d, c, mkt))

    if not swaps:
        print('훼손은 있었으나 조건을 넘는 후보가 없어 교체하지 않는다.')
        if not dry:
            json.dump(S, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return

    # 3) 자리 바꾸기 ---------------------------------------------------------
    lines = []
    cnt = {}
    for d, c, mkt in swaps:
        i, old = d['i'], d['h']
        ccy = U['markets'][mkt]['ccy']
        try:
            px_new = fp.price(c['sym'])      # 스냅샷 가격과 같은 기준(직전 종가)으로 맞춘다
        except Exception:
            px_new = c['m']['px']
        sell_usd = cur['prices'][i] * old['shares'] / fx[old['ccy']]
        shares_new = sell_usd * fx[ccy] / px_new
        nm = c['info'].get('name') or c['code']
        key = {'미국': 'us', '한국': 'kr', '홍콩': 'hk'}[mkt] + ':' + c['code']

        new = {
            'mkt': mkt, 'tk': c['code'], 'nm': nm, 'ccy': ccy,
            'mc_usd': round((c['info'].get('mcap') or 0) / 1e9, 1),
            'pe': c['info'].get('pe'), 'fpe': c['info'].get('fpe'),
            'chart': c['score'], 'prem': prem_score(c['info']),
            'tot': 0.0,
            'branch': 'T' if c['m']['px'] > c['m']['ma20'] > c['m']['ma40'] else 'R',
            'flag': 0, 'entry': round(px_new, 6), 'shares': shares_new,
            'fx_entry': fx[ccy], 'since': len(SN) - 1,
            'key': key, 'yahoo': c['sym'],
        }
        new['tot'] = round(new['chart'] + new['prem'], 1)
        H[i] = new
        cur['prices'][i] = px_new
        S.setdefault('details', {}).pop(old['key'], None)   # 편출 종목의 상세는 지운다
        S['details'][key] = {
            'bm': '자동 편입 종목 — 사업 개요·재무·이슈는 다음 상세 수집(상세 데이터 수집 워크플로) 때 채워진다.',
            'news': [], 'unit': '', 'f': {}, 'annual': [], 'quarter': [],
            'bs': [], 'bsUnit': '', 'netcash': None, 'seg': [], 'segUnit': '', 'segPeriod': '',
            'hist': hist_block(c['cl'], px_new),
        }
        cnt[mkt] = cnt.get(mkt, 0) + 1
        lines.append(
            f"<b>{old['tk']} {old['nm']}</b> → <b>{new['tk']} {nm}</b> — "
            f"{', '.join(d['why'])} (차트 점수 {d['score']:.0f} → {c['score']:.0f})")

    # 총 평가액은 교체로 변하지 않지만, 부동소수 오차를 없애기 위해 다시 계산해 둔다
    cur['tv'] = round(sum(p * h['shares'] / fx[h['ccy']] for p, h in zip(cur['prices'], H)), 2)
    order = [m for m in ('미국', '한국', '홍콩') if cnt.get(m)]
    cur['rebalance_title'] = (f"자동 리밸런싱 — {len(lines)}종목 교체 ("
                              + ' · '.join(f'{m} {cnt[m]}' for m in order) + ')')
    cur['rebalance'] = [
        f"<b>판정 기준</b> — 주봉 기준 40주선 이탈·52주 고점 대비 낙폭·12주 모멘텀을 점수화해 "
        f"{DAMAGE_MIN}점 이상이면 교체 대상으로 봅니다. 국가당 한 주 최대 {MAX_PER_MARKET}종목까지만 교체하며, "
        f"조건을 넘는 후보가 없으면 교체하지 않습니다."
    ] + lines + [
        "<b>평가액 승계</b> — 매도 종목의 현재 평가액을 그대로 신규 종목에 넣었으므로 "
        "교체 시점의 총 평가액과 누적 수익률은 끊기지 않습니다. 신규 종목의 진입가는 교체일 종가입니다."
    ]
    M['last_rebalance'] = now.strftime('%Y-%m-%d')

    if dry:
        print('\n[DRY RUN] 저장하지 않음')
        print(cur['rebalance_title'])
        for l in lines:
            print(' -', l.replace('<b>', '').replace('</b>', ''))
        return

    json.dump(S, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n' + cur['rebalance_title'])
    for l in lines:
        print(' -', l.replace('<b>', '').replace('</b>', ''))


def quote_info(sym):
    """이름·시총·PER·FW PER. 실패해도 빈 dict 로 넘어간다."""
    try:
        import urllib.parse
        cr = fp.session()
        q = urllib.parse.urlencode({'symbols': sym})
        if cr:
            q += '&crumb=' + urllib.parse.quote(cr)
        j = json.loads(fp._open(f'{fp.HOSTS[0]}/v7/finance/quote?{q}'))
        r = ((j.get('quoteResponse') or {}).get('result') or [{}])[0]
        return {'name': r.get('longName') or r.get('shortName'),
                'mcap': r.get('marketCap'),
                'pe': round(r['trailingPE'], 1) if r.get('trailingPE') else None,
                'fpe': round(r['forwardPE'], 2) if r.get('forwardPE') else None}
    except Exception:
        return {}


def prem_score(info):
    """밸류·성장 가점(0~25)의 자동 근사치. FW PER 이 낮을수록 높다. 값이 없으면 중립 8점."""
    fpe = info.get('fpe')
    if not fpe or fpe <= 0:
        return 8.0
    return round(25.0 * clip((30.0 - fpe) / 25.0), 1)


def hist_block(cl, px):
    """상세 패널 주봉 스파크라인. 후보 진단에서 이미 받아둔 주봉을 그대로 쓴다."""
    try:
        lo, hi = min(cl), max(cl)
        rg = (hi - lo) or 1
        return {'lo': round(lo, 6), 'hi': round(hi, 6),
                'v': [round((x - lo) / rg * 999) for x in cl]}
    except Exception:
        return {'lo': px, 'hi': px, 'v': [500]}


if __name__ == '__main__':
    main()
