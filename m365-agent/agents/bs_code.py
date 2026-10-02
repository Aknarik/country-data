def structure(cty,what='loans',kind='stack',year=None):
 r=lp(cty) if what=='loans' else get('Bk',cty).pipe(lambda d:d[d['Indicator code'].str[:8]=='BANK_STR'])
 assert len(r),'No data for '+cty;f,ax=plt.subplots(figsize=(11,5.8));p=mix(ax,r,kind,year)
 title(ax,f"{r['Economy'].iloc[0]}: "+('Bank loan portfolio by sector' if what=='loans' else 'Bank asset structure by counterparty')+p+' (percent of total)');source(f,r)
TAB['La']=('Soundness','Loan_amounts')
BS=[('CREDIT_TA','Credit'),('STR_PRIV','Private sector claims'),('STR_PUBNFC','Public corporations claims'),('GOV_TA','Government claims'),('NRES_TA','Foreign assets'),
 ('CB_TA','Central bank claims'),('DEPOSITS_TA','Deposits'),('FOREIGN_LIAB_TA','Foreign liabilities'),('EQUITY_TA','Equity')]
def lev(cty,what,parts=0):
 if what=='loans':
  r=lp(cty,'La');assert len(r),'No data for '+cty;L=r.set_index('Indicator')[per(r)];return L,L.sum(min_count=1),r,'Bank credit'
 r=get('Bk',cty);I=r.set_index('Indicator code').reindex(columns=per(r));assert 'BANK_ASSETS' in I.index,'No data for '+cty;b=I.loc['BANK_ASSETS']
 K=[(k,re.sub('.*: ','',n)) for k,n in zip(r['Indicator code'],r['Indicator']) if k[:8]=='BANK_STR'] if parts else [('BANK_'+k,n) for k,n in BS]
 return pd.DataFrame({n:b*I.loc[k]/100 for k,n in K if k in I.index}).T,b,r,'Bank assets'
def prev(L):return L.reindex(columns=[str(int(k[:4])-1)+k[4:] for k in L.columns])
def growth(cty,what='balance',a=2012):
 L,b,r,t=lev(cty,what);L.loc['Total']=b;g=(100*(L/prev(L).values-1)).round(1).dropna(axis=1,how='all')
 m=(L.div(b)*100).iloc[:,-4:].mean(axis=1).values>=5;g=g.rename_axis('Indicator').reset_index().assign(Unit='Annual percent change',Citation=r['Citation'].iloc[0]+'; growth: own calculation')
 f,ax=plt.subplots(figsize=(10.5,5.5));lines(ax,g[m],a);ax.axhline(0,color='k',lw=.5);title(ax,f"{r['Economy'].iloc[0]}: {t} growth by item, nominal (annual percent change)");source(f,g)
 print(g.set_index('Indicator')[per(g,a)].to_string());return g
def contrib(cty,what='balance',a=2012):
 L,b,r,t=lev(cty,what,1);P=prev(L);C=(100*(L-P.values)/P.sum(min_count=1).values).loc[:,[int(k[:4])>=a for k in L.columns]].dropna(axis=1,how='all')
 x=num(list(C.columns));w=.2 if '-Q' in C.columns[0] else .6;f,ax=plt.subplots(figsize=(11,5.8));bp=np.zeros(len(x));bn=bp.copy()
 for i,(k,z) in enumerate(C.fillna(0).iterrows()):p=np.clip(z.values,0,None);ax.bar(x,p,w,bottom=bp,color=plt.cm.tab20(i),label=k);ax.bar(x,z.values-p,w,bottom=bn,color=plt.cm.tab20(i));bp+=p;bn+=z.values-p
 g=C.sum(min_count=1).values;ax.plot(x,g,'ko',ms=4,label='Total growth');last(ax,x,g);ax.axhline(0,color='k',lw=.5);leg(ax);ax.locator_params(axis='x',integer=True)
 title(ax,f"{r['Economy'].iloc[0]}: {t} growth, contributions by sector (percentage points)");source(f,r);return C
