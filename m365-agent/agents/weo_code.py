D=T('World_Economic','Data');G=T('World_Economic','Groups')
def members(g):return list(G.loc[G[g]=='Yes','Economy code'])
def weo(ctys,codes):
 r=pick(D,ctys);return r[r['Indicator code'].isin([codes] if isinstance(codes,str) else codes)]
def who(r):
 e=set(r['Economy code']);g=[c for c in G.columns[2:-1] if set(members(c))==e]
 return g[0] if g else r['Economy'].iloc[0] if len(e)==1 else ', '.join(r['Economy'].unique()[:4])
def pj(r):return int(pd.to_numeric(r['First projection year'],errors='coerce').min())
def line(r,a=2000,b=2031,t=None):
 c=per(r,a,b);x=num(c);V=vals(r,c);P=pj(r);one=r['Indicator code'].nunique()==1
 f,ax=plt.subplots(figsize=(10.5,5.8))
 for lab,v,p in zip(r['Economy'] if one else r['Indicator'],V,r['First projection year']):
  h=x<p;l,=ax.plot(x[h],v[h],lw=2.2,label=lab);last(ax,x[h],v[h],l.get_color());ax.plot(x[x>=p-1],v[x>=p-1],lw=2.2,ls='--',color=l.get_color())
 ax.axvspan(P-.5,x[-1]+.5,color='gray',alpha=.12);ax.set_xlim(x[0]-.5,x[-1]+.5)
 ax.text(P-.3,.98,f'IMF projections\n{P} onward',transform=ax.get_xaxis_transform(),va='top',fontsize=8,color='dimgray')
 if np.nanmin(V)<0<np.nanmax(V):ax.axhline(0,color='k',lw=.8)
 ax.grid(alpha=.3);ax.set_ylabel(r['Unit'].iloc[0]);leg(ax)
 ax.xaxis.get_major_locator().set_params(integer=True)
 title(ax,t or who(r)+': '+(r['Indicator'].iloc[0] if one else ', '.join(r['Indicator'].unique()))+U(r))
 source(f,r)
def bar(r,year=None,hl=None):
 P=pj(r);y=str(year or P-1);s=r.set_index('Economy')[y].dropna().sort_values()
 f,ax=plt.subplots(figsize=(9,.28*len(s)+1.8));pr=int(y)>=P
 ax.barh(s.index,s.values,color=['#c0392b' if k==hl else BLUE for k in s.index]);pr and(ax.set_facecolor('#ececec'),ax.text(.99,.02,'IMF projection',transform=ax.transAxes,ha='right',color='dimgray'))
 for i,v in enumerate(s.values):ax.text(v,i,f' {v:,.1f}',va='center',fontsize=7)
 ax.axvline(0,color='k',lw=.8);ax.grid(alpha=.3,axis='x');ax.set_xlabel(r['Unit'].iloc[0])
 title(ax,f"{who(r)}: {r['Indicator'].iloc[0]}, {y}{U(r)}");source(f,r)
def table(r,years=range(2019,2032)):
 y=[str(k) for k in years if str(k) in r];P=pj(r)
 t=r.set_index(['Economy','Indicator'])[y].round(1);t.columns=[k+('*' if int(k)>=P else '') for k in y]
 print(t.to_string());print('* IMF projection. Source:',r['Citation'].iloc[0])
DASH=[('NGDP_RPCH','Real GDP growth, percent'),('PCPIPCH','Inflation, average, percent'),('LUR','Unemployment rate, percent'),
 ('GGXCNL_NGDP','Fiscal balance, percent of GDP'),('GGXWDG_NGDP','Government gross debt, percent of GDP'),('BCA_NGDPD','Current account, percent of GDP')]
def dashboard(cty,a=2015,b=2031):
 r=weo(cty,[k for k,_ in DASH]);P=pj(r);f,axs=plt.subplots(2,3,figsize=(16,10))
 for ax,(k,lab) in zip(axs.flat,DASH):
  q=r[r['Indicator code']==k]
  if q.empty:ax.axis('off');ax.set_title(lab+': no data',fontsize=9);continue
  c=per(q,a,b);x=num(c);v=vals(q,c)[0]
  ax.set_xlim(x[0]-.6,x[-1]+.6);ax.bar(x,v,color=BLUE);ax.axvspan(P-.5,x[-1]+.6,color='gray',alpha=.15);last(ax,x[x<P],v[x<P])
  ax.text(P-.4,.98,'Projections',transform=ax.get_xaxis_transform(),va='top',fontsize=7,color='dimgray')
  ax.axhline(0,color='k',lw=.8);ax.grid(alpha=.3,axis='y');ax.xaxis.get_major_locator().set_params(integer=True);ax.set_title(lab,loc='left',fontsize=10,color=BLUE,weight='bold')
 f.suptitle(f"{r['Economy'].iloc[0]}: Macroeconomic dashboard",x=.01,ha='left',color=BLUE,weight='bold',fontsize=14)
 source(f,r)
