const D=JSON.parse(document.getElementById('pf-data').textContent);
const box=document.getElementById('chart'),tip=document.getElementById('tip');
const CS=getComputedStyle(document.documentElement);
const S1=CS.getPropertyValue('--s1').trim(),S2=CS.getPropertyValue('--s2').trim();
const nf=(v,d)=>v==null||!isFinite(v)?'—':v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const pc=(v,d)=>{if(v==null||!isFinite(v))return '<span class="flat">—</span>';
 const c=v>0.0001?'up':v<-0.0001?'down':'flat';return '<span class="'+c+'">'+(v>=0?'+':'')+v.toFixed(d==null?2:d)+'%</span>';};
const ad=v=>v==null||!isFinite(v)?'—':(Math.abs(v)>=1000?nf(v,0):Math.abs(v)>=10?nf(v,1):nf(v,3));
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function draw(){
 if(D.series.length<2){box.innerHTML='<div class="empty">스냅샷이 1개입니다 — 다음 갱신부터 추이가 표시됩니다.</div>';return;}
 const W=box.clientWidth||900,H=260,P={t:14,r:16,b:26,l:52};
 const pv=D.series.map(s=>s.v/D.base-1),bv=D.series.map(s=>s.b/D.base-1);
 const all=pv.concat(bv);let lo=Math.min(...all),hi=Math.max(...all);
 const pad=(hi-lo||0.02)*0.18;lo-=pad;hi+=pad;
 const X=i=>P.l+i*(W-P.l-P.r)/(D.series.length-1),Y=v=>P.t+(hi-v)/(hi-lo)*(H-P.t-P.b);
 const path=a=>a.map((v,i)=>(i?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1)).join(' ');
 let g='';
 for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4,y=Y(v);
  g+='<line x1="'+P.l+'" y1="'+y.toFixed(1)+'" x2="'+(W-P.r)+'" y2="'+y.toFixed(1)+'" stroke="#1B2942" stroke-width="1"/>'
   +'<text x="'+(P.l-9)+'" y="'+(y+4).toFixed(1)+'" fill="#63758F" font-size="10" text-anchor="end" font-family="IBM Plex Mono,monospace">'+(v*100).toFixed(1)+'%</text>';}
 D.series.forEach((s,i)=>{if(i===0||i===D.series.length-1||D.series.length<8)
  g+='<text x="'+X(i).toFixed(1)+'" y="'+(H-8)+'" fill="#63758F" font-size="10" text-anchor="'+(i===0?'start':i===D.series.length-1?'end':'middle')+'" font-family="IBM Plex Mono,monospace">'+s.date.slice(5)+'</text>';});
 g+='<path d="'+path(bv)+'" fill="none" stroke="'+S2+'" stroke-width="2" stroke-linejoin="round"/>';
 g+='<path d="'+path(pv)+'" fill="none" stroke="'+S1+'" stroke-width="2" stroke-linejoin="round"/>';
 g+='<circle cx="'+X(pv.length-1).toFixed(1)+'" cy="'+Y(pv[pv.length-1]).toFixed(1)+'" r="4" fill="'+S1+'" stroke="#121D31" stroke-width="2"/>';
 g+='<line id="cx" y1="'+P.t+'" y2="'+(H-P.b)+'" stroke="#3A4C6B" stroke-width="1" opacity="0"/>';
 box.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" width="100%" height="'+H+'" role="img" aria-label="포트폴리오와 벤치마크 누적 수익률 추이">'+g+'</svg>';
 const svg=box.querySelector('svg'),cx=svg.querySelector('#cx');
 svg.addEventListener('mousemove',e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)*W/r.width;
  let i=Math.round((x-P.l)/((W-P.l-P.r)/(D.series.length-1)));i=Math.max(0,Math.min(D.series.length-1,i));
  cx.setAttribute('x1',X(i));cx.setAttribute('x2',X(i));cx.setAttribute('opacity','1');
  tip.innerHTML=D.series[i].date+'<br><span style="color:'+S1+'">■</span> '+(pv[i]*100).toFixed(2)+'%<br><span style="color:'+S2+'">■</span> '+(bv[i]*100).toFixed(2)+'%';
  tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY-10)+'px';tip.style.opacity='1';});
 svg.addEventListener('mouseleave',()=>{tip.style.opacity='0';cx.setAttribute('opacity','0');});
}
document.querySelectorAll('td.spk').forEach(td=>{
 const a=td.dataset.spk.split(',').map(Number);
 if(a.length<2){td.innerHTML='<span style="color:#3A4C6B;font-size:11px">—</span>';return;}
 const w=64,h=18,lo=Math.min(...a),hi=Math.max(...a),r=(hi-lo)||1;
 const p=a.map((v,i)=>(i?'L':'M')+(i*w/(a.length-1)).toFixed(1)+' '+(h-((v-lo)/r)*(h-3)-1.5).toFixed(1)).join(' ');
 td.innerHTML='<svg width="'+w+'" height="'+h+'"><path d="'+p+'" fill="none" stroke="'+(a[a.length-1]>=a[0]?'#FF5B6B':'#4E9CFF')+'" stroke-width="1.5" stroke-linejoin="round"/></svg>';});

/* ---- 종목 상세 ---- */
const dw=document.getElementById('dw'),scrim=document.getElementById('scrim');
let curKey=null,curTab='개요',finMode='annual',lastFocus=null;

function bars(vals,color){
 const v=vals.filter(x=>x!=null&&isFinite(x));if(v.length<2)return '';
 const mx=Math.max(...v.map(Math.abs))||1,w=100/vals.length;
 return '<svg width="100%" height="34" viewBox="0 0 100 34" preserveAspectRatio="none">'+
  vals.map((x,i)=>{if(x==null||!isFinite(x))return '';const h=Math.abs(x)/mx*30;
   return '<rect x="'+(i*w+w*0.18).toFixed(2)+'" y="'+(32-h).toFixed(2)+'" width="'+(w*0.64).toFixed(2)+'" height="'+h.toFixed(2)+'" fill="'+(x<0?'#4E9CFF':color)+'" rx="0.6"/>';}).join('')+'</svg>';
}

function priceChart(h,ccy){
 if(!h||!h.v||h.v.length<5)return '<div class="hint">주가 이력이 없습니다.</div>';
 const P=h.v.map(x=>h.lo+x/999*(h.hi-h.lo));
 const W=640,H=170,M={t:10,r:46,b:16,l:8};
 const sma=(n)=>P.map((_,i)=>i<n-1?null:P.slice(i-n+1,i+1).reduce((a,b)=>a+b,0)/n);
 const s13=sma(13);
 const lo=Math.min(...P),hi=Math.max(...P),rg=(hi-lo)||1;
 const X=i=>M.l+i*(W-M.l-M.r)/(P.length-1),Y=v=>M.t+(hi-v)/rg*(H-M.t-M.b);
 const d=a=>a.map((v,i)=>v==null?'':((i&&a[i-1]!=null?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1))).join(' ');
 const area=d(P)+' L'+X(P.length-1).toFixed(1)+' '+(H-M.b)+' L'+X(0).toFixed(1)+' '+(H-M.b)+' Z';
 const last=P[P.length-1],up=last>=P[0];
 const col=up?'#FF5B6B':'#4E9CFF';
 const dec=ccy==='KRW'?0:2;
 let g='<defs><linearGradient id="ga" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="'+col+'" stop-opacity="0.20"/><stop offset="1" stop-color="'+col+'" stop-opacity="0"/></linearGradient></defs>';
 [hi,(hi+lo)/2,lo].forEach(v=>{const y=Y(v);
  g+='<line x1="'+M.l+'" y1="'+y.toFixed(1)+'" x2="'+(W-M.r)+'" y2="'+y.toFixed(1)+'" stroke="#1B2942" stroke-width="1"/>'
   +'<text x="'+(W-M.r+6)+'" y="'+(y+3.5).toFixed(1)+'" fill="#63758F" font-size="9.5" font-family="IBM Plex Mono,monospace">'+nf(v,dec)+'</text>';});
 g+='<path d="'+area+'" fill="url(#ga)"/>';
 g+='<path d="'+d(s13)+'" fill="none" stroke="#8A6A2A" stroke-width="1.4" stroke-dasharray="3 3"/>';
 g+='<path d="'+d(P)+'" fill="none" stroke="'+col+'" stroke-width="1.8" stroke-linejoin="round"/>';
 g+='<circle cx="'+X(P.length-1).toFixed(1)+'" cy="'+Y(last).toFixed(1)+'" r="3.2" fill="'+col+'"/>';
 return '<div class="rng"><svg viewBox="0 0 '+W+' '+H+'" width="100%" height="180" preserveAspectRatio="none" role="img" aria-label="최근 60주 주가 추이">'+g+'</svg>'
  +'<div class="rngl" style="margin-top:6px"><span>60주 전</span><span style="color:#8A6A2A">— — 13주 이동평균</span><span>최근</span></div></div>';
}
function segTable(d){
 if(!d.seg||!d.seg.length)return '';
 const tot=d.seg.reduce((a,s)=>a+(s[1]||0),0);
 let h='<div class="blk" style="margin-top:18px"><h4>사업부문별 실적 <span style="color:var(--faint);font-weight:400">· '+esc(d.segPeriod||'')+' · '+esc(d.segUnit||'')+'</span></h4>'
  +'<table class="fin"><thead><tr><th>부문</th><th style="text-align:right">매출</th><th style="text-align:right">비중</th><th style="text-align:right">영업이익</th><th style="text-align:right">OPM</th></tr></thead><tbody>';
 d.seg.forEach(([n,rev,op])=>{
  const w=(rev&&tot)?rev/tot*100:null, opm=(rev&&op!=null&&rev!==0)?op/rev*100:null;
  h+='<tr><td>'+esc(n)+'</td><td>'+(rev==null?'—':nf(rev,0))+'</td>'
   +'<td>'+(w==null?'—':'<span class="dim">'+w.toFixed(1)+'%</span>')+'</td>'
   +'<td>'+(op==null?'—':'<span class="'+(op<0?'down':'')+'">'+nf(op,0)+'</span>')+'</td>'
   +'<td>'+(opm==null?'—':pc(opm,1))+'</td></tr>';});
 h+='</tbody></table></div>';
 return h;
}
function bsBlock(d,h){
 const b=d.bs||{},u=d.bsUnit||'';
 const de=(b.liab!=null&&b.equity)?b.liab/b.equity*100:null;
 const nc=d.netcash;
 return '<div class="blk" style="margin-top:18px"><h4>재무상태 <span style="color:var(--faint);font-weight:400">· '+esc(u)+'</span></h4><div class="grid">'
  +[['자산',b.assets==null?'—':nf(b.assets,0)],['부채',b.liab==null?'—':nf(b.liab,0)],['자본',b.equity==null?'—':nf(b.equity,0)],
    ['현금성자산',b.cash==null?'—':nf(b.cash,0)],['총차입금',b.debt==null?'—':nf(b.debt,0)],
    [nc==null?'순현금':(nc>=0?'순현금':'순차입금'),nc==null?'—':'<span class="'+(nc>=0?'up':'down')+'">'+nf(Math.abs(nc),0)+'</span>'],
    ['부채비율',de==null?'—':nf(de,0)+'%'],['PBR',nf((d.f||{}).pbr,2)]]
    .map(([k,v])=>'<div class="cell"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>').join('')+'</div></div>';
}

function finTable(f,unit){
 if(!f||!f.p)return '<div class="hint">재무 데이터가 없습니다.</div>';
 const R=f.r,P=f.p;
 const yoy=a=>a.map((v,i)=>(v!=null&&a[i+1]!=null&&a[i+1]!==0)?(v/Math.abs(a[i+1])-1)*100*(a[i+1]<0?-1:1):null);
 const rows=[];
 const push=(k,ko,dp)=>{if(R[k]&&R[k].some(x=>x!=null))rows.push([ko,R[k],dp==null?0:dp,false]);};
 push('REV','매출');
 if(R.REV)rows.push(['매출 YoY',yoy(R.REV),1,true]);
 push('OI','영업이익');
 if(R.REV&&R.OI)rows.push(['영업이익률',R.OI.map((v,i)=>(v!=null&&R.REV[i])?v/R.REV[i]*100:null),1,true]);
 push('NI','순이익');
 if(R.NI)rows.push(['순이익 YoY',yoy(R.NI),1,true]);
 push('EPS','EPS',2);
 push('FCF','잉여현금흐름');
 push('DPS','주당배당',2);
 let h='<table class="fin"><thead><tr><th>항목 ('+esc(unit)+')</th>'+P.map(p=>'<th style="text-align:right">'+esc(p)+'</th>').join('')+'</tr></thead><tbody>';
 rows.forEach(([ko,arr,dp,isPct])=>{
  const mg=ko.indexOf('률')>=0;
  h+='<tr><td'+(isPct?' class="dim"':'')+'>'+ko+'</td>'+arr.map(v=>'<td>'+(v==null?'—':(isPct?(mg?'<span class="'+(v<0?'down':'flat')+'">'+v.toFixed(dp)+'%</span>':pc(v,dp)):nf(v,Math.abs(v)>=1000?0:dp)))+'</td>').join('')+'</tr>';});
 h+='</tbody></table>';
 if(R.REV)h+='<div style="margin-top:12px"><div class="hint" style="margin-bottom:4px">매출 추이 (좌→우: 최근→과거)</div>'+bars(R.REV,'#B8862C')+'</div>';
 return h;
}
function render(){
 const h=D.holdings.find(x=>x.key===curKey);if(!h)return;
 const d=D.details[curKey]||{},f=d.f||{};
 document.getElementById('dwName').textContent=h.nm;
 document.getElementById('dwSub').textContent=h.mkt+' · '+h.tk+' · '+(h.branch==='T'?'추세':'반전')+' 경로';
 document.getElementById('dwPx').innerHTML='<b>'+nf(h.cur,h.ccy==='KRW'?0:2)+'</b><span>'+h.ccy+'</span>'
   +'<span>진입 '+nf(h.entry,h.ccy==='KRW'?0:2)+'</span><span>현지 '+pc(h.loc*100)+'</span><span>USD '+pc(h.usd*100)+'</span>';
 const b=document.getElementById('dwBody');
 if(curTab==='개요'){
  const lo=f.lo52,hi=f.hi52,c=h.cur;
  const pos=(lo!=null&&hi!=null&&hi>lo)?Math.max(0,Math.min(100,(c-lo)/(hi-lo)*100)):null;
  const rsi=f.rsi;
  b.innerHTML=
   '<div class="blk"><h4>주가 추이 <span style="color:var(--faint);font-weight:400">· 최근 60주 (주봉)</span></h4>'+priceChart(d.hist,h.ccy)+'</div>'
   +(d.bm?'<div class="blk"><h4>비즈니스 모델</h4><div class="rng"><p style="margin:0;font-size:12.8px;line-height:1.72;color:#D6DFEE">'+esc(d.bm)+'</p></div></div>':'')
   +'<div class="blk"><h4>가격 위치</h4><div class="rng">'
   +(pos==null?'<div class="hint">52주 데이터 없음</div>':
     '<div class="rngbar"><u style="left:0;width:'+pos.toFixed(1)+'%"></u><i style="left:calc('+pos.toFixed(1)+'% - 1px)"></i></div>'
     +'<div class="rngl"><span>52주 저 '+nf(lo,h.ccy==='KRW'?0:2)+'</span><span>고점 대비 '+pos.toFixed(0)+'%</span><span>52주 고 '+nf(hi,h.ccy==='KRW'?0:2)+'</span></div>')
   +'</div></div>'
   +'<div class="blk"><h4>밸류에이션</h4><div class="grid">'
   +[['PER',nf(h.pe,1)],['FW PER',nf(h.fpe,1)+(h.flag?' <span class="fl">⚑</span>':'')],['PBR',nf(f.pbr,2)],['PSR',nf(f.psr,2)],
     ['EV/EBITDA',nf(f.ev_ebitda,1)],['배당수익률',f.div_yield==null?'—':nf(f.div_yield,2)+'%'],
     ['배당성향',f.payout==null?'—':nf(f.payout,1)+'%'],['시가총액','$'+nf(h.mc_usd,1)+'B']]
     .map(([k,v])=>'<div class="cell"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>').join('')+'</div></div>'
   +'<div class="blk"><h4>수익성 · 재무구조</h4><div class="grid">'
   +[['ROE',f.roe==null?'—':nf(f.roe,1)+'%'],['ROA',f.roa==null?'—':nf(f.roa,1)+'%'],
     ['영업이익률',f.op_margin==null?'—':nf(f.op_margin,1)+'%'],['순이익률',f.net_margin==null?'—':nf(f.net_margin,1)+'%'],
     ['부채/자본',nf(f.de,2)],['베타(1Y)',nf(f.beta,2)],['임직원',f.employees==null?'—':nf(f.employees,0)]]
     .map(([k,v])=>'<div class="cell"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>').join('')+'</div></div>'
   +'<div class="blk"><h4>기술 지표</h4><div class="grid">'
   +[['RSI(14)',nf(rsi,1)],['MACD',ad(f.macd)],['시그널',ad(f.macd_sig)],
     ['20일선 대비',f.sma20==null?'—':pc((c/f.sma20-1)*100)],
     ['50일선 대비',f.sma50==null?'—':pc((c/f.sma50-1)*100)],
     ['200일선 대비',f.sma200==null?'—':pc((c/f.sma200-1)*100)]]
     .map(([k,v])=>'<div class="cell"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>').join('')+'</div>'
   +(rsi==null?'':'<div class="rng" style="margin-top:9px"><div class="hint">RSI '+nf(rsi,1)+' — '+(rsi>70?'과열권':rsi<40?'침체권':'중립~강세권')+'</div><div class="bar"><i style="width:'+Math.min(100,rsi).toFixed(0)+'%"></i></div></div>')
   +'</div>'
   +'<div class="blk"><h4>기간 수익률</h4><div class="grid">'
   +[['1주',f.perf_w],['1개월',f.perf_1m],['3개월',f.perf_3m],['6개월',f.perf_6m],['1년',f.perf_y],['연초 이후',f.perf_ytd]]
     .map(([k,v])=>'<div class="cell"><div class="k">'+k+'</div><div class="v">'+pc(v)+'</div></div>').join('')+'</div></div>'
   +'<div class="blk"><h4>선정 점수</h4><div class="grid">'
   +[['차트 점수',nf(h.chart,0)],['밸류·성장','+'+nf(h.prem,1)],['총점',nf(h.tot,1)],['경로',h.branch==='T'?'추세':'반전']]
     .map(([k,v])=>'<div class="cell"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>').join('')+'</div></div>';
 } else if(curTab==='재무'){
  b.innerHTML='<div class="blk">'
   +'<div class="seg"><button data-fin="annual" aria-pressed="'+(finMode==='annual')+'">연간</button>'
   +'<button data-fin="quarter" aria-pressed="'+(finMode==='quarter')+'">분기</button></div>'
   +finTable(d[finMode],d.unit||'')
   +'<div class="cap" style="margin-top:12px">출처 stockanalysis.com · 좌측이 최신 기간입니다. YoY·영업이익률은 표의 값에서 계산했습니다.</div>'
   +'</div>'+bsBlock(d,h)+segTable(d);
  b.querySelectorAll('[data-fin]').forEach(btn=>btn.onclick=()=>{finMode=btn.dataset.fin;render();});
 } else {
  const nw=d.news||[];
  b.innerHTML='<div class="blk"><h4>최근 주요 이슈</h4>'+(nw.length===0?'<div class="hint">수집된 이슈가 없습니다.</div>':
   '<div class="nw">'+nw.map(([dt,kind,txt,src,url])=>
    '<div class="nwi"><div class="m"><span class="d">'+esc(dt)+'</span><span class="kd '+esc(kind)+'">'+esc(kind)+'</span></div>'
    +'<p>'+esc(txt)+'</p><a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(src)+' ↗</a></div>').join('')+'</div>')
   +'<div class="cap" style="margin-top:12px">수집 기준일 '+esc(D.detailUpdated)+' · 웹 검색 결과 요약이며 투자 판단의 근거로 단독 사용하지 마십시오.</div></div>';
 }
}
function open_(key){
 curKey=key;curTab='개요';finMode='annual';lastFocus=document.activeElement;
 document.querySelectorAll('.tabs button').forEach(t=>t.setAttribute('aria-selected',String(t.dataset.tab===curTab)));
 render();dw.classList.add('on');scrim.classList.add('on');dw.removeAttribute('hidden');
 document.body.style.overflow='hidden';document.querySelector('.close').focus();
}
function close_(){dw.classList.remove('on');scrim.classList.remove('on');document.body.style.overflow='';
 setTimeout(()=>dw.setAttribute('hidden',''),220);if(lastFocus)lastFocus.focus();}
document.querySelectorAll('tbody tr[data-key]').forEach(tr=>{
 tr.tabIndex=0;
 tr.addEventListener('click',()=>open_(tr.dataset.key));
 tr.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open_(tr.dataset.key);}});});
document.querySelectorAll('.tabs button').forEach(t=>t.onclick=()=>{
 curTab=t.dataset.tab;document.querySelectorAll('.tabs button').forEach(x=>x.setAttribute('aria-selected',String(x===t)));render();});
document.querySelector('.close').onclick=close_;scrim.onclick=close_;
addEventListener('keydown',e=>{if(e.key==='Escape'&&dw.classList.contains('on'))close_();});
draw();addEventListener('resize',()=>{clearTimeout(window.__t);window.__t=setTimeout(draw,150);});
