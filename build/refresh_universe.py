#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/universe.json 을 stockanalysis.com 거래소별 시총 순위로 다시 만든다.

    python3 build/refresh_universe.py

분기에 한 번 정도 손으로 돌리면 된다. 자동 갱신 워크플로에는 넣지 않았다 —
유니버스가 매주 바뀌면 교체 사유를 추적하기 어렵고, 스크래핑 실패가 리밸런싱을 막기 때문이다.
사이트 구조가 바뀌어 파싱이 실패하면 기존 파일을 그대로 두고 종료한다.
"""
import json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'universe.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36')

SRC = {
    '미국': ('nasdaq-stocks',            300, {'ccy': 'USD', 'suffix': '',    'pad': 0}),
    '한국': ('korea-stock-exchange',     100, {'ccy': 'KRW', 'suffix': '.KS', 'pad': 6,
                                              'alt_suffix': '.KQ'}),
    '홍콩': ('hong-kong-stock-exchange', 300, {'ccy': 'HKD', 'suffix': '.HK', 'pad': 4}),
}


def fetch(slug):
    url = f'https://stockanalysis.com/list/{slug}/__data.json'
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def rows(payload):
    """SvelteKit 평탄화 페이로드에서 (심볼, 시총)을 시총 내림차순 그대로 뽑는다."""
    D = payload['nodes'][-1]['data']
    dr = lambda x: D[x] if isinstance(x, int) else x
    out = []
    for v in D:
        if isinstance(v, dict) and 'marketCap' in v and 's' in v:
            s, mc = dr(v['s']), dr(v['marketCap'])
            if isinstance(s, str) and isinstance(mc, (int, float)) and mc > 0:
                out.append(s)
    return out


def code(mkt, s):
    if mkt == '미국':
        return s
    c = s.split('/')[-1]
    return str(int(c)) if mkt == '홍콩' else c


def main():
    markets = {}
    for mkt, (slug, n, cfg) in SRC.items():
        try:
            raw = rows(fetch(slug))
        except Exception as e:
            print(f'{mkt} 수집 실패: {e} — 기존 파일을 유지하고 종료한다')
            return 1
        seen, tick = set(), []
        for s in raw:
            c = code(mkt, s)
            if mkt == '홍콩' and 4000 <= int(c) <= 4999:   # HK 4000번대는 채권·HDR
                continue
            if mkt == '한국' and not re.fullmatch(r'\d{6}', c):
                continue
            if c in seen:
                continue
            seen.add(c); tick.append(c)
            if len(tick) >= n:
                break
        if len(tick) < n * 0.5:
            print(f'{mkt} 파싱 결과가 너무 적다({len(tick)}) — 중단')
            return 1
        markets[mkt] = dict(cfg, tickers=tick)
        print(f'{mkt} {len(tick)}종목')

    old = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    from datetime import datetime, timezone, timedelta
    json.dump({
        'note': old.get('note', '리밸런싱 후보 유니버스. 시총 상위 순으로 정렬돼 있다.'),
        'updated': datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d'),
        'source': 'stockanalysis.com 거래소별 시총 순위 (NASDAQ / KRX / HKEX)',
        'markets': markets,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('universe.json 갱신 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main())
