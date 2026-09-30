CQ=T('BIS_credit','Credit_GDP_Quarterly');M=T('IMF_MFS_credit','Credit_GDP_Annual');CS=T('BIS_credit','Credit_by_sector')
MP=T('iMaPP','Tools_in_place')
def hp(y,lam):
 o=[]
 for t in range(1,len(y)+1):d=np.diff(np.eye(t),2,axis=0);o.append(y[t-1] if t<3 else np.linalg.solve(np.eye(t)+lam*d.T@d,y[:t])[-1])
 return np.array(o)
def _s(s):s=pd.Series(s,dtype=float).dropna();s.index=[re.sub(r'^(\d{4})\D*Q(\d)$',r'\1-Q\2',str(i).strip()) for i in s.index];return s
def user_gap(credit,gdp=None,name='User data',lam=None):
 s=_s(credit);q='-Q' in s.index[0]
 if gdp is not None:g=_s(gdp);g=g.rolling(4).sum() if q else g;s=(100*s/g.reindex(s.index)).dropna()
 assert len(s)>(40 if q else 10),'Need over 10 years; 20+ recommended';len(s)<(80 if q else 20) and print('Caution: under 20 years, gap less reliable');l=lam or(4e5 if q else 1e5);t=hp(s.values,l);t[:40 if q else 10]=np.nan
 c=f'{name}: user data; one-sided HP filter, lambda {l:,.0f} (BCBS 2010)'
 return pd.DataFrame([{'Economy':name,'Economy code':name,'Indicator code':k,'Citation':c,**dict(zip(s.index,v))} for k,v in(('CREDIT_GDP',s.values),('CREDIT_GDP_TREND',t),('CREDIT_GDP_GAP',s.values-t))])
def buffer(g):return 0 if g<2 else 2.5 if g>10 else round((g-2)/8*2.5,2)
def gap(r,a=2000,mpp=True):
 if isinstance(r,str):r=pick(M,r) if len(pick(M,r)) else pick(CQ,r)
 I=r.set_index('Indicator code');c=[k for k in per(r,a) if pd.notna(I.loc['CREDIT_GDP',k])];x=num(c);v=lambda k:pd.to_numeric(I.loc[k,c]).values
 f,(ax,a2)=plt.subplots(2,1,figsize=(10.5,7.5),sharex=True,gridspec_kw={'height_ratios':[2,1.2]})
 ax.plot(x,v('CREDIT_GDP'),lw=2.2,color=BLUE,label='Credit-to-GDP ratio');ax.plot(x,v('CREDIT_GDP_TREND'),'--',lw=2,color='#e67e22',label='One-sided HP trend');last(ax,x,v('CREDIT_GDP'),BLUE);last(ax,x,v('CREDIT_GDP_TREND'),'#e67e22',-9)
 g=v('CREDIT_GDP_GAP');a2.bar(x,g,width=.22 if '-Q' in c[0] else .8,color=['#c0392b' if z>=0 else BLUE for z in g]);last(a2,x,g)
 a2.axhspan(2,10,color='#c0392b',alpha=.07);a2.text(x[0],10,' Basel range 2-10 pp',fontsize=7,color='#c0392b',va='bottom')
 a2.xaxis.get_major_locator().set_params(integer=True);a2.axhline(0,color='k',lw=.8);a2.set_ylabel('Gap, pp of GDP');ax.set_ylabel('Percent of GDP');a2.grid(alpha=.3);ax.grid(alpha=.3)
 leg(a2,ax,-.2);gv=g[~np.isnan(g)][-1];lg=np.array(c)[~np.isnan(g)][-1]
 title(ax,f"{r['Economy'].iloc[0]}: Credit-to-GDP ratio, trend and gap",f"Latest {lg}: gap {gv:.1f} pp, Basel guide buffer {buffer(gv)} percent");source(f,r)
 e=r['Economy code'].iloc[0]
 if mpp and len(pick(MP,e)):return mpp_table(e)
def sectors(cty,a=2000):
 r=pick(CS,cty);assert len(r),'No BIS sector data for '+cty;c=[k for k in per(r,a) if r[k].notna().any()];f,ax=plt.subplots(figsize=(10.5,5.5))
 for lab,z in zip(r['Indicator'],vals(r,c)):l,=ax.plot(num(c),z,lw=2,label=lab);last(ax,num(c),z,l.get_color())
 ax.grid(alpha=.3);leg(ax);title(ax,f"{r['Economy'].iloc[0]}: Credit by borrower sector",'Percent of GDP');source(f,r)
N='A tool introduced is in place unless later removed; No = no action since 1990. Source: IMF iMaPP Database (Alam et al., 2019).'
def mpp_table(cty):
 t=pick(MP,cty)
 if t.empty:return print(cty,'is not in the IMF iMaPP Database.')
 o=t.iloc[:,2:7].fillna('');o['Latest measure']=o['Latest measure'].str[:170];print(o.to_string(index=False),N,sep='\n');return o
def mpp_compare(ctys,tools=None):
 t=MP[MP['Tool'].str.contains('|'.join(tools),case=False)] if tools else pick(MP,ctys)
 t=t.assign(c=[f'Yes, since {a[:4]}, latest {b[:4]}'+(', '+l if l==l and l else '') for a,b,l in t.iloc[:,3:6].values])
 k=[(e.iloc[0] if len(e) else c+' (not in iMaPP)') for c in ctys for e in[pick(MP,c)['Economy']]]
 o=t.pivot_table(index='Tool',columns='Economy',values='c',aggfunc='first').reindex(columns=k).fillna('No')
 o[[c for c in k if 'iMaPP' in c]]='-';print(o.to_string(),N,sep='\n');return o
