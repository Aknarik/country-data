def structure(cty,what='loans',kind='stack',year=None):
 r=lp(cty) if what=='loans' else get('Bk',cty).pipe(lambda d:d[d['Indicator code'].str[:8]=='BANK_STR'])
 assert len(r),'No data for '+cty;f,ax=plt.subplots(figsize=(11,5.8));p=mix(ax,r,kind,year)
 title(ax,f"{r['Economy'].iloc[0]}: "+('Bank loan portfolio by sector' if what=='loans' else 'Bank asset structure by counterparty')+p+' (percent of total)');source(f,r)
def banks(cty,ind='T1',year=None):
 r=get('Hb',cty,f'HEAT_{ind}_BANK');n=r[per(r)].notna().sum();y=str(year or n[n>=.6*n.max()].index[-1])
 s=r.set_index('Economy')[y].dropna().sort_values();f,ax=plt.subplots(figsize=(10,.3*len(s)+2));ax.barh(s.index,s.values,color=BLUE)
 ax.axvline(s.median(),color='#c0392b',ls='--',label=f'Median bank {s.median():.1f}');leg(ax,y=-.12);ax.grid(alpha=.3,axis='x')
 e=get('Bk',cty)['Economy'];title(ax,f"{e.iloc[0] if len(e) else cty}: {r['Indicator'].iloc[0]} by bank, {y}{U(r)}");source(f,r);return s
def growth(cty,a=2012):
 r=get('Bk',cty);I=r.set_index('Indicator code').reindex(columns=per(r)).apply(pd.to_numeric,errors='coerce')
 assert 'BANK_ASSETS' in I.index,'No bank balance sheet data for '+cty;ta=I.loc['BANK_ASSETS']
 G={'Total assets':ta,**{n:ta*I.loc[f'BANK_{k}_TA']/100 for k,n in[('CREDIT','Credit to the economy'),('DEPOSITS','Deposits'),('EQUITY','Equity'),('GOV','Claims on government'),('NRES','Foreign assets')] if f'BANK_{k}_TA' in I.index}}
 g=(pd.DataFrame(G).T.pct_change(axis=1)*100).round(1).rename_axis('Indicator').reset_index().assign(Unit='Annual percent change',Citation=r['Citation'].iloc[0]+'; growth: own calculation')
 m=(pd.DataFrame(G).T.div(ta)*100).iloc[:,-5:].mean(axis=1).values>=5
 f,ax=plt.subplots(figsize=(10.5,5.5));lines(ax,g[m],a);ax.axhline(0,color='k',lw=.5);title(ax,r['Economy'].iloc[0]+': Bank balance sheet growth, nominal (annual percent change)','Chart: items of 5+ percent of assets; all items in the table');source(f,g)
 print(g.set_index('Indicator')[per(g,a)].to_string());return g
