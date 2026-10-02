TAB.update(H=('IQ_Pro','HEAT_country'),Hb=('IQ_Pro','HEAT_banks'))
def cname(cty):e=get('H',cty)['Economy'];return e.iloc[0] if len(e) else cty
def banks(cty,ind='T1',year=None):
 r=get('Hb',cty,f'HEAT_{ind}_BANK');n=r[per(r)].notna().sum();y=str(year or n[n>=.6*n.max()].index[-1])
 s=r.set_index('Economy')[y].dropna().sort_values();f,ax=plt.subplots(figsize=(10,.3*len(s)+2));ax.barh(s.index,s.values,color=BLUE)
 ax.axvline(s.median(),color='#c0392b',ls='--',label=f'Median bank {s.median():.1f}');leg(ax,y=-.12);ax.grid(alpha=.3,axis='x')
 title(ax,f"{cname(cty)}: {r['Indicator'].iloc[0]} by bank, {y}{U(r)}");source(f,r);return s
def bank_hist(cty,ind='T1',n=8,a=2010):
 r=get('Hb',cty,f'HEAT_{ind}_BANK');t=get('Hb',cty,'HEAT_TA_BANK').set_index('Economy');top=t[per(t)].ffill(axis=1).iloc[:,-1].nlargest(n).index
 f,ax=plt.subplots(figsize=(11,6));lines(ax,r[r['Economy'].isin(top)].assign(Indicator=lambda d:d['Economy']),a,3);c=per(r,a);m=r[c].median()
 ax.plot(num(c),m,'k--',lw=1.5,label='Median bank');v=r[c].stack();ax.set_ylim(min(0,v.quantile(.01)),v.quantile(.97)*1.3);leg(ax,n=3);title(ax,f"{cname(cty)}: {r['Indicator'].iloc[0]} by bank, {n} largest banks{U(r)}");source(f,r);return r
def bank_profile(name,cty=None,a=2010):
 get('Hb','x');d=_C['Hb'];r=d[d['Economy'].str.contains(name,case=False,regex=False)];r=pick(r,cty) if cty else r;assert len(r),'Bank not found: '+name
 n=sorted(r['Economy'].unique(),key=len);print('Other matching banks:',n[1:]) if len(n)>1 else 0;r=r[r['Economy']==n[0]]
 f,A=plt.subplots(2,3,figsize=(16,9))
 for ax,k in zip(A.flat,['T1','TCE','NPLNET','ROAA','LIQ','TA']):
  q=r[r['Indicator code']==f'HEAT_{k}_BANK'];ax.set_title(q['Indicator'].iloc[0] if len(q) else k,loc='left',fontsize=10);len(q) and(lines(ax,q.assign(Indicator=q['Economy']),a,1),ax.get_legend().remove())
 f.suptitle(r['Economy'].iloc[0]+': Bank profile',x=.01,ha='left',color=BLUE,weight='bold');source(f,r);return r
