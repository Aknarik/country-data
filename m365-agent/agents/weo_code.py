D=T('World_Economic','Data');G=T('World_Economic','Groups')
def members(g):return list(G.loc[G[g]=='Yes','Economy code'])
def weo(ctys,codes):
 r=pick(D,ctys);return r[r['Indicator code'].isin([codes] if isinstance(codes,str) else codes)]
def pj(r):return int(pd.to_numeric(r['First projection year'],errors='coerce').min())
def line(r,a=2000,b=2031,t=None):
 c=per(r,a,b);x=num(c);V=vals(r,c);P=pj(r);one=r['Indicator code'].nunique()==1
 f,ax=plt.subplots(figsize=(10.5,5.8))
 for lab,v,p in zip(r['Economy'] if one else r['Indicator'],V,r['First projection year']):
  h=x<p;l,=ax.plot(x[h],v[h],lw=2.2,label=lab);ax.plot(x[x>=p-1],v[x>=p-1],lw=2.2,ls='--',color=l.get_color())
 ax.axvspan(P-.5,x[-1]+.5,color='gray',alpha=.12)
 ax.text(P-.3,.98,f'IMF projections\n{P} onward',transform=ax.get_xaxis_transform(),va='top',fontsize=8,color='dimgray')
 if np.nanmin(V)<0<np.nanmax(V):ax.axhline(0,color='k',lw=.8)
 ax.grid(alpha=.3);ax.set_ylabel(r['Unit'].iloc[0]);ax.legend(frameon=False,fontsize=8,ncol=1+len(r)//8)
 ax.xaxis.get_major_locator().set_params(integer=True)
 title(ax,t or(r['Indicator'].iloc[0]+(', '+r['Economy'].iloc[0] if len(r)==1 else '') if one else r['Economy'].iloc[0]),
  'Solid = actual, dashed and shaded = IMF projections')
 source(f,r)
def bar(r,year=None,hl=None):
 P=pj(r);y=str(year or P-1);s=r.set_index('Economy')[y].dropna().sort_values()
 f,ax=plt.subplots(figsize=(9,.28*len(s)+1.8));pr=int(y)>=P
 ax.barh(s.index,s.values,color=['#c0392b' if k==hl else BLUE for k in s.index],alpha=.6 if pr else 1,hatch='//' if pr else None)
 for i,v in enumerate(s.values):ax.text(v,i,f' {v:,.1f}',va='center',fontsize=7)
 ax.axvline(0,color='k',lw=.8);ax.grid(alpha=.3,axis='x');ax.set_xlabel(r['Unit'].iloc[0])
 title(ax,f"{r['Indicator'].iloc[0]}, {y}"+(' (IMF projection)' if pr else ''));source(f,r)
def table(r,years=range(2019,2032)):
 y=[str(k) for k in years if str(k) in r];P=pj(r)
 t=r.set_index(['Economy','Indicator'])[y].round(1);t.columns=[k+('*' if int(k)>=P else '') for k in y]
 print(t.to_string());print('* IMF projection. Source:',r['Citation'].iloc[0])
DASH=[('NGDP_RPCH','Real GDP growth (%)'),('PCPIPCH','Inflation, average (%)'),('LUR','Unemployment rate (%)'),
 ('GGXCNL_NGDP','Fiscal balance (% of GDP)'),('GGXWDG_NGDP','Government gross debt (% of GDP)'),('BCA_NGDPD','Current account (% of GDP)')]
def dashboard(cty,a=2015,b=2031):
 r=weo(cty,[k for k,_ in DASH]);P=pj(r);f,axs=plt.subplots(2,3,figsize=(15,8))
 for ax,(k,lab) in zip(axs.flat,DASH):
  q=r[r['Indicator code']==k]
  if q.empty:ax.axis('off');ax.set_title(lab+': no data',fontsize=9);continue
  c=per(q,a,b);x=num(c);v=vals(q,c)[0]
  ax.bar(x,v,color=[BLUE if y<P else '#a9c4db' for y in x],edgecolor=['none' if y<P else BLUE for y in x])
  ax.axhline(0,color='k',lw=.8);ax.grid(alpha=.3,axis='y');ax.xaxis.get_major_locator().set_params(integer=True);ax.set_title(lab,loc='left',fontsize=10,color=BLUE,weight='bold')
 f.suptitle(f"{r['Economy'].iloc[0]}: macroeconomic dashboard (light bars = IMF projections, {P} onward)",x=.01,ha='left',color=BLUE,weight='bold',fontsize=14)
 source(f,r)
