import glob,re,textwrap,numpy as np,pandas as pd,matplotlib.pyplot as plt
BLUE='#4B82AD';FILES=glob.glob('/mnt/**/*.xls*',recursive=True)+glob.glob('**/*.xls*',recursive=True)
def T(key,sheet):
 f=[p for p in FILES if key.lower() in p.lower().replace(' ','_')];return pd.read_excel(f[0],sheet_name=sheet) if f else None
def per(r,a=1900,b=2100):return[c for c in r.columns if re.fullmatch(r'\d{4}(-Q\d)?',str(c)) and a<=int(str(c)[:4])<=b]
def num(c):return np.array([int(k[:4])+(int(k[-1])-1)/4 if '-Q' in k else int(k) for k in c])
def vals(r,c):return r[c].apply(pd.to_numeric,errors='coerce').values
def pick(df,cty):c=[str(x).lower() for x in([cty] if isinstance(cty,str) else cty)];return df[df['Economy'].str.lower().isin(c)|df['Economy code'].str.lower().isin(c)]
def title(ax,t,sub=None):
 ax.set_title(t,loc='left',weight='bold',color=BLUE,fontsize=12,pad=18 if sub else 6);sub and ax.text(0,1.01,sub,transform=ax.transAxes,fontsize=8,color='dimgray')
def leg(ax,src=None,y=-.09,n=4):h,l=(src or ax).get_legend_handles_labels();ax.legend(h,l,frameon=False,fontsize=8,loc='upper center',bbox_to_anchor=(.5,y),ncol=n)
def last(ax,x,v,c='k'):
 k=np.flatnonzero(~np.isnan(np.asarray(v,float)))
 if len(k):i=k[-1];ax.annotate(f'{v[i]:,.1f}',(x[i],v[i]),xytext=(4,0),textcoords='offset points',va='center',fontsize=8,color=c,weight='bold')
def source(f,*R,tl=True,note=''):
 s=[]
 for r in R:
  for c,l in zip(r['Citation'],r.reindex(columns=['Source link'])['Source link']):l='' if pd.isna(l) else str(l);s.append(str(c)+(' ('+(l.split('/datamapper')[0]+'/datamapper' if '@' in l else l)+')' if l else ''))
 s=list(dict.fromkeys(s));'CONFIDENTIAL' in str(s) and f.text(.99,.995,'CONFIDENTIAL - IMF internal use only',color='red',ha='right',va='top',weight='bold')
 w=textwrap.fill('Source: '+'; '.join(s),175)+(chr(10)+textwrap.fill('Note: '+note,175) if note else '');f.text(.01,.005,w,fontsize=7,color='gray',va='bottom');tl and f.tight_layout(rect=(0,.15*(w.count(chr(10))+1.5)/f.get_figheight(),1,.97));plt.show()
