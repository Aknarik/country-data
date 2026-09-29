# Country Data Assistant - tools for the Microsoft 365 Copilot agent's Code interpreter.
# build_data_file.py stores this file, one line per row, in a sheet "Code" of every workbook
# (and in Agent_tools.xlsx); the agent runs it with exec(). Keep it self-contained
# (pandas, numpy, matplotlib only).
import glob, os, re, textwrap, numpy as np, pandas as pd, matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

fs = sorted({os.path.abspath(p) for pat in ('/mnt/**/*.xls*', '/home/**/*.xls*', '**/*.xls*')
             for p in glob.glob(pat, recursive=True)})


def xl(key, sheet):
    """Load a sheet from the first workbook whose name contains `key`; None if not available."""
    p = next((p for p in fs if key in os.path.basename(p)), None)
    return pd.read_excel(p, sheet_name=sheet) if p else None


D, G = xl('World_Economic_Outlook', 'Data'), xl('World_Economic_Outlook', 'Groups')
F = xl('Financial_Soundness', 'FSI_Quarterly')
CQ, CA = xl('BIS_credit', 'Credit_GDP_Quarterly'), xl('BIS_credit', 'Credit_GDP_Annual')
M = xl('IMF_MFS_credit', 'Credit_GDP_Annual')
_loaded = {'D (IMF WEO)': D, 'G (groups)': G, 'F (FSI)': F, 'CQ/CA (BIS credit)': CQ, 'M (Gulf MFS credit)': M}
print('Loaded:', ', '.join(k for k, v in _loaded.items() if v is not None) or 'no data workbooks')
if any(v is None for v in _loaded.values()):
    print('Not available:', ', '.join(k for k, v in _loaded.items() if v is None),
          '| workbooks found:', [os.path.basename(p) for p in fs])
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
# Groups and directions come from the FSI workbook: column Group, and column "More vulnerable when"
# ("higher" or "lower"), set from a financial-sector vulnerability perspective.


def percent_rank(s):
    """Excel PERCENTRANK.INC of every value within its own series: (values below) / (n - 1)."""
    s = s.dropna(); return (s.rank(method='min') - 1) / (len(s) - 1) if len(s) > 1 else s * np.nan


def fsi_heatmap(country, quarters=12, min_history=8):
    """Heat map of FSIs: colour = vulnerability percentile vs the country's own history
    (0 = least vulnerable ever, dark blue; 1 = most vulnerable ever, dark red); cells show actual values."""
    rows = F[(F['Economy'].str.lower() == country.lower()) | (F['Economy code'] == country.upper())]
    rows = rows.drop_duplicates('Indicator code').set_index('Indicator code')
    per = [c for c in rows.columns if re.fullmatch(r'\d{4}-Q\d', str(c))]
    V = rows[per].apply(pd.to_numeric, errors='coerce')
    V = V[V.notna().sum(axis=1) >= min_history]
    rows = rows.loc[V.index]
    R = V.apply(percent_rank, axis=1).reindex(columns=per)
    lower = (rows['More vulnerable when'] == 'lower').values; R.loc[lower] = 1 - R.loc[lower]
    first = min(V.apply(lambda r: r.first_valid_index(), axis=1).dropna())
    cols = [c for c in per if V[c].notna().any()][-quarters:]
    V, R = V[cols], R[cols]
    # explicit layout in inches: labels left, group names right, colour bar and source below
    L = 0.3 + 0.062 * rows['Indicator'].str.len().max(); Rt = 0.4 + 0.07 * rows['Group'].str.len().max()
    w, h, top, bot = 0.7 * len(cols), 0.42 * len(V), 0.75, 1.75
    W, H = L + w + Rt, top + h + bot
    fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([L / W, bot / H, w / W, h / H])
    im = ax.imshow(R.values.astype(float), cmap='RdBu_r', vmin=0, vmax=1, aspect='auto')
    for i in range(len(V)):
        for j in range(len(cols)):
            v, r = V.iat[i, j], R.iat[i, j]
            if pd.notna(v):
                ax.text(j, i, f'{v:.1f}', ha='center', va='center', fontsize=8,
                        color='white' if pd.notna(r) and abs(r - 0.5) > 0.3 else 'black')
    ax.set_yticks(range(len(V))); ax.set_yticklabels(rows['Indicator'], fontsize=8)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=45, ha='right', fontsize=8)
    groups = list(rows['Group'])
    starts = [i for i in range(len(groups)) if i == 0 or groups[i] != groups[i - 1]]
    for i in starts[1:]: ax.axhline(i - 0.5, color='black', lw=1.2)
    ax2 = ax.twinx(); ax2.set_ylim(ax.get_ylim())
    ax2.set_yticks([(s + e - 1) / 2 for s, e in zip(starts, starts[1:] + [len(groups)])])
    ax2.set_yticklabels([groups[s] for s in starts], fontsize=8, weight='bold', color=BLUE)
    ax2.tick_params(length=0); ax2.spines[:].set_visible(False)
    cax = fig.add_axes([L / W, 0.55 / H, min(w, 5) / W, 0.13 / H])
    cb = fig.colorbar(im, cax=cax, orientation='horizontal'); cb.set_ticks([0, 0.5, 1])
    cb.set_ticklabels(['Less vulnerable', 'Median', 'More vulnerable']); cb.ax.tick_params(labelsize=8)
    ax.set_title(f"{rows['Economy'].dropna().iloc[0]}: financial soundness heat map\n"
                 "colour = percent rank vs own history (dark red = most vulnerable, dark blue = least)",
                 loc='left', weight='bold', color=BLUE, fontsize=10)
    note = f"Each indicator is ranked against all its own quarters since {first} (Excel PERCENTRANK.INC)."
    fig.text(0.01, 0.06 / H, textwrap.fill(f"Source: {rows['Citation'].dropna().iloc[0]}. {note}", int(W * 14)),
             fontsize=8, color='dimgray'); plt.show()
    return pd.DataFrame({'Group': rows['Group'].values, 'Indicator': rows['Indicator'].values,
                         'Latest value': V.ffill(axis=1).iloc[:, -1].round(2).values,
                         'Vulnerability percentile': R.ffill(axis=1).iloc[:, -1].round(2).values})
