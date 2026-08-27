#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""상세 패널용 데이터를 수집해 data/state.json 의 details 에 채운다.

  python3 build/fetch_details.py               # f/bs/annual/quarter/hist 가 빈 종목만
  python3 build/fetch_details.py --all         # 전 종목 강제 갱신
  python3 build/fetch_details.py --only us:GEN,kr:086790

수집 항목
  f       TradingView scanner — 밸류·수익성·기술지표·기간수익률
  annual  stockanalysis 손익계산서 (연간)
  quarter stockanalysis 손익계산서 (분기)
  bs      stockanalysis 재무상태표 + netcash
  hist    Yahoo Finance 주봉 60주 정규화

bm(비즈니스 모델)·seg(사업부문)·news(이슈)는 사람이 정리하는 항목이라 여기서 건드리지 않는다.
컨테이너에서는 시세 사이트가 막혀 있으므로 이 스크립트는 GitHub Actions 러너에서 돌린다.
"""
import json, os, re, sys, time, random, urllib.request, urllib.parse, http.cookiejar

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'data', 'state.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36')

_jar = http.cookiejar.CookieJar()
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def get(url, data=None, ctype=None, timeout=30, tries=3):
    last = None
    for i in range(tries):
        try:
            hdr = {'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9'}
            if ctype:
                hdr['Content-Type'] = ctype
            req = urllib.request.Request(url, data=data, headers=hdr)
            with _op.open(req, timeout=timeout) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1) + random.uniform(0, 1))
    raise RuntimeError(f'{url} 실패: {last}')


# ── TradingView ────────────────────────────────────────────────────────────
TVCOLS = ['price_book_fq', 'price_sales_current', 'enterprise_value_ebitda_ttm',
          'dividends_yield_current', 'dividend_payout_ratio_ttm', 'return_on_equity',
          'return_on_assets', 'debt_to_equity', 'total_revenue', 'net_income',
          'gross_margin', 'operating_margin', 'after_tax_margin', 'free_cash_flow',
          'total_assets', 'total_debt', 'beta_1_year', 'number_of_employees',
          'price_52_week_high', 'price_52_week_low', 'close', 'RSI', 'MACD.macd',
          'MACD.signal', 'SMA20', 'SMA50', 'SMA200', 'Perf.W', 'Perf.1M', 'Perf.3M',
          'Perf.6M', 'Perf.Y', 'Perf.YTD']
FKEYS = ['pbr', 'psr', 'ev_ebitda', 'div_yield', 'payout', 'roe', 'roa', 'de',
         'revenue', 'net_income', 'gross_margin', 'op_margin', 'net_margin', 'fcf',
         'total_assets', 'total_debt', 'beta', 'employees', 'hi52', 'lo52', 'close',
         'rsi', 'macd', 'macd_sig', 'sma20', 'sma50', 'sma200', 'perf_w', 'perf_1m',
         'perf_3m', 'perf_6m', 'perf_y', 'perf_ytd']
TVMKT = {'미국': ('america', 'NASDAQ'), '한국': ('korea', 'KRX'), '홍콩': ('hongkong', 'HKEX')}


def tv_fetch(mkt, tickers):
    market, pre = TVMKT[mkt]
    body = json.dumps({'symbols': {'tickers': [f'{pre}:{t}' for t in tickers]},
                       'columns': TVCOLS}).encode()
    j = json.loads(get(f'https://scanner.tradingview.com/{market}/scan',
                       data=body, ctype='text/plain'))
    out = {}
    for row in j.get('data', []):
        tk = row['s'].split(':')[1]
        out[tk] = {k: v for k, v in zip(FKEYS, row['d'])}
    return out


# ── stockanalysis ──────────────────────────────────────────────────────────
SA_EXC = {'kr:005935': 'krx/005930', 'hk:2359': 'sha/603259', 'hk:2899': 'sha/601899',
          'hk:2099': 'tsx/CGG', 'hk:939': 'hkg/0939', 'hk:914': 'sha/600585'}


def sa_base(h):
    if h['key'] in SA_EXC:
        return 'https://stockanalysis.com/quote/' + SA_EXC[h['key']]
    if h['mkt'] == '미국':
        return 'https://stockanalysis.com/stocks/' + h['tk']
    if h['mkt'] == '한국':
        return 'https://stockanalysis.com/quote/krx/' + h['tk']
    return 'https://stockanalysis.com/quote/hkg/' + str(h['tk']).zfill(4)


TD = re.compile(r'^\s*<td[^>]*>([^<]*)</td>')
CMT = re.compile(r'<!--[\s\S]*?-->')


def row(html, label):
    """라벨 행의 값들을 문자열 리스트로. 차트 범례 등 가짜 매치는 건너뛴다."""
    k = '>' + label + '</div>'
    at = 0
    while True:
        i = html.find(k, at)
        if i < 0:
            return None
        at = i + 1
        j = html.find('</td>', i)
        if j < 0:
            continue
        s = CMT.sub('', html[j + 5:j + 3000])
        out = []
        while True:
            m = TD.match(s)
            if not m:
                break
            out.append(m.group(1).strip())
            s = s[m.end():]
        if len(out) >= 2:
            return out


def heads(html, n=4):
    return [x for x in re.findall(r'<th[^>]*>([^<]{2,20})</th>', html) if x.strip()][:n]


def numify(vals, scale):
    out = []
    for v in vals:
        v = v.replace(',', '').replace('%', '').strip()
        if v in ('', '-', '—', 'n/a', 'Upgrade'):
            out.append(None)
            continue
        try:
            out.append(round(float(v) / scale, 4 if scale == 1 else 2))
        except ValueError:
            out.append(None)
    return out


UNIT_RE = re.compile(r'[Ff]inancials in (millions|thousands|billions) ([A-Z]{3})')


def unit_of(html, mkt):
    m = UNIT_RE.search(html)
    mag, cur = (m.group(1), m.group(2)) if m else ('millions', 'USD')
    if mkt == '한국':
        return '억원', 100.0 if mag == 'millions' else 100000.0
    return {'millions': '백만 ', 'thousands': '천 ', 'billions': '십억 '}[mag] + cur, 1.0


def income(html, mkt, n=4):
    unit, sc = unit_of(html, mkt)
    p = heads(html, n)
    r = {}
    for key, lab in (('REV', 'Revenue'), ('OI', 'Operating Income'),
                     ('NI', 'Net Income'), ('EPS', 'Earnings Per Share')):
        v = row(html, lab)
        if v is None:
            continue
        r[key] = numify(v[:n], 1.0 if key == 'EPS' else sc)
    if not r.get('REV'):
        return None, unit
    return {'p': p, 'r': r}, unit


def balance(html, mkt):
    unit, sc = unit_of(html, mkt)
    def one(lab):
        v = row(html, lab)
        return numify(v[:1], sc)[0] if v else None
    bs = {'assets': one('Total Assets'), 'liab': one('Total Liabilities'),
          'equity': one("Shareholders' Equity") or one('Total Equity'),
          'cash': one('Cash &amp; Equivalents') or one('Cash &amp; Cash Equivalents')
                  or one('Cash and Equivalents'),
          'debt': one('Total Debt')}
    return (bs if bs['assets'] else None), unit


# ── Yahoo 주봉 ──────────────────────────────────────────────────────────────
def weekly(sym, n=60):
    for host in ('https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com'):
        try:
            j = json.loads(get(f'{host}/v8/finance/chart/{urllib.parse.quote(sym)}'
                               f'?range=2y&interval=1wk', tries=2))
            cl = [c for c in j['chart']['result'][0]['indicators']['quote'][0]['close']
                  if c is not None][-n:]
            if len(cl) < 10:
                return None
            lo, hi = min(cl), max(cl)
            rg = (hi - lo) or 1
            return {'lo': round(lo, 6), 'hi': round(hi, 6),
                    'v': [round((c - lo) / rg * 999) for c in cl]}
        except Exception:
            time.sleep(2)
    return None


def main():
    S = json.load(open(STATE, encoding='utf-8'))
    H = S['holdings']
    DET = S.setdefault('details', {})
    only = None
    for a in sys.argv[1:]:
        if a.startswith('--only'):
            only = set(a.split('=', 1)[1].split(',')) if '=' in a else None
    force = '--all' in sys.argv

    todo = [h for h in H if (only and h['key'] in only) or
            (not only and (force or not (DET.get(h['key'], {}).get('f')
                                         and DET.get(h['key'], {}).get('annual'))))]
    print(f'대상 {len(todo)}종목')
    if not todo:
        return

    # 1) TradingView 일괄
    tv = {}
    for mkt in ('미국', '한국', '홍콩'):
        tks = [h['tk'] for h in todo if h['mkt'] == mkt]
        if tks:
            try:
                tv.update({(mkt, k): v for k, v in tv_fetch(mkt, tks).items()})
                print(f'  TV {mkt} {len(tks)}종목')
            except Exception as e:
                print(f'  TV {mkt} 실패: {e}')

    ok = 0
    for h in todo:
        d = DET.setdefault(h['key'], {})
        f = tv.get((h['mkt'], h['tk']))
        if f:
            d['f'] = {k: v for k, v in f.items() if v is not None}
        base = sa_base(h)
        try:
            a = get(base + '/financials/')
            ann, unit = income(a, h['mkt'])
            if ann:
                d['annual'] = ann
                d['unit'] = unit
        except Exception as e:
            print(f"  연간 실패 {h['tk']}: {e}")
        try:
            q = get(base + '/financials/?p=quarterly')
            qtr, _ = income(q, h['mkt'])
            if qtr:
                d['quarter'] = qtr
        except Exception as e:
            print(f"  분기 실패 {h['tk']}: {e}")
        try:
            b = get(base + '/financials/balance-sheet/')
            bs, bunit = balance(b, h['mkt'])
            if bs:
                d['bs'] = bs
                d['bsUnit'] = bunit
                if bs['cash'] is not None and bs['debt'] is not None:
                    d['netcash'] = round(bs['cash'] - bs['debt'], 2)
        except Exception as e:
            print(f"  재무상태 실패 {h['tk']}: {e}")
        w = weekly(h['yahoo'])
        if w:
            d['hist'] = w
        d.setdefault('bm', '')
        d.setdefault('seg', [])
        d.setdefault('news', [])
        got = [k for k in ('f', 'annual', 'quarter', 'bs', 'hist') if d.get(k)]
        print(f"  {h['tk']:8s} {','.join(got)}")
        if len(got) >= 4:
            ok += 1
        time.sleep(1.2)

    json.dump(S, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'완료 {ok}/{len(todo)}')


if __name__ == '__main__':
    main()
