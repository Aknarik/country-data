import glob,re,textwrap,numpy as np,pandas as pd,matplotlib.pyplot as plt
BLUE='#4B82AD'
try:plt.rcParams.update({'axes.titlecolor':BLUE,'axes.titleweight':'bold','axes.titlelocation':'left','axes.linewidth':.5,'grid.linewidth':.4,'xtick.major.width':.5,'ytick.major.width':.5})
except Exception:0
FILES=glob.glob('/mnt/**/*.xls*',recursive=True)+glob.glob('**/*.xls*',recursive=True)
def T(key,sheet):
 f=[p for p in FILES if key.lower() in p.lower().replace(' ','_')]
 try:return pd.read_excel(f[0],sheet_name=sheet)
 except Exception:print('Missing:',key,sheet)
def per(r,a=1900,b=2100):return[c for c in r.columns if re.fullmatch(r'\d{4}(-Q\d)?',str(c)) and a<=int(str(c)[:4])<=b]
def num(c):return np.array([int(k[:4])+(int(k[-1])-1)/4 if '-Q' in k else int(k) for k in c])
def vals(r,c):return r[c].apply(pd.to_numeric,errors='coerce').values
def pick(df,cty):c=[str(x).lower() for x in([cty] if isinstance(cty,str) else cty)];return df[df['Economy'].str.lower().isin(c)|df['Economy code'].str.lower().isin(c)]
def U(r):u=r['Unit'].dropna().unique();return' ('+(u[0][0].lower() if u[0][1:2].islower() else u[0][0])+u[0][1:]+')' if len(u)==1 else''
def title(ax,t,sub=None):
 ax.set_title(t,loc='left',weight='bold',color=BLUE,fontsize=12,pad=18 if sub else 6);sub and ax.text(0,1.01,sub,transform=ax.transAxes,fontsize=8,color='dimgray')
def leg(ax,src=None,y=-.09,n=4):h,l=(src or ax).get_legend_handles_labels();ax.legend(h,l,frameon=False,fontsize=8,loc='upper center',bbox_to_anchor=(.5,y),ncol=n)
def last(ax,x,v,c='k',d=0):
 k=np.flatnonzero(~np.isnan(np.asarray(v,float)))
 if len(k):i=k[-1];ax.annotate(f'{v[i]:,.1f}',(x[i],v[i]),xytext=(4,d),textcoords='offset points',va='center',fontsize=8,color=c,weight='bold')
def source(f,*R,tl=True):
 s=list(dict.fromkeys(f'{c} ({l})' if isinstance(l,str) else str(c) for r in R for c,l in zip(r['Citation'],r.reindex(columns=['Source link'])['Source link'])))
 w=textwrap.fill('Source: '+'; '.join(s),175);f.text(.01,.005,w,fontsize=7,color='gray',va='bottom');tl and f.tight_layout(rect=(0,.15*(w.count(chr(10))+1.5)/f.get_figheight(),1,.97),h_pad=2.5,w_pad=2);plt.show()
