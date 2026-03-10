
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from datetime import timedelta, datetime
import textwrap
import os

# --- 1. CHARGEMENT ---
files = [f for f in os.listdir('.') if 'athenee' in f.lower() and (f.endswith('.xlsx') or f.endswith('.csv'))]
if not files:
    print("❌ ERREUR : Fichier 'planning athenee' introuvable dans l'onglet Files.")
else:
    file_name = files[0]
    df = pd.read_excel(file_name) if file_name.endswith('.xlsx') else pd.read_csv(file_name)

    # --- 2. NETTOYAGE ---
    df_clean = df.dropna(subset=['CFC', 'N°appartement', 'Début', 'Fin']).copy()
    month_map = {'Janvier': 'January', 'Février': 'February', 'Mars': 'March', 'Avril': 'April', 'Mai': 'May', 'Juin': 'June', 'Juillet': 'July', 'Août': 'August', 'Septembre': 'September', 'Octobre': 'October', 'Novembre': 'November', 'Décembre': 'December'}

    def parse_date(d):
        if pd.isna(d): return None
        d_str = str(d)
        for fr, en in month_map.items():
            if fr in d_str: d_str = d_str.replace(fr, en); break
        return pd.to_datetime(d_str, format='%d %B %Y %H:%M', errors='coerce')

    df_clean['Start'] = df_clean['Début'].apply(parse_date)
    df_clean['End'] = df_clean['Fin'].apply(parse_date)
    df_clean = df_clean.dropna(subset=['Start', 'End'])
    df_clean['Apt'] = df_clean['N°appartement'].apply(lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x))

    # --- 3. DATES ---
    dt_start = pd.to_datetime(DATE_DEBUT_FORCEE)
    p_start = dt_start - timedelta(days=dt_start.weekday())
    p_end = p_start + timedelta(days=NB_SEMAINES * 7)
    df_zoom = df_clean[((df_clean['Start'] < p_end) & (df_clean['End'] >= p_start))].copy()
    active_cfcs = sorted(df_zoom['CFC'].unique(), key=lambda x: str(x))

    # --- 4. DESSIN ---
    cfc_info = {}
    for cfc in active_cfcs:
        tasks = df_zoom[df_zoom['CFC'] == cfc].sort_values('Start')
        placed, max_lvl = [], 0
        for _, row in tasks.iterrows():
            s, e = mdates.date2num(row['Start']), mdates.date2num(row['End'])
            lvl = 0
            while any(not (e <= ts or s >= te) and tl == lvl for ts, te, tl in placed): lvl += 1
            placed.append((s, e, lvl))
            max_lvl = max(max_lvl, lvl)
        cfc_info[cfc] = (max_lvl + 1, placed)

    total_h = sum([max(2.8, h * 2.0) for h, _ in cfc_info.values()])
    fig = plt.figure(figsize=(LARGEUR_PDF, total_h * 1.6 + 12))
    ax = fig.add_axes([0.15, 0.1, 0.82, 0.8])
    ax.set_xlim(mdates.date2num(p_start), mdates.date2num(p_end))
    ax.set_ylim(-4.5, total_h); ax.invert_yaxis()
    
    # Couleurs par appartement
    apt_list = sorted(df_clean['Apt'].unique())
    apt_colors = {a: plt.cm.tab20(i % 20) for i, a in enumerate(apt_list)}

    y_cursor = 0
    for cfc in active_cfcs:
        h = max(2.8, cfc_info[cfc][0] * 2.0)
        ax.add_patch(patches.Rectangle((mdates.date2num(p_start), y_cursor), NB_SEMAINES*7, h, color='grey', alpha=0.03))
        ax.axhline(y_cursor, color='black', linewidth=4)
        ax.text(mdates.date2num(p_start) - 0.1, y_cursor + h/2, f"CFC {cfc}", ha='right', va='center', fontweight='bold', fontsize=35)
        
        tasks = df_zoom[df_zoom['CFC'] == cfc].sort_values('Start')
        for (idx, row), (s, e, lvl) in zip(tasks.iterrows(), cfc_info[cfc][1]):
            vis_s, vis_e = max(s, mdates.date2num(p_start)), min(e, mdates.date2num(p_end))
            y_t = y_cursor + 1.3 + (lvl * 2.0)
            ax.add_patch(patches.Rectangle((s+0.02, y_t-0.9), e-s-0.04, 1.8, facecolor=apt_colors[row['Apt']], edgecolor='black', linewidth=2.5, zorder=5))
            txt = f"APP {row['Apt']}\n" + "\n".join(textwrap.wrap(row['Nom'], width=20))
            ax.text(vis_s + (vis_e - vis_s)/2, y_t, txt, ha='center', va='center', fontsize=22, fontweight='bold', zorder=10)
        y_cursor += h

    # Headers
    months_fr = ["", "JANVIER", "FEVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOUT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DECEMBRE"]
    curr = p_start
    while curr < p_end:
        dn = mdates.date2num(curr)
        if curr.day == 1 or curr == p_start:
            ax.text(dn, -3.5, f"{months_fr[curr.month]} {curr.year}", fontsize=65, fontweight='bold', color='navy')
        if curr.weekday() == 0:
            ax.text(dn + 3.5, -2.2, f"SEMAINE {curr.isocalendar()[1]}", ha='center', fontsize=50, fontweight='bold', bbox=dict(facecolor='gold', edgecolor='black', boxstyle='round,pad=0.8'))
            ax.axvline(dn, color='black', linewidth=6)
        ax.text(dn + 0.5, -0.6, f"{['LUN','MAR','MER','JEU','VEN','SAM','DIM'][curr.weekday()]} {curr.day}", ha='center', fontsize=28, fontweight='bold')
        curr += timedelta(days=1)

    ax.set_yticks([]); ax.set_xticks([])
    output_name = f"Planning_Production_{datetime.now().strftime('%Y%m%d')}.pdf"
    plt.savefig(output_name, format='pdf')
    print(f"✅ SUCCÈS : Le fichier '{output_name}' est prêt dans l'onglet Files.")

    plt.show()
