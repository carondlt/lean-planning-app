import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from datetime import timedelta, datetime, date
import textwrap
import io
import re
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

st.set_page_config(page_title="Générateur Lean", layout="wide")
st.title("🗓️ Planning Lean - Vue Emploi du Temps")

with st.sidebar:
    st.header("⚙️ Configuration")
    nb_semaines = st.slider("Nombre de semaines", 1, 6, 2)
    date_debut_ui = st.date_input("Date de début", date(2026, 6, 1))
    
    st.markdown("---")
    st.header("🔎 Réglages Visuels (Zoom)")
    zoom_largeur = st.slider("Étirer le planning (Largeur)", 20, 80, 35)
    # NOUVEAU REGLAGE POUR L'IMPRESSION A3
    zoom_hauteur = st.slider("Hauteur du planning (Compacter)", 0.5, 3.0, 1.5, step=0.1)
    taille_texte = st.slider("Taille du texte", 6, 16, 10)

uploaded_file = st.file_uploader("📁 Glissez votre fichier Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)

        df.columns = [str(c).strip() for c in df.columns]
        cols_brutes = {str(c).lower().strip().replace(' ', '').replace('°', ''): c for c in df.columns}

        c_cfc = cols_brutes.get('cfc')
        c_apt = cols_brutes.get('nappartement') or cols_brutes.get('appartement')
        c_debut = cols_brutes.get('début') or cols_brutes.get('debut')
        c_fin = cols_brutes.get('fin') or cols_brutes.get('end')
        c_nom = cols_brutes.get('nom') or cols_brutes.get('tâche')

        if not all([c_cfc, c_apt, c_debut, c_fin]):
            st.error("❌ Colonnes introuvables. Vérifiez le fichier.")
        else:
            def parse_french_date(d):
                if pd.isna(d): return pd.NaT
                if isinstance(d, (datetime, pd.Timestamp, date)): return pd.to_datetime(d)

                s = str(d).lower().strip()
                mois_fr = {
                    'janvier': '01', 'février': '02', 'fevrier': '02', 'mars': '03',
                    'avril': '04', 'mai': '05', 'juin': '06', 'juillet': '07',
                    'août': '08', 'aout': '08', 'septembre': '09', 'octobre': '10',
                    'novembre': '11', 'décembre': '12', 'decembre': '12'
                }
                for fr, num in mois_fr.items():
                    s = s.replace(fr, num)

                match = re.search(r'(\d{1,2})[\s\./-]+(\d{1,2})[\s\./-]+(\d{4})', s)
                if match:
                    clean_date = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                    return pd.to_datetime(clean_date, format='%d/%m/%Y', errors='coerce')
                return pd.NaT

            df_clean = df.dropna(subset=[c_cfc, c_apt, c_debut, c_fin]).copy()
            df_clean['Start_Dt'] = df_clean[c_debut].apply(parse_french_date)
            df_clean['End_Dt'] = df_clean[c_fin].apply(parse_french_date)

            df_clean = df_clean.dropna(subset=['Start_Dt', 'End_Dt'])
            df_clean['Apt_Txt'] = df_clean[c_apt].apply(lambda x: str(x).split('.')[0] if '.' in str(x) else str(x))

            p_start = pd.to_datetime(date_debut_ui)
            p_end = p_start + timedelta(days=nb_semaines * 7)
            df_zoom = df_clean[(df_clean['Start_Dt'] < p_end) & (df_clean['End_Dt'] >= p_start)].copy()

            if df_zoom.empty:
                st.warning(f"📅 Rien de prévu entre le {p_start.date()} et le {p_end.date()}.")
            else:
                active_cfcs = sorted(df_zoom[c_cfc].unique(), key=lambda x: str(x))
                cfc_info = {}
                
                for cfc in active_cfcs:
                    tasks = df_zoom[df_zoom[c_cfc] == cfc].sort_values('Start_Dt')
                    placed, max_lvl = [], 0
                    for _, row in tasks.iterrows():
                        s = mdates.date2num(row['Start_Dt'])
                        e = mdates.date2num(row['End_Dt']) + 1 
                        
                        lvl = 0
                        marge_texte = 0.8 
                        while any(not (e + marge_texte <= ts or s >= te) and tl == lvl for ts, te, tl in placed): 
                            lvl += 1
                        
                        placed.append((s, e, lvl))
                        max_lvl = max(max_lvl, lvl)
                    cfc_info[cfc] = (max_lvl + 1, placed)

                total_h = sum([max(2.8, h * 2.2) for h, _ in cfc_info.values()])
                
                # INTEGRATION DU ZOOM HAUTEUR ICI
                fig = plt.figure(figsize=(zoom_largeur, total_h * zoom_hauteur + 5), facecolor='white')
                ax = fig.add_axes([0.15, 0.1, 0.82, 0.8], facecolor='white')
                ax.set_xlim(mdates.date2num(p_start), mdates.date2num(p_end))
                ax.set_ylim(-4, total_h)
                ax.invert_yaxis()
                
                for spine in ax.spines.values():
                    spine.set_visible(False)

                chic_palette = ['#EAECEE', '#D6DBDF', '#D5C4A1', '#BCAAA4', '#B0BEC5', '#A9CCE3', '#A2D9CE', '#F9E79F', '#F5CBA7', '#E8DAEF']
                apt_list = sorted(df_clean['Apt_Txt'].unique())
                apt_colors = {a: chic_palette[i % len(chic_palette)] for i, a in enumerate(apt_list)}

                curr_grid = p_start
                while curr_grid <= p_end:
                    ax.axvline(mdates.date2num(curr_grid), color='#EEEEEE', linewidth=1.5, zorder=0)
                    curr_grid += timedelta(days=1)

                y_cursor = 0
                for cfc in active_cfcs:
                    h = max(2.8, cfc_info[cfc][0] * 2.2)
                    
                    if active_cfcs.index(cfc) % 2 == 0:
                        ax.add_patch(patches.Rectangle((mdates.date2num(p_start), y_cursor), nb_semaines*7, h, color='#F8F9FA', zorder=1))
                    
                    ax.axhline(y_cursor, color='#BDC3C7', linewidth=1)
                    ax.text(mdates.date2num(p_start) - 0.2, y_cursor + h/2, f"CFC {cfc}", ha='right', va='center', fontweight='bold', fontsize=16, color='#2C3E50')

                    tasks = df_zoom[df_zoom[c_cfc] == cfc].sort_values('Start_Dt')
                    for (_, row), (start_num, end_num, lvl) in zip(tasks.iterrows(), cfc_info[cfc][1]):
                        y_t = y_cursor + 1.2 + (lvl * 2.2)
                        
                        rect_s = max(start_num, mdates.date2num(p_start))
                        rect_e = min(end_num, mdates.date2num(p_end))
                        
                        ax.add_patch(patches.Rectangle((start_num, y_t-1.0), end_num-start_num, 2.0, facecolor=apt_colors[row['Apt_Txt']], edgecolor='white', linewidth=2, zorder=5))

                        task_name = str(row[c_nom]) if c_nom and pd.notna(row[c_nom]) else "Tâche"
                        
                        largeur_wrap = int(zoom_largeur / 1.5) 
                        txt_label = f"APP {row['Apt_Txt']}\n" + "\n".join(textwrap.wrap(task_name, width=largeur_wrap))
                        
                        ax.text(rect_s + (rect_e-rect_s)/2, y_t, txt_label, ha='center', va='center', fontsize=taille_texte, fontweight='bold', color='#1C2833', zorder=10)
                    y_cursor += h

                # --- NOUVEAUX EN-TÊTES TEMPORELS ---
                jours_fr = ['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM', 'DIM']
                mois_fr = ['JANVIER', 'FÉVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN', 'JUILLET', 'AOÛT', 'SEPTEMBRE', 'OCTOBRE', 'NOVEMBRE', 'DÉCEMBRE']
                
                curr = p_start
                while curr < p_end:
                    dn = mdates.date2num(curr)
                    
                    # 1. Le Mois (s'affiche au début et à chaque 1er du mois)
                    if curr.day == 1 or curr == p_start:
                        ax.text(dn, -3.2, f"{mois_fr[curr.month - 1]} {curr.year}", ha='left', fontsize=20, fontweight='bold', color='#2C3E50')
                    
                    # 2. La Semaine (le lundi)
                    if curr.weekday() == 0:
                        ax.text(dn+3.5, -1.8, f"SEM {curr.isocalendar()[1]}", ha='center', fontsize=16, fontweight='bold', color='white', bbox=dict(facecolor='#1C2833', edgecolor='none', pad=4, boxstyle='round,pad=0.3'))
                        ax.axvline(dn, color='#1C2833', linewidth=2, zorder=2)
                    
                    # 3. Le Jour de la semaine + Numéro
                    color_jour = '#E74C3C' if curr.weekday() >= 5 else '#7F8C8D' # Weekends en rouge, semaine en gris
                    jour_txt = f"{jours_fr[curr.weekday()]}\n{curr.day}"
                    ax.text(dn+0.5, -0.6, jour_txt, ha='center', va='center', fontsize=11, fontweight='bold', color=color_jour)
                    
                    curr += timedelta(days=1)

                ax.set_yticks([]); ax.set_xticks([])
                st.pyplot(fig)

                buf = io.BytesIO()
                plt.savefig(buf, format='pdf', bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
                st.download_button("📥 Télécharger PDF", buf.getvalue(), f"Planning_Lean_Athenee.pdf", "application/pdf")

    except Exception as e:
        st.error(f"💥 Erreur inattendue : {e}")
