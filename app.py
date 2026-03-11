import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from datetime import timedelta, datetime, date
import textwrap
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Générateur de Planning Lean", layout="wide")
st.title("🏗️ Générateur de Planning Lean")

with st.sidebar:
    st.header("⚙️ Configuration")
    nb_semaines = st.sidebar.slider("Nombre de semaines", 1, 12, 4)
    date_debut_ui = st.sidebar.date_input("Date de début", date(2026, 5, 4))

uploaded_file = st.file_uploader("📁 Glissez votre fichier Excel (.xlsx) ici", type=["xlsx"])

if uploaded_file:
    try:
        # 1. Lecture souple de l'Excel
        df = pd.read_excel(uploaded_file)
        
        # Nettoyage automatique des noms de colonnes (enlève espaces et majuscules)
        df.columns = [str(c).strip() for c in df.columns]
        cols_brutes = {c.lower().replace(' ', '').replace('°', ''): c for c in df.columns}
        
        # Mappage intelligent des colonnes
        c_cfc = cols_brutes.get('cfc')
        c_apt = cols_brutes.get('nappartement') or cols_brutes.get('appartement') or cols_brutes.get('zone')
        c_debut = cols_brutes.get('debut') or cols_brutes.get('début') or cols_brutes.get('start')
        c_fin = cols_brutes.get('fin') or cols_brutes.get('end')
        c_nom = cols_brutes.get('nom') or cols_brutes.get('tâche') or cols_brutes.get('task')

        if not all([c_cfc, c_apt, c_debut, c_fin]):
            st.error(f"❌ Colonnes manquantes ! J'ai besoin de : CFC, N°appartement, Début, Fin.")
            st.info(f"Colonnes trouvées dans ton fichier : {list(df.columns)}")
        else:
            # 2. Nettoyage des dates "Suisses" (01.06.27)
            def clean_date(d):
                if pd.isna(d): return None
                if isinstance(d, datetime): return d
                s = str(d).lower()
                for day in ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim']:
                    s = s.replace(day, '')
                s = s.replace('.', '/').replace(' ', '').strip('/')
                return pd.to_datetime(s, dayfirst=True, errors='coerce')

            df_clean = df.dropna(subset=[c_cfc, c_apt, c_debut, c_fin]).copy()
            df_clean['Start_Dt'] = df_clean[c_debut].apply(clean_date)
            df_clean['End_Dt'] = df_clean[c_fin].apply(clean_date)
            df_clean = df_clean.dropna(subset=['Start_Dt', 'End_Dt'])
            
            # Formatage appartement
            df_clean['Apt_Txt'] = df_clean[c_apt].apply(lambda x: str(x).split('.')[0] if '.' in str(x) else str(x))

            # 3. Filtrage Temporel
            p_start = pd.to_datetime(date_debut_ui)
            p_end = p_start + timedelta(days=nb_semaines * 7)
            df_zoom = df_clean[(df_clean['Start_Dt'] < p_end) & (df_clean['End_Dt'] >= p_start)].copy()

            if df_zoom.empty:
                st.warning(f"📅 Rien à afficher entre le {p_start.date()} et le {p_end.date()}.")
                st.info(f"Dates dans ton fichier : du {df_clean['Start_Dt'].min().date()} au {df_clean['End_Dt'].max().date()}")
            else:
                # 4. Calcul du Stacking (hauteur des barres)
                active_cfcs = sorted(df_zoom[c_cfc].unique(), key=lambda x: str(x))
                cfc_info = {}
                for cfc in active_cfcs:
                    tasks = df_zoom[df_zoom[c_cfc] == cfc].sort_values('Start_Dt')
                    placed, max_lvl = [], 0
                    for _, row in tasks.iterrows():
                        s, e = mdates.date2num(row['Start_Dt']), mdates.date2num(row['End_Dt'])
                        lvl = 0
                        while any(not (e <= ts or s >= te) and tl == lvl for ts, te, tl in placed): lvl += 1
                        placed.append((s, e, lvl))
                        max_lvl = max(max_lvl, lvl)
                    cfc_info[cfc] = (max_lvl + 1, placed)

                # 5. Dessin
                total_h = sum([max(2.8, h * 2.2) for h, _ in cfc_info.values()])
                fig = plt.figure(figsize=(25, total_h * 1.5 + 10))
                ax = fig.add_axes([0.15, 0.1, 0.82, 0.8])
                ax.set_xlim(mdates.date2num(p_start), mdates.date2num(p_end))
                ax.set_ylim(-4, total_h)
                ax.invert_yaxis()
                
                apt_colors = {a: plt.cm.tab20(i % 20) for i, a in enumerate(sorted(df_clean['Apt_Txt'].unique()))}

                y_cursor = 0
                for cfc in active_cfcs:
                    h = max(2.8, cfc_info[cfc][0] * 2.2)
                    ax.add_patch(patches.Rectangle((mdates.date2num(p_start), y_cursor), nb_semaines*7, h, color='grey', alpha=0.03))
                    ax.axhline(y_cursor, color='black', linewidth=3)
                    ax.text(mdates.date2num(p_start) - 0.2, y_cursor + h/2, f"CFC {cfc}", ha='right', va='center', fontweight='bold', fontsize=25)
                    
                    tasks = df_zoom[df_zoom[c_cfc] == cfc].sort_values('Start_Dt')
                    for (_, row), (s, e, lvl) in zip(tasks.iterrows(), cfc_info[cfc][1]):
                        y_t = y_cursor + 1.2 + (lvl * 2.2)
                        rect_s = max(s, mdates.date2num(p_start))
                        rect_e = min(e, mdates.date2num(p_end))
                        ax.add_patch(patches.Rectangle((s, y_t-1.0), e-s, 2.0, facecolor=apt_colors[row['Apt_Txt']], edgecolor='black', linewidth=1))
                        
                        txt_label = f"APP {row['Apt_Txt']}\n" + "\n".join(textwrap.wrap(str(row[c_nom]), width=15))
                        ax.text(rect_s + (rect_e-rect_s)/2, y_t, txt_label, ha='center', va='center', fontsize=16, fontweight='bold')
                    y_cursor += h

                # En-têtes (Semaines)
                curr = p_start
                while curr < p_end:
                    dn = mdates.date2num(curr)
                    if curr.weekday() == 0:
                        ax.text(dn+3.5, -2, f"SEMAINE {curr.isocalendar()[1]}", ha='center', fontsize=40, fontweight='bold', bbox=dict(facecolor='gold', pad=5))
                        ax.axvline(dn, color='black', linewidth=3)
                    ax.text(dn+0.5, -0.5, f"{curr.day}", ha='center', fontsize=20)
                    curr += timedelta(days=1)

                ax.set_yticks([]); ax.set_xticks([])
                st.pyplot(fig)

                # PDF
                buf = io.BytesIO()
                plt.savefig(buf, format='pdf', bbox_inches='tight')
                st.download_button("📥 Télécharger PDF", buf.getvalue(), f"Lean_Planning_{date_debut_ui}.pdf", "application/pdf")

    except Exception as e:
        st.error(f"💥 Erreur technique : {e}")
