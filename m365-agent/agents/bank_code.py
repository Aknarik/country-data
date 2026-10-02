def structure(cty,what='loans',kind='stack',year=None):
 r=lp(cty) if what=='loans' else get('Bk',cty).pipe(lambda d:d[d['Indicator code'].str[:8]=='BANK_STR'])
 assert len(r),'No data for '+cty;f,ax=plt.subplots(figsize=(11,5.8));p=mix(ax,r,kind,year)
 title(ax,f"{r['Economy'].iloc[0]}: "+('Bank loan portfolio by sector' if what=='loans' else 'Bank asset structure by counterparty')+p+' (percent of total)');source(f,r)
def banks(cty,ind='T1',year=None):
 r=get('Hb',cty,f'HEAT_{ind}_BANK');n=r[per(r)].notna().sum();y=str(year or n[n>=.6*n.max()].index[-1])
 s=r.set_index('Economy')[y].dropna().sort_values();f,ax=plt.subplots(figsize=(10,.3*len(s)+2));ax.barh(s.index,s.values,color=BLUE)
 ax.axvline(s.median(),color='#c0392b',ls='--',label=f'Median bank {s.median():.1f}');leg(ax,y=-.12);ax.grid(alpha=.3,axis='x')
 e=get('Bk',cty)['Economy'];title(ax,f"{e.iloc[0] if len(e) else cty}: {r['Indicator'].iloc[0]} by bank, {y}{U(r)}");source(f,r);return s
TAB['La']=('Soundness','Loan_amounts')
BS=[('CREDIT_TA','Credit'),('STR_PRIV','Private sector claims'),('STR_PUBNFC','Public corporations claims'),('GOV_TA','Government claims'),('NRES_TA','Foreign assets'),
 ('CB_TA','Central bank claims'),('DEPOSITS_TA','Deposits'),('FOREIGN_LIAB_TA','Foreign liabilities'),('EQUITY_TA','Equity')]
def growth(cty,what='balance',a=2012):
 if what=='loans':
  r=lp(cty,'La')
  assert len(r),'No data for '+cty;L=r.set_index('Indicator')[per(r)];L.loc['Total loans']=L.sum(min_count=1);b=L.loc['Total loans'];t='Bank credit by sector'
 else:
  r=get('Bk',cty);I=r.set_index('Indicator code').reindex(columns=per(r))
  assert 'BANK_ASSETS' in I.index,'No data for '+cty;b=I.loc['BANK_ASSETS'];t='Bank balance sheet'
  L=pd.DataFrame({'Total assets':b,**{n:b*I.loc['BANK_'+k]/100 for k,n in BS if 'BANK_'+k in I.index}}).T
 c=list(L.columns);g=pd.DataFrame(100*(L.values/L.reindex(columns=[str(int(k[:4])-1)+k[4:] for k in c]).values-1),L.index,c).round(1).dropna(axis=1,how='all')
 m=(L.div(b)*100).iloc[:,-4:].mean(axis=1).values>=5;g=g.rename_axis('Indicator').reset_index().assign(Unit='Annual percent change',Citation=r['Citation'].iloc[0]+'; growth: own calculation')
 f,ax=plt.subplots(figsize=(10.5,5.5));lines(ax,g[m],a);ax.axhline(0,color='k',lw=.5);title(ax,f"{r['Economy'].iloc[0]}: {t} growth, nominal (annual percent change)",'Items under 5 percent of the total: table only');source(f,g)
 print(g.set_index('Indicator')[per(g,a)].to_string());return g
