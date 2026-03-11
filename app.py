import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from datetime import timedelta, datetime, date
import textwrap
import io
from PIL import Image

# Désactive la limite pour les images géantes
Image.MAX_IMAGE_PIXELS = None 

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Générateur de Planning Lean", layout="wide")

st.title("🏗️ Générateur de Planning Lean")
st.write("Chargez votre export Excel pour générer le planning visuel.")

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("⚙️ Configuration")
    nb_semaines_ui = st.slider("Nombre de semaines", 1, 8, 2)
    # On met une date par défaut plus proche de ton fichier (Mai 2026)
    date_debut_ui = st.date_input("Date de début", date(2026, 5, 11))
    largeur_pdf = st.select_slider("Largeur du PDF (Zoom)", options=[20, 40, 60, 80], value=40)

uploaded_file = st.file_uploader("📁 Glissez votre fichier Excel (.xlsx) ici", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # --- DÉTECTION INTELLIGENTE DES COLONNES ---
        # On nettoie les noms de colonnes pour ignorer les espaces et les majuscules
        df.columns = [str(c).strip() for c in df.columns]
        cols = {c.lower().replace('°', ''): c for c in df.columns}
        
        c_cfc = cols.get('cfc')
        c_apt = cols.get('nappartement') or cols.get('appartement') or cols.get('zone')
        c_debut = cols.get('début') or cols.get('debut') or cols.get('start')
        c_fin = cols.get('fin') or cols.get('end')
        c_nom = cols.get('nom') or cols.get('tâche') or cols.get('nom de la tâche')

        if not all([c_cfc, c_apt, c_debut, c_fin]):
            st.error(f"❌ Colonnes manquantes. Trouvées : {list(df.columns)}")
        else:
            # --- NETTOYAGE DES DATES SUISSES ---
            def parse_date_suisse(d):
                if pd.isna(d): return None
                if isinstance(d, datetime): return d
                d_str = str(d).lower().strip()
                d_str = d_str.replace('.', '/') # Transforme 01.06.26 en 01/06/26
                # Supprime les jours (lun, mar...)
                for day in ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim']:
                    d_str = d_str.replace(day, '')
                return pd.to_datetime(d_str, dayfirst=True, errors='coerce')

            df_clean = df.dropna(subset=[c_cfc, c_apt, c_debut, c_fin]).copy()
            df_clean['Start'] = df_clean[c_debut].apply(parse_date_suisse)
            df_clean['End'] = df_clean[c_fin].apply(parse_date_suisse)
            df_clean = df_clean.dropna(subset=['Start', 'End'])
            
            df_clean['Apt'] = df_clean[c_apt].apply(lambda x: str(x).split('.')[0] if '.' in str(x) else str(x))

            # --- FILTRE TEMPOREL ---
            p_start = pd.to_datetime(date_debut_ui)
            p_end = p_start + timedelta(days=nb_semaines_ui * 7)
            df_zoom = df_clean[((df_clean['Start'] < p_end) & (df_clean['End'] >= p_start))].copy()
            
            if df_zoom.empty:
                st.warning(f"📅 Rien à afficher entre le {p_start.date()} et le {p_end.date()}.")
                st.info("Astuce : Votre planning semble avoir beaucoup d'activité entre le 11 et le 25 mai 2026.")
            else:
                # --- DESSIN (MATPLOTLIB) ---
                active_cfcs = sorted(df_zoom[c_cfc].unique(), key=lambda x: str(x))
                cfc_info = {}
                for cfc in active_cfcs:
                    tasks = df_zoom[df_zoom[c_cfc] == cfc].sort_values('Start')
                    placed, max_lvl = [], 0
                    for _, row in tasks.iterrows():
                        s, e = mdates.date2num(row['Start']), mdates.date2num(row['End'])
                        lvl = 0
                        while any(not (e <= ts or s >= te) and tl == lvl for ts, te, tl in placed): lvl += 1
                        placed.append((s, e, lvl))
                        max_lvl = max(max_lvl, lvl)
                    cfc_info[cfc] = (max_lvl + 1, placed)

                total_h = sum([max(2.8, h * 2.0) for h, _ in cfc_info.values()])
                fig = plt.figure(figsize=(largeur_pdf, total_h * 1.4 + 10))
                ax = fig.add_axes([0.15, 0.1, 0.82, 0.8])
                ax.set_xlim(mdates.date2num(p_start), mdates.date2num(p_end))
                ax.set_ylim(-4, total_h)
                ax.invert_yaxis()
                
                apt_list = sorted(df_clean['Apt'].unique())
                colors = {a: plt.cm.tab20(i % 20) for i, a in enumerate(apt_list)}

                y_cursor = 0
                for cfc in active_cfcs:
                    h = max(2.8, cfc_info[cfc][0] * 2.0)
                    ax.add_patch(patches.Rectangle((mdates.date2num(p_start), y_cursor), nb_semaines_ui*7, h, color='grey', alpha=0.03))
                    ax.axhline(y_cursor, color='black', linewidth=3)
                    ax.text(mdates.date2num(p_start)-0.2, y_cursor+h/2, f"CFC {cfc}", ha='right', va='center', fontweight='bold', fontsize=30)
                    
                    tasks = df_zoom[df_zoom[c_cfc] == cfc].sort_values('Start')
                    for (_, row), (s, e, lvl) in zip(tasks.iterrows(), cfc_info[cfc][1]):
                        y_t = y_cursor + 1.2 + (lvl * 2.0)
                        rect_s = max(s, mdates.date2num(p_start))
                        rect_e = min(e, mdates.date2num(p_end))
                        ax.add_patch(patches.Rectangle((s, y_t-0.9), e-s, 1.8, facecolor=colors[row['Apt']], edgecolor='black', linewidth=1.5, zorder=5))
                        txt = f"APP {row['Apt']}\n" + "\n".join(textwrap.wrap(str(row[c_nom]), width=15))
                        ax.text(rect_s + (rect_e-rect_s)/2, y_t, txt, ha='center', va='center', fontsize=18, fontweight='bold', zorder=10)
                    y_cursor += h

                # Headers Temporels
                curr = p_start
                while curr < p_end:
                    dn = mdates.date2num(curr)
                    if curr.weekday() == 0:
                        ax.text(dn+3.5, -2, f"SEMAINE {curr.isocalendar()[1]}", ha='center', fontsize=40, fontweight='bold', bbox=dict(facecolor='gold', pad=5))
                        ax.axvline(dn, color='black', linewidth=4)
                    ax.text(dn+0.5, -0.5, f"{['LUN','MAR','MER','JEU','VEN','SAM','DIM'][curr.weekday()]} {curr.day}", ha='center', fontsize=22)
                    curr += timedelta(days=1)

                ax.set_yticks([]); ax.set_xticks([])
                st.pyplot(fig, dpi=72)

                buf = io.BytesIO()
                plt.savefig(buf, format='pdf', bbox_inches='tight')
                st.download_button(label="📥 Télécharger le PDF", data=buf.getvalue(), file_name="Planning.pdf", mime="application/pdf")

    except Exception as e:
        st.error(f"💥 Erreur : {e}")
