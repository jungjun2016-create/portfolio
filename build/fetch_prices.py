#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Yahoo Finance에서 보유 30종목 종가·환율·벤치마크를 받아 data/state.json에 스냅샷을 추가한다.

  python3 build/fetch_prices.py            # 시세 스냅샷만
  python3 build/fetch_prices.py --weekly   # 주봉 60주 차트 데이터도 갱신

같은 날짜 스냅샷이 있으면 마지막 행을 덮어쓴다. 기존 이력은 절대 삭제하지 않는다.

GitHub Actions 러너(데이터센터 IP)는 Yahoo가 429로 막는 경우가 많다. 그래서
 1) 쿠키+crumb 세션을 먼저 만들고
 2) v7/quote 로 전 종목을 1~2회에 몰아서 받고
 3) 실패분만 v8/chart 로 개별 재시도(query1↔query2 번갈아, 지수 백오프)
 4) 그래도 안 되면 stooq CSV로 마지막 폴백
하는 4단 구조로 간다.
"""
import json, os, sys, time, random, urllib.request, urllib.error, urllib.parse, http.cookiejar
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'data', 'state.json')
KST = timezone(timedelta(hours=9))
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36')
HOSTS = ['https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com']

_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))
_crumb = None


def _open(url, timeout=25):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'application/json,text/plain,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    with _opener.open(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def session():
    """쿠키 + crumb 확보. 실패해도 치명적이지 않으니 조용히 넘어간다."""
    global _crumb
    if _crumb:
        return _crumb
    for seed in ('https://fc.yahoo.com/', 'https://finance.yahoo.com/quote/AAPL/'):
        try:
            _open(seed, timeout=15)
        except Exception:
            pass
    for h in HOSTS:
        try:
            c = _open(h + '/v1/test/getcrumb', timeout=15).strip()
            if c and len(c) < 40 and '{' not in c:
                _crumb = c
                print(f'crumb 확보 ({len(_jar)} cookies)')
                return _crumb
        except Exception as e:
            print(f'  crumb 실패 {h}: {e}')
    print('crumb 없음 — chart 엔드포인트로만 진행')
    return None


def _sleep(i):
    time.sleep(min(60, 3 * (2 ** i)) + random.uniform(0, 2))


def quote_batch(syms):
    """v7/quote 로 여러 종목을 한 번에. {sym: price} 반환(못 받은 건 빠짐)."""
    out = {}
    cr = session()
    for i in range(0, len(syms), 20):
        chunk = syms[i:i + 20]
        q = urllib.parse.urlencode({'symbols': ','.join(chunk)})
        if cr:
            q += '&crumb=' + urllib.parse.quote(cr)
        for a in range(4):
            host = HOSTS[a % 2]
            try:
                j = json.loads(_open(f'{host}/v7/finance/quote?{q}'))
                for r in (j.get('quoteResponse') or {}).get('result') or []:
                    p = r.get('regularMarketPrice') or r.get('previousClose')
                    if p and p > 0:
                        out[r['symbol']] = float(p)
                break
            except Exception as e:
                print(f'  quote 재시도 {a+1}: {e}')
                _sleep(a)
        time.sleep(1.0)
    print(f'일괄 시세 {len(out)}/{len(syms)}')
    return out


def chart(sym, rng='5d', iv='1d', tries=6):
    last = None
    for i in range(tries):
        host = HOSTS[i % 2]
        try:
            return json.loads(_open(f'{host}/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval={iv}'))
        except Exception as e:
            last = e
            if i == 0:
                session()
            _sleep(i)
    raise RuntimeError(f'{sym} 조회 실패: {last}')


def stooq(sym):
    """마지막 폴백. 미국 티커만 대응(005930.KS 같은 건 미지원)."""
    if '.' in sym or '^' in sym or '=' in sym:
        return None
    try:
        url = f'https://stooq.com/q/l/?s={sym.lower()}.us&f=sd2t2ohlcv&h&e=csv'
        rows = _open(url, timeout=20).strip().splitlines()
        if len(rows) < 2:
            return None
        cols = rows[0].split(',')
        vals = rows[1].split(',')
        c = float(vals[cols.index('Close')])
        return c if c > 0 else None
    except Exception:
        return None


def price(sym, cache=None):
    if cache and sym in cache:
        return cache[sym]
    try:
        res = chart(sym)['chart']['result'][0]
        p = res['meta'].get('regularMarketPrice')
        if p is None:
            cl = [c for c in res['indicators']['quote'][0]['close'] if c is not None]
            p = cl[-1] if cl else None
        if p and p > 0:
            return float(p)
    except Exception as e:
        print(f'  chart 폴백 실패 {sym}: {e}')
    p = stooq(sym)
    if p:
        print(f'  stooq 폴백 사용 {sym}')
        return p
    raise RuntimeError(f'{sym} 가격 없음')


def weekly(sym, n=60):
    res = chart(sym, '2y', '1wk')['chart']['result'][0]
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

    hold_syms = [h['yahoo'] for h in H]
    fx_syms = list(M['yahoo_fx'].values())
    bench_syms = list(M['yahoo_bench'].values())
    cache = quote_batch(hold_syms + fx_syms + bench_syms)

    prices = []
    for h in H:
        prices.append(price(h['yahoo'], cache))
    fx = {'USD': 1.0}
    for k, sym in M['yahoo_fx'].items():
        fx[k] = price(sym, cache)
    bench = {k: price(sym, cache) for k, sym in M['yahoo_bench'].items()}

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
            time.sleep(0.6)
        print(f'주봉 갱신 {ok}/{len(H)}')

    json.dump(S, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    base = M['base_capital']
    tot = sum(p * h['shares'] / fx[h['ccy']] for p, h in zip(prices, H))
    print(f"스냅샷 {act}: {today} (총 {len(S['snapshots'])}개)  평가액 ${tot:,.2f}  누적 {tot/base-1:+.2%}")


if __name__ == '__main__':
    main()
