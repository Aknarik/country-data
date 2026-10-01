def heatmap(cty,q=12):
 r=get('F',cty).drop_duplicates('Indicator code');c=per(r);V=r[c].apply(pd.to_numeric,errors='coerce')
 k=(V.notna().sum(axis=1)>=8).values;r,V=r[k],V[k];R=V.apply(lambda s:(s.rank(method='min')-1)/(s.count()-1),axis=1)
 lo=(r['More vulnerable when']=='lower').values;R[lo]=1-R[lo];c=[k for k in c if V[k].notna().any()][-q:];V,R=V[c],R[c]
 r,V,R=r.reset_index(drop=True),V.reset_index(drop=True),R.reset_index(drop=True);lb=list(r['Indicator'])
 w=.06*max(map(len,lb))+.3;W=w+3+.7*len(c);h=1.8+.4*len(V)
 f,ax=plt.subplots(figsize=(W,h));f.subplots_adjust(left=w/W,right=1-2.6/W,top=1-.6/h,bottom=1.2/h)
 im=ax.imshow(R.values.astype(float),cmap='RdBu_r',vmin=0,vmax=1,aspect='auto')
 for i in range(len(V)):
  for j in range(len(c)):
   if pd.notna(V.iat[i,j]):ax.text(j,i,f'{V.iat[i,j]:.1f}',ha='center',va='center',fontsize=7,color='w' if abs(R.iat[i,j]-.5)>.3 else 'k')
 ax.set_yticks(range(len(V)));ax.set_yticklabels(lb,fontsize=7);ax.set_xticks(range(len(c)));ax.set_xticklabels(c,rotation=45,fontsize=7)
 for g,d in r.groupby('Group',sort=False):
  ax.text(len(c)-.35,d.index.to_numpy().mean(),g,va='center',fontsize=7,weight='bold',color=BLUE);d.index[0] and ax.axhline(d.index[0]-.5,color='w',lw=3)
 f.colorbar(im,cax=f.add_axes([1-.8/W,1.2/h,.12/W,1-1.8/h]),label='Red = more vulnerable');title(ax,r['Economy'].iloc[0]+': FSI heat map, percentile vs own history');source(f,r,tl=False)
def dashboard(cty):
 f,A=plt.subplots(2,3,figsize=(18,11.5));A=A.flat;u=[]
 P=[('Capital','F',['FSI688_CFSI_PT','FSI626_CFSI_PT']),('Asset quality','F',['AQ12_CFSI_PT','AQ14_CFSI_PT']),('Profitability','F',['ROA_CFSI_PT','ROE_CFSI_PT']),
  ('Liquidity','F',['FSI283_LIQATTA_PT','FSI55_AFSI_PT']),('Loan portfolio','Lp',0),('Sovereign-bank nexus','Bk',['BANK_GOV_TA','BANK_GOV_GDP'])]
 for ax,(t,n,k) in zip(A,P):
  r=lp(cty) if n=='Lp' else get(n,cty,k)
  if len(r)==0:ax.axis('off');ax.set_title(t+': no data',loc='left');continue
  ax.set_title(t+(mix(ax,r,'pie',None) if n=='Lp' else ''),loc='left',color=BLUE,weight='bold');n=='Lp' or lines(ax,r,2016,1);u.append(r)
 f.suptitle(f"{u[0]['Economy'].iloc[0]}: Banking sector dashboard, percent",x=.01,ha='left',color=BLUE,weight='bold');source(f,*u)
