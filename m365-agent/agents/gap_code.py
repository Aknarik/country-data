CQ=T('BIS_credit','Credit_GDP_Quarterly');M=T('IMF_MFS_credit','Credit_GDP_Annual');CS=T('BIS_credit','Credit_by_sector')
MP=T('iMaPP','Summary');MA=T('iMaPP','Actions');TOOLS=list(T('iMaPP','Definitions')['Tool code'])
def hp(y,lam):
 o=[]
 for t in range(1,len(y)+1):d=np.diff(np.eye(t),2,axis=0);o.append(y[t-1] if t<3 else np.linalg.solve(np.eye(t)+lam*d.T@d,y[:t])[-1])
 return np.array(o)
def _s(s):s=pd.Series(s,dtype=float).dropna();s.index=[re.sub(r'^(\d{4})\D*Q(\d)$',r'\1-Q\2',str(i).strip()) for i in s.index];return s
def user_gap(credit,gdp=None,name='User data',lam=None):
 s=_s(credit);q='-Q' in s.index[0]
 if gdp is not None:g=_s(gdp);g=g.rolling(4).sum() if q else g;s=(100*s/g.reindex(s.index)).dropna()
 assert len(s)>(40 if q else 10),'Need over 10 years; 20+ recommended';len(s)<(80 if q else 20) and print('Caution: under 20 years, gap less reliable');l=lam or(4e5 if q else 1e5);t=hp(s.values,l);t[:40 if q else 10]=np.nan
 c=f'{name}: user data; own calculation, one-sided HP filter (lambda {l:,.0f}), Basel III method (BCBS 2010)'
 return pd.DataFrame([{'Economy':name,'Economy code':name,'Indicator code':k,'Citation':c,**dict(zip(s.index,v))} for k,v in(('CREDIT_GDP',s.values),('CREDIT_GDP_TREND',t),('CREDIT_GDP_GAP',s.values-t))])
def buffer(g):return 0 if g<2 else 2.5 if g>10 else round((g-2)/8*2.5,2)
def gap(r,a=2000,mpp=True):
 if isinstance(r,str):r=pick(M,r) if len(pick(M,r)) else pick(CQ,r)
 I=r.set_index('Indicator code');c=[k for k in per(r,a) if pd.notna(I.loc['CREDIT_GDP',k])];x=num(c);v=lambda k:pd.to_numeric(I.loc[k,c]).values
 f,(ax,a2)=plt.subplots(2,1,figsize=(10.5,7.5),sharex=True,gridspec_kw={'height_ratios':[2,1.2]})
 ax.plot(x,v('CREDIT_GDP'),lw=2.2,color=BLUE,label='Credit-to-GDP ratio');ax.plot(x,v('CREDIT_GDP_TREND'),'--',lw=2,color='#e67e22',label='One-sided HP trend')
 g=v('CREDIT_GDP_GAP');a2.bar(x,g,width=.22 if '-Q' in c[0] else .8,color=['#c0392b' if z>=0 else BLUE for z in g])
 a2.axhspan(2,10,color='#c0392b',alpha=.07);a2.text(x[0],10,' Basel buffer range 2-10 pp',fontsize=7,color='#c0392b',va='bottom')
 a2.xaxis.get_major_locator().set_params(integer=True);a2.axhline(0,color='k',lw=.8);a2.set_ylabel('Gap, pp of GDP');ax.set_ylabel('% of GDP');a2.grid(alpha=.3);ax.grid(alpha=.3)
 m=MA[(MA['Economy code']==r['Economy code'].iloc[0])&MA['Indicator code'].isin(TOOLS)] if mpp else MA[:0]
 if len(m):
  n=m[per(m)].apply(pd.to_numeric,errors='coerce').sum();n=n[(n!=0)&(n.index.astype(int)>=x[0])]
  for y,z in n.items():ax.axvline(int(y)+.5,color='#c0392b' if z>0 else 'green',alpha=.35,lw=1.5)
  ax.plot([],[],color='#c0392b',alpha=.5,label='Net tightening (iMaPP)');ax.plot([],[],color='green',alpha=.5,label='Net loosening')
 ax.legend(frameon=False,fontsize=8);gv=g[~np.isnan(g)][-1];lg=np.array(c)[~np.isnan(g)][-1]
 title(ax,f"{r['Economy'].iloc[0]}: credit-to-GDP ratio, trend and gap",f"Latest {lg}: gap {gv:.1f} pp, Basel guide buffer {buffer(gv)}%");source(f,r,m,note=len(m) and 'Lines: iMaPP scores each tool +1 in a month it is tightened, -1 if loosened; summed per year over 17 tools: red >0, green <0.' or '')
def sectors(cty,a=2000):
 r=pick(CS,cty);assert len(r),'No BIS sector data for '+cty;c=[k for k in per(r,a) if r[k].notna().any()];f,ax=plt.subplots(figsize=(10.5,5.5))
 for lab,z in zip(r['Indicator'],vals(r,c)):ax.plot(num(c),z,lw=2,label=lab)
 ax.grid(alpha=.3);ax.legend(frameon=False,fontsize=8);title(ax,f"{r['Economy'].iloc[0]}: credit by borrower sector",'% of GDP');source(f,r)
def mpp_table(cty):
 t=pick(MP,cty).sort_values('Latest action',ascending=False)
 print(t.iloc[:,[3,*range(9,16)]].fillna('').to_string(index=False))  # Tool, latest action..description
