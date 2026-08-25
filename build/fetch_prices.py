#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Yahoo Finance에서 보유 30종목 종가·환율·벤치마크를 받아 data/state.json에 스냅샷을 추가한다.

  python3 build/fetch_prices.py            # 시세 스냅샷만
  python3 build/fetch_prices.py --weekly   # 주봉 60주 차트 데이터도 갱신
같은 날짜 스냅샷이 있으면 마지막 행을 덮어쓴다. 기존 이력은 절대 삭제하지 않는다.
"""
import json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'data', 'state.json')
KST = timezone(timedelta(hours=9))
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'
BASE = 'https://query1.finance.yahoo.com/v8/finance/chart/'


def get(sym, rng='5d', iv='1d', tries=4):
    url = f'{BASE}{sym}?range={rng}&interval={iv}'
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:            # 429/5xx/타임아웃 모두 재시도
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f'{sym} 조회 실패: {last}')


def price(sym):
    j = get(sym)
    res = j['chart']['result'][0]
    p = res['meta'].get('regularMarketPrice')
    if p is None:                          # 장 마감 직후 등 meta가 비면 마지막 종가 사용
        cl = [c for c in res['indicators']['quote'][0]['close'] if c is not None]
        p = cl[-1] if cl else None
    if p is None or p <= 0:
        raise RuntimeError(f'{sym} 가격 없음')
    return float(p)


def weekly(sym, n=60):
    res = get(sym, '2y', '1wk')['chart']['result'][0]
    cl = [c for c in res['indicators']['quote'][0]['close'] if c is not None][-n:]
    if len(cl) < 10:
        return None
    lo, hi = min(cl), max(cl)
    rg = (hi - lo) or 1
    return {'lo': round(lo, 6), 'hi': round(hi, 6), 'v': [round((c - lo) / rg * 999) for c in cl]}


def main():
    do_weekly = '--weekly' in sys.argv
    S = json.load(open(STATE, encoding='utf-8'))
    H, M = S['holdings'], S['meta']

    prices = []
    for h in H:
        prices.append(price(h['yahoo']))
        time.sleep(0.25)
    fx = {'USD': 1.0}
    for k, sym in M['yahoo_fx'].items():
        fx[k] = price(sym)
    bench = {k: price(sym) for k, sym in M['yahoo_bench'].items()}

    # 검증 — 하나라도 이상하면 저장하지 않는다
    assert len(prices) == len(H) and all(p and p > 0 for p in prices), '가격 누락'
    assert all(v > 0 for v in fx.values()) and all(v > 0 for v in bench.values()), '환율/벤치마크 누락'
    prev = S['snapshots'][-1]['prices']
    for h, p, q in zip(H, prices, prev):                    # 50% 이상 급변은 데이터 오류로 간주
        if q and abs(p / q - 1) > 0.5:
            raise SystemExit(f"이상치 감지 {h['tk']}: {q} → {p}. 저장 중단.")

    today = datetime.now(KST).strftime('%Y-%m-%d')
    snap = {'date': today, 'label': '자동 갱신 (GitHub Actions)', 'fx': fx, 'bench': bench, 'prices': prices}
    if S['snapshots'][-1]['date'] == today:
        keep = {k: S['snapshots'][-1][k] for k in ('rebalance', 'rebalance_title') if k in S['snapshots'][-1]}
        S['snapshots'][-1] = {**snap, **keep}
        act = '갱신'
    else:
        S['snapshots'].append(snap)
        act = '추가'

    if do_weekly:
        ok = 0
        for h in H:
            try:
                w = weekly(h['yahoo'])
                if w:
                    S['details'][h['key']]['hist'] = w
                    ok += 1
            except Exception as e:
                print(f"  주봉 실패 {h['tk']}: {e}")
            time.sleep(0.25)
        print(f'주봉 갱신 {ok}/{len(H)}')

    json.dump(S, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    base = M['base_capital']
    tot = sum(p * h['shares'] / fx[h['ccy']] for p, h in zip(prices, H))
    print(f"스냅샷 {act}: {today} (총 {len(S['snapshots'])}개)  평가액 ${tot:,.2f}  누적 {tot/base-1:+.2%}")


if __name__ == '__main__':
    main()
