# Country Data Assistant - tools for the Microsoft 365 Copilot agent's Code interpreter.
# build_data_file.py stores this file, one line per row, in Agent_tools.xlsx (sheet "Code");
# the agent runs it with exec(). Keep it self-contained (pandas, numpy, matplotlib only).
import glob, re, textwrap, numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

fs = glob.glob('/mnt/data/*.xlsx') + glob.glob('**/*.xlsx', recursive=True)
xl = lambda k, sh: pd.read_excel(next(p for p in fs if k in p), sheet_name=sh)
D, G = xl('World_Economic_Outlook', 'Data'), xl('World_Economic_Outlook', 'Groups')
F = xl('Financial_Soundness', 'FSI_Quarterly')
CQ, CA = xl('BIS_credit', 'Credit_GDP_Quarterly'), xl('BIS_credit', 'Credit_GDP_Annual')
M = xl('IMF_MFS_credit', 'Credit_GDP_Annual')
BLUE, RED = '#4B82AD', '#c0392b'
PERIOD = re.compile(r'\d{4}(-Q\d)?')


def _style(ax):
    ax.grid(alpha=0.3); ax.spines[['top', 'right']].set_visible(False)


def _footer(fig, src):
    fig.text(0.01, 0.01, textwrap.fill(src, 150), fontsize=8, color='dimgray')
    fig.tight_layout(rect=(0, 0.06, 1, 1)); plt.show()


# --------------------------------------------------------------------------- charts
def chart(rows, start=2000, end=2031, kind='line', year=None):
    """kind='line' time series; 'bar' ranking for one period; 'gap' credit-to-GDP ratio + HP trend
    (top) and gap (bottom) - pass the 3 rows CREDIT_GDP, CREDIT_GDP_TREND, CREDIT_GDP_GAP."""
    r0 = rows.iloc[-1]; P = int(r0['First projection year']) if 'First projection year' in rows else None
    per = [c for c in rows.columns if PERIOD.fullmatch(str(c)) and start <= int(str(c)[:4]) <= end]
    x = [int(c[:4]) + (int(c[-1]) - 1) / 4 if '-Q' in c else int(c) for c in per]
    V = rows[per].apply(pd.to_numeric, errors='coerce'); codes = list(rows['Indicator code'])
    many = rows['Indicator'].nunique() > 1; title = r0['Economy'] if many else r0['Indicator']
    L = str(r0.get('Source link') or ''); src = f"Source: {r0['Citation']}. {L.rsplit('/', 1)[0] if '@' in L else L}"
    if kind == 'gap':
        fig, (ax, a2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        for c, lab, ls in (('CREDIT_GDP', 'Credit-to-GDP ratio', '-'), ('CREDIT_GDP_TREND', 'Hodrick-Prescott trend', '--')):
            ax.plot(x, V.values[codes.index(c)], lw=2, ls=ls, label=lab)
        g = V.values[codes.index('CREDIT_GDP_GAP')]
        a2.bar(x, g, width=0.22 if '-Q' in per[0] else 0.8, color=[RED if v >= 0 else BLUE for v in g])
        for h in (2, 10): a2.axhline(h, color='grey', ls=':', lw=1)
        a2.axhline(0, color='black', lw=0.8); a2.set_ylabel('Gap, pp of GDP')
        _style(a2); a2.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylabel('Percent of GDP'); ax.legend(frameon=False)
        title = f"{r0['Economy']}: credit-to-GDP ratio, trend and gap"
    else:
        fig, ax = plt.subplots(figsize=(10, 5.5))
    if kind == 'bar':
        n = V.notna().sum(); y = str(year) if year else (str(P - 1) if P else n[n >= 0.8 * n.max()].index[-1])
        s = rows.set_index('Economy')[y].dropna().sort_values()
        ax.barh(s.index, s.values, color='#2a6fb0'); ax.set_xlabel(r0['Unit'])
        title = f"{title}, {y}" + (' (IMF projection)' if P and int(y[:4]) >= P else '')
    elif kind == 'line':
        for lab, v in zip(rows['Indicator'] if many else rows['Economy'], V.values):
            ax.plot(x, v, lw=2, label=lab)
        if V.min().min() < 0 < V.max().max(): ax.axhline(0, color='black', lw=0.8)
        if P and x[-1] >= P:
            ax.axvspan(P - 0.5, x[-1] + 0.5, color='grey', alpha=0.15, zorder=0)
            ax.text(P, 0.98, ' IMF projections', transform=ax.get_xaxis_transform(), va='top', fontsize=9, color='dimgray')
        ax.set_ylabel(r0['Unit']); ax.legend(frameon=False); ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(title, loc='left', weight='bold', color=BLUE); _style(ax)
    _footer(fig, src)


# --------------------------------------------------------------------------- user data: credit gap
def hp_one_sided(y, lamb):
    """One-sided HP trend: for each t, fit a standard HP filter on y[0..t] and keep the last value."""
    y = np.asarray(y, float); out = np.full(len(y), np.nan)
    for t in range(1, len(y) + 1):
        if t < 3:
            out[t - 1] = y[t - 1]; continue
        d = np.diff(np.eye(t), 2, axis=0)
        out[t - 1] = np.linalg.solve(np.eye(t) + lamb * d.T @ d, y[:t])[-1]
    return out


def to_periods(index):
    """Dates / 2020 / '2020Q1' / '2020-Q1' -> '2020' or '2020-Q1'. Dates become quarters; a series
    with only one date per year (e.g. every 31 Dec) becomes annual."""
    out = []
    for v in index:
        s = str(v).strip().upper().replace(' ', '')
        if re.fullmatch(r'\d{4}(\.0)?', s): out.append(s[:4])
        elif re.fullmatch(r'\d{4}-?Q[1-4]', s): out.append(f'{s[:4]}-Q{s[-1]}')
        else: t = pd.Timestamp(v); out.append(f'{t.year}-Q{t.quarter}')
    if all('-Q' in p for p in out) and len({p[:4] for p in out}) == len(out):
        out = [p[:4] for p in out]
    return out


def user_gap(credit=None, gdp=None, ratio=None, economy='User data', lamb=None, min_years=10, source='User-provided data'):
    """Build the 3 gap rows from the user's own data, ready for chart(rows, kind='gap').
    Give either `ratio` (% of GDP) or `credit` and `gdp` as pandas Series indexed by period/date.
    Quarterly GDP is summed over the last 4 quarters (BIS method); annual GDP with quarterly credit
    is matched by calendar year. lambda: 400,000 quarterly, 100,000 annual (override with lamb)."""
    if ratio is None:
        c = pd.Series(credit.values, index=to_periods(credit.index), dtype=float).dropna()
        g = pd.Series(gdp.values, index=to_periods(gdp.index), dtype=float).dropna()
        qc, qg = '-Q' in c.index[0], '-Q' in g.index[0]
        if qc and qg: g = g.sort_index().rolling(4).sum()
        elif qc: g = pd.Series(g.reindex([p[:4] for p in c.index]).values, index=c.index)
        ratio = 100 * c / g.reindex(c.index)
    else:
        ratio = pd.Series(ratio.values, index=to_periods(ratio.index), dtype=float)
    r = ratio.dropna().sort_index(); q = '-Q' in r.index[0]
    lamb = lamb or (400_000 if q else 100_000)
    tr = pd.Series(hp_one_sided(r.values, lamb), index=r.index)
    tr.iloc[:min_years * (4 if q else 1)] = np.nan
    cite = f"{source}; trend and gap: own calculation, one-sided HP filter (lambda {lamb:,})"
    rows = [dict(Economy=economy, **{'Indicator code': k, 'Indicator': n, 'Unit': u, 'Citation': cite, 'Source link': ''}, **s.to_dict())
            for k, n, u, s in (('CREDIT_GDP', 'Credit-to-GDP ratio', 'Percent of GDP', r),
                               ('CREDIT_GDP_TREND', 'Hodrick-Prescott trend', 'Percent of GDP', tr),
                               ('CREDIT_GDP_GAP', 'Credit-to-GDP gap', 'Percentage points of GDP', r - tr))]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- FSI heat map
FSI_ORDER = ['FSI688_CFSI_PT', 'FSI626_CFSI_PT', 'FSI15_CFSI_PT', 'T1KTA_CFSI_PT', 'AQ12_CFSI_PT', 'FSI17_CFSI_PT',
             'AQ14_CFSI_PT', 'AQ1_CFSI_PT', 'FSI524_CFSI_PT', 'ROA_CFSI_PT', 'ROE_CFSI_PT', 'FSI99_CFSI_PT',
             'FSI107_CFSI_PT', 'FSI765_CFSI_PT', 'FSI288_CFSI_PT', 'FSI289_CFSI_PT', 'FSI555_CFSI_PT']
# Higher value = MORE risk for these; for all others a higher value = LESS risk (rank is flipped).
RISK_UP = {'AQ12_CFSI_PT', 'FSI17_CFSI_PT', 'AQ1_CFSI_PT', 'FSI524_CFSI_PT', 'FSI107_CFSI_PT', 'FSI555_CFSI_PT'}


def percent_rank(s):
    """Excel PERCENTRANK.INC of every value within its own series: (values below) / (n - 1)."""
    s = s.dropna(); return (s.rank(method='min') - 1) / (len(s) - 1) if len(s) > 1 else s * np.nan


def fsi_heatmap(country, quarters=12, min_history=8):
    """Heat map of core FSIs: colour = risk percentile vs the country's own history
    (0 = lowest risk ever, dark blue; 1 = highest risk ever, dark red); cells show actual values."""
    rows = F[(F['Economy'].str.lower() == country.lower()) | (F['Economy code'] == country.upper())]
    rows = rows.set_index('Indicator code').reindex([c for c in FSI_ORDER if c in set(rows['Indicator code'])])
    per = [c for c in rows.columns if re.fullmatch(r'\d{4}-Q\d', str(c))]
    V = rows[per].apply(pd.to_numeric, errors='coerce')
    V = V[V.notna().sum(axis=1) >= min_history]
    R = V.apply(percent_rank, axis=1).reindex(columns=per)
    safer = ~R.index.isin(list(RISK_UP)); R.loc[safer] = 1 - R.loc[safer]
    first = min(V.apply(lambda r: r.first_valid_index(), axis=1).dropna())
    cols = [c for c in per if V[c].notna().any()][-quarters:]
    V, R = V[cols], R[cols]
    fig, ax = plt.subplots(figsize=(4.5 + 0.7 * len(cols), 1.4 + 0.42 * len(V)))
    im = ax.imshow(R.values.astype(float), cmap='RdBu_r', vmin=0, vmax=1, aspect='auto')
    for i in range(len(V)):
        for j in range(len(cols)):
            v, r = V.iat[i, j], R.iat[i, j]
            if pd.notna(v):
                ax.text(j, i, f'{v:.1f}', ha='center', va='center', fontsize=8,
                        color='white' if pd.notna(r) and abs(r - 0.5) > 0.3 else 'black')
    labels = [f"{rows.at[c, 'Indicator']} ({'higher = riskier' if c in RISK_UP else 'higher = safer'})" for c in V.index]
    ax.set_yticks(range(len(V))); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=45, ha='right', fontsize=8)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02); cb.set_ticks([0, 0.5, 1])
    cb.set_ticklabels(['Lower risk', 'Median', 'Higher risk'])
    ax.set_title(f"{rows['Economy'].dropna().iloc[0]}: financial soundness heat map\n"
                 "colour = percent rank vs own history (dark red = highest risk, dark blue = lowest)",
                 loc='left', weight='bold', color=BLUE, fontsize=10)
    note =f"Each indicator is ranked against all its own quarters since {first} (Excel PERCENTRANK.INC)."
    _footer(fig, f"Source: {rows['Citation'].dropna().iloc[0]}. {note}")
    return pd.DataFrame({'Latest value': V.ffill(axis=1).iloc[:, -1],
                         'Risk percentile': R.ffill(axis=1).iloc[:, -1].round(2)},).set_index(pd.Index(
                         [rows.at[c, 'Indicator'] for c in V.index], name='Indicator'))
