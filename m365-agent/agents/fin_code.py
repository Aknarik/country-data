TAB=dict(F=('Soundness','FSI_Quarterly'),Lp=('Soundness','Loan_portfolio'),Bk=('banking_sector','Banking'),H=('HEAT','HEAT_country'),Hb=('HEAT','HEAT_banks'));_C={}
def get(n,cty,codes=None):
 if n not in _C:_C[n]=T(*TAB[n])
 r=pick(_C[n],cty);return r if codes is None else r[r['Indicator code'].isin([codes] if isinstance(codes,str) else codes)]
def lines(ax,r,a=2010):
 c=[k for k in per(r,a) if r[k].notna().any()];ax.grid(alpha=.3)
 for lab,v in zip(r['Indicator'],vals(r,c)):ax.plot(num(c),v,lw=2,label=lab.split(': ')[-1].capitalize())
 ax.legend(frameon=False,fontsize=7)
def ts(n,cty,codes,t,a=2010):
 r=get(n,cty,codes);f,ax=plt.subplots(figsize=(10.5,5.5));lines(ax,r,a);title(ax,f"{r['Economy'].iloc[0]}: {t}",r['Unit'].iloc[0]);source(f,r)
def heatmap(cty,q=12):
 r=get('F',cty).drop_duplicates('Indicator code');c=per(r);V=r[c].apply(pd.to_numeric,errors='coerce')
 k=(V.notna().sum(axis=1)>=8).values;r,V=r[k],V[k];R=V.apply(lambda s:(s.rank(method='min')-1)/(s.count()-1),axis=1)
 lo=(r['More vulnerable when']=='lower').values;R[lo]=1-R[lo];c=[k for k in c if V[k].notna().any()][-q:];V,R=V[c],R[c]
 lb=[f'{g}: {n}' for g,n in zip(r['Group'],r['Indicator'])];w=.06*max(map(len,lb))+.3;W=w+1.5+.7*len(c);h=1.8+.4*len(V)
 f,ax=plt.subplots(figsize=(W,h));f.subplots_adjust(left=w/W,right=1-1.3/W,top=1-.6/h,bottom=1.2/h)
 im=ax.imshow(R.values.astype(float),cmap='RdBu_r',vmin=0,vmax=1,aspect='auto')
 for i in range(len(V)):
  for j in range(len(c)):
   if pd.notna(V.iat[i,j]):ax.text(j,i,f'{V.iat[i,j]:.1f}',ha='center',va='center',fontsize=7,color='w' if abs(R.iat[i,j]-.5)>.3 else 'k')
 ax.set_yticks(range(len(V)));ax.set_yticklabels(lb,fontsize=7);ax.set_xticks(range(len(c)));ax.set_xticklabels(c,rotation=45,fontsize=7)
 f.colorbar(im,ax=ax,fraction=.03,label='Red = more vulnerable');title(ax,r['Economy'].iloc[0]+': FSI heat map, percentile vs own history');source(f,r,tl=False)
def mix(ax,r,kind,year):
 c=[k for k in per(r) if r[k].sum()>90];lb=np.array([re.sub('.*: ','',i) for i in r['Indicator']]);v=r[c].fillna(0).values
 if kind=='pie':
  j=[i for i,k in enumerate(c) if year is None or k[:4]==str(year)][-1];p=v[:,j]>.5
  ax.pie(v[p,j],labels=lb[p],autopct='%1.0f%%',colors=plt.cm.tab20.colors,textprops={'fontsize':7});return ', '+c[j]
 b=0
 for i,w in enumerate(v):ax.bar(num(c),w,bottom=b,width=.2 if '-Q' in c[0] else .8,label=lb[i],color=plt.cm.tab20(i));b=b+w
 ax.set_ylim(0,100);ax.legend(frameon=False,fontsize=7,loc='upper left',bbox_to_anchor=(1,1));return ''
def lp(cty):
 r=get('Lp',cty);cb=r[~r['Indicator code'].str.endswith('_SH')];return cb if len(cb) else r[r['Indicator code']!='LOANS_RRE_SH']
def structure(cty,what='loans',kind='stack',year=None):
 r=lp(cty) if what=='loans' else get('Bk',cty).pipe(lambda d:d[d['Indicator code'].str[:8]=='BANK_STR'])
 assert len(r),'No data for '+cty;f,ax=plt.subplots(figsize=(11,5.8));p=mix(ax,r,kind,year)
 title(ax,f"{r['Economy'].iloc[0]}: "+('bank loan portfolio by sector' if what=='loans' else 'bank asset structure by counterparty')+p,'% of total');source(f,r)
def banks(cty,ind='T1',year=None):
 r=get('Hb',cty,f'HEAT_{ind}_BANK');n=r[per(r)].notna().sum();y=str(year or n[n>=.6*n.max()].index[-1])
 s=r.set_index('Economy')[y].dropna().sort_values();f,ax=plt.subplots(figsize=(10,.3*len(s)+2));ax.barh(s.index,s.values,color=BLUE)
 ax.axvline(s.median(),color='#c0392b',ls='--',label=f'Median bank {s.median():.1f}');ax.legend(frameon=False,fontsize=8);ax.grid(alpha=.3,axis='x');ax.tick_params(axis='y',labelsize=7)
 title(ax,f"{cty}: {r['Indicator'].iloc[0]} by bank, {y}");source(f,r)
def dashboard(cty):
 f,A=plt.subplots(2,3,figsize=(17,9));A=A.flat;u=[]
 P=[('Capital','F',['FSI688_CFSI_PT','FSI626_CFSI_PT']),('Asset quality','F',['AQ12_CFSI_PT','AQ14_CFSI_PT']),('Profitability','F',['ROA_CFSI_PT','ROE_CFSI_PT']),
  ('Liquidity','F',['FSI283_LIQATTA_PT','FSI55_AFSI_PT']),('Loan portfolio','Lp',0),('Sovereign-bank nexus','Bk',['BANK_GOV_TA','BANK_GOV_GDP'])]
 for ax,(t,n,k) in zip(A,P):
  r=lp(cty) if n=='Lp' else get(n,cty,k)
  if len(r)==0:ax.axis('off');ax.set_title(t+': no data',loc='left');continue
  ax.set_title(t+(mix(ax,r,'pie',None) if n=='Lp' else ''),loc='left',color=BLUE,weight='bold');n=='Lp' or lines(ax,r,2016);u.append(r)
 f.suptitle(f"{u[0]['Economy'].iloc[0]}: banking sector dashboard (%)",x=.01,ha='left',color=BLUE,weight='bold',size=15);source(f,*u)
