# -*- coding: utf-8 -*-
import json
import os,sys
from datetime import datetime,timezone,timedelta
BUILT=datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S=json.load(open(os.path.join(R,'data','state.json'),encoding='utf-8'))
M,H,SN=S['meta'],S['holdings'],S['snapshots']
DET=S.get('details',{});BASE=M['base_capital'];NH=len(H)
B=os.path.join(R,'build')
CSS=open(os.path.join(B,'css.txt'),encoding='utf-8').read();JS=open(os.path.join(B,'app.js'),encoding='utf-8').read()

def val_at(s):
    # 스냅샷 시점의 실제 평가액(tv)이 있으면 그것을 쓴다. 종목 수·수량이 바뀌어도 과거 이력이 왜곡되지 않는다.
    if s.get('tv'): return s['tv']
    return sum((s['prices'][i] or 0)*h['shares']/s['fx'][h['ccy']] for i,h in enumerate(H))
def bm_at(s):
    b0=M['bench_base'];v=sum(s['bench'][k]/b0[k]-1 for k in b0)/3
    return 0.0 if abs(v)<5e-9 else v
series=[{"date":s['date'],"v":val_at(s),"b":BASE*(1+bm_at(s))} for s in SN]
cur=SN[-1];prv=SN[-2] if len(SN)>1 else None
tot=series[-1]['v'];cum=tot/BASE-1
cum=0.0 if abs(cum)<5e-9 else cum
bmc=bm_at(cur);dchg=(series[-1]['v']/series[-2]['v']-1) if prv else None

rows=[]
for i,h in enumerate(H):
    px=cur['prices'][i];fx=cur['fx'][h['ccy']]
    cost=h['entry']*h['shares']/M['fx_base'][h['ccy']];v=px*h['shares']/fx
    rows.append(dict(h,cur=px,loc=px/h['entry']-1,usd=v/cost-1,val=v,cost=cost,
                     d=(px/prv['prices'][i]-1) if (prv and i<len(prv['prices']) and prv['prices'][i]) else None,
                     hist=[s['prices'][i] for s in SN if i<len(s['prices']) and s['prices'][i] is not None]))

def money(v,c): return "{:,.0f}".format(v) if c=='KRW' else "{:,.2f}".format(v)
def pct(v,dp=2):
    if v is None: return '<span class="flat">—</span>'
    if abs(v)<5e-5: v=0.0
    c="up" if v>0 else ("down" if v<0 else "flat")
    return '<span class="%s">%+.*f%%</span>'%(c,dp,v*100)
def num(v,dp=1): return "—" if v is None else "{:,.{}f}".format(v,dp)

BN={"미국":"SPY","한국":"KOSPI","홍콩":"HSI"};b0=M['bench_base']
mrows=""
for m in ["미국","한국","홍콩"]:
    s=[r for r in rows if r['mkt']==m];v=sum(x['val'] for x in s);c=sum(x['cost'] for x in s)
    bb=cur['bench'][BN[m]]/b0[BN[m]]-1
    mrows+=f'<tr><td class="mk">{m}</td><td class="n">${v:,.0f}</td><td class="n">{pct(v/c-1)}</td><td>{BN[m]}</td><td class="n">{pct(bb)}</td><td class="n">{pct(v/c-1-bb)}</td></tr>'

hrows="";prev=None
for i,r in enumerate(rows,1):
    first=r['mkt']!=prev;prev=r['mkt']
    tag='<span class="pill trend">추세</span>' if r['branch']=='T' else '<span class="pill rev">반전</span>'
    sep=' class="grp"' if first and i>1 else ''
    fl='<sup class="fl">&#9873;</sup>' if r['flag'] else ''
    hrows+=(f'<tr{sep} data-key="{r["key"]}" role="button" aria-label="{r["nm"]} 상세 보기">'
      f'<td class="mk">{r["mkt"]}</td><td class="tk">{r["tk"]}</td>'
      f'<td class="nm">{r["nm"]} {tag}</td><td class="n">${r["mc_usd"]:,.1f}B</td>'
      f'<td class="n dim">{num(r["pe"])}</td><td class="n">{num(r["fpe"])}{fl}</td>'
      f'<td class="n">{money(r["entry"],r["ccy"])}</td><td class="n">{money(r["cur"],r["ccy"])}</td>'
      f'<td class="n">{pct(r["d"])}</td><td class="n">{pct(r["loc"])}</td><td class="n">{pct(r["usd"])}</td>'
      f'<td class="spk" data-spk="{",".join("%g"%x for x in r["hist"])}"></td>'
      f'<td class="n sc"><i style="width:{min(100,r["chart"])}%"></i><b>{r["chart"]:.0f}</b></td>'
      f'<td class="n gold">+{r["prem"]:.1f}</td><td class="n tot">{r["tot"]:.1f}</td></tr>')

RB=cur.get('rebalance') or []
rb=('<section><h2>5. '+cur.get('rebalance_title','이번 리밸런싱')+'</h2><div class="note"><ul>'
    +''.join(f'<li>{x}</li>' for x in RB)+'</ul></div></section>') if RB else ''

DATA=json.dumps({"series":series,"base":BASE,"detailUpdated":M.get('detail_updated',cur['date']),
  "holdings":[{k:r[k] for k in ('key','mkt','tk','nm','ccy','entry','cur','loc','usd','pe','fpe','flag','mc_usd','chart','prem','tot','branch')} for r in rows],
  "details":DET},ensure_ascii=False,separators=(',',':'))

nsnap=len(SN)
dcard=pct(dchg) if dchg is not None else '<span class="flat">—</span>'
dsub=f"{prv['date']} → {cur['date']}" if prv else "다음 갱신부터 표시"
nnews=sum(len(v.get('news',[])) for v in DET.values())

HTML=f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>글로벌 스크리닝 {NH}</title>
<meta name="description" content="글로벌 기술적 스크리닝 모의 포트폴리오 — 나스닥·한국·홍콩 {NH}종목 트래킹">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ctext y='26' font-size='26'%3E📈%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>{CSS}</style>
</head><body>
<div class="wrap">
 <header class="head">
  <div class="eyebrow">Tracking Report · Model V3 · Snapshot {nsnap}</div>
  <h1>글로벌 기술적 스크리닝 모의 포트폴리오</h1>
  <div class="meta">기준 <b>{cur['date']} KST</b> (전 시장 직전 종가) · V3 개시 {M['inception']} · 초기자본 <b>$100,000</b> · {NH}종목 동일가중 (포지션당 ${BASE/NH:,.2f})</div>
  <div class="meta">마지막 갱신 <b>{BUILT}</b> · 자동 갱신 평일 07:30 / 17:30 KST (GitHub Actions, 최대 1시간 지연 가능)</div>
  <div class="meta">유니버스 — 나스닥 시총 Top 300 · 한국 시총 Top 100 · 홍콩 시총 Top 300</div>
  <div class="notice">{cur.get('label','')} · <b>종목 행을 클릭하면</b> 재무제표·밸류·배당·기술지표·최근 이슈가 담긴 상세 패널이 열립니다.</div>
 </header>
 <section class="kpis">
  <div class="kpi"><div class="k">총 평가액</div><div class="v">${tot:,.0f}</div><div class="s">초기자본 $100,000</div></div>
  <div class="kpi"><div class="k">누적 수익률</div><div class="v">{pct(cum)}</div><div class="s">V3 개시 대비 (USD, 환효과 포함)</div></div>
  <div class="kpi"><div class="k">직전 갱신 대비</div><div class="v">{dcard}</div><div class="s">{dsub}</div></div>
  <div class="kpi"><div class="k">합성 벤치마크 대비</div><div class="v">{pct(cum-bmc)}</div><div class="s">BM {bmc*100:+.2f}% (SPY·KOSPI·HSI 균등)</div></div>
  <div class="kpi"><div class="k">배수 검증</div><div class="v">{NH-sum(h['flag'] for h in H)} / {NH}</div><div class="s">2개 소스 일치 · {sum(h['flag'] for h in H)}종목 편차 표시</div></div>
  <div class="kpi"><div class="k">수집된 이슈</div><div class="v">{nnews}</div><div class="s">{NH}종목 뉴스·실적·리포트</div></div>
 </section>
 <section><h2>1. 누적 추이</h2>
  <div class="chartbox"><div class="legend"><span><i style="background:var(--s1)"></i>포트폴리오</span><span><i style="background:var(--s2)"></i>합성 벤치마크</span></div><div id="chart"></div></div>
 </section>
 <section><h2>2. 시장별 성과</h2>
  <div class="scroll"><table><thead><tr><th>시장</th><th class="n">평가액(USD)</th><th class="n">누적</th><th>벤치마크</th><th class="n">BM 수익률</th><th class="n">초과</th></tr></thead><tbody>{mrows}</tbody></table></div>
 </section>
 <section><h2>3. 보유 종목 30 (행 클릭 → 상세)</h2>
  <div class="scroll"><table><thead><tr><th>시장</th><th>티커</th><th>종목명</th><th class="n">시가총액</th><th class="n">PER</th><th class="n">FW PER</th><th class="n">진입가</th><th class="n">현재가</th><th class="n">직전 대비</th><th class="n">현지 누적</th><th class="n">USD 누적</th><th>추이</th><th class="n">차트</th><th class="n">밸류·성장</th><th class="n">총점</th></tr></thead><tbody>{hrows}</tbody></table></div>
  <div class="cap">시가총액은 USD 환산 · 진입가/현재가는 현지통화 · 배수는 TradingView와 stockanalysis.com 2개 소스 교차검증 후 보수적(높은) 값 채택 · <span class="fl">&#9873;</span>는 편차 25% 이상 · 환율 USDKRW {cur['fx']['KRW']:,.2f} / USDHKD {cur['fx']['HKD']:,.4f}</div>
 </section>
 <section><h2>4. 운영 규칙</h2><div class="note"><ul>
  <li><b>월요일</b> — 전체 점검 및 리밸런싱. 차트가 훼손된 종목을 <b>최대 9종목</b>까지 교체하고 하단에 사유를 기재합니다.</li>
  <li><b>주중·주말 수시</b> — "수익률 체크" 한마디로 최신 종가를 반영해 같은 링크에 갱신합니다.</li>
  <li><b>재무·이슈</b> — 재무제표와 뉴스는 월요일 주 1회 갱신합니다. 시세는 매 갱신마다 최신입니다.</li>
  <li><b>스냅샷 누적</b> — 갱신할 때마다 추이 차트와 스파크라인이 길어집니다. 현재 {nsnap}개.</li>
 </ul></div></section>
 {rb}
 <footer><span>모의 포트폴리오 · 실제 매매 아님</span><span>데이터: TradingView · stockanalysis.com · 웹 검색</span><span>기준통화 USD</span><span>Model V3 · 빌드 {BUILT}</span></footer>
</div>
<div id="scrim"></div>
<aside id="dw" role="dialog" aria-modal="true" aria-labelledby="dwName" hidden>
 <div class="dwh">
  <button class="close" aria-label="닫기">&#10005;</button>
  <div class="r1"><h3 id="dwName">—</h3><span class="sub" id="dwSub"></span></div>
  <div class="px" id="dwPx"></div>
  <div class="tabs" role="tablist">
   <button role="tab" data-tab="개요" aria-selected="true">개요</button>
   <button role="tab" data-tab="재무" aria-selected="false">재무</button>
   <button role="tab" data-tab="이슈" aria-selected="false">이슈</button>
  </div>
 </div>
 <div class="dwb" id="dwBody"></div>
</aside>
<div id="tip"></div>
<script id="pf-data" type="application/json">{DATA}</script>
<script>{JS}</script>
</body></html>
"""
open(os.path.join(R,'index.html'),'w',encoding='utf-8').write(HTML)
print("ok",len(HTML),"snapshots",nsnap,"news",nnews)
