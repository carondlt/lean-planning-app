from PIL import Image
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from datetime import timedelta, datetime, date
import textwrap
import io

# Securite pour les grandes images
Image.MAX_IMAGE_PIXELS = None

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Générateur de Planning Lean", layout="wide")

st.title("🏗️ Générateur de Planning Lean")
st.write("Compatible MS Project / Excel (Dates 2026-2027)")

# --- BARRE LATERALE ---
with st.sidebar:
    st.header("⚙️ Configuration")
    nb_semaines_ui = st.slider("Nombre de semaines a afficher", 1, 12, 4)
    # Date par defaut reglee sur une zone active de ton fichier
    date_debut_ui = st.date_input("Date de debut", date(2026, 5, 4))
    largeur_pdf = st.select_slider("Largeur du rendu (Zoom)", options=[20, 40, 60, 80], value=40)
    st.info("💡 Change la date ci-dessus pour naviguer dans le planning (ex: Mai 2027).")

# --- CHARGEMENT DU FICHIER ---
uploaded_file = st.file_uploader("📁 Glissez votre fichier Excel (.xlsx) ici", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # --- DETECTION INTELLIGENTE DES COLONNES ---
        df.columns = [str(c).strip() for c in df.columns]
        cols = {c.lower().replace('°', '').replace(' ', ''): c for c in df.columns}
        
        c_cfc = cols.get('cfc')
        c_apt = cols.get('nappartement') or cols.get('appartement') or cols.get('zone')
        c_debut = cols.get('debut') or cols.get('début') or cols.get('start')
        c_fin = cols.get('fin') or cols.get('end')
        c_nom = cols.get('nom') or cols.get('tâche') or cols.get('nomdelatâche')

        if not all([c_cfc, c_apt, c_debut, c_fin]):
            st.error(f"❌ Colonnes manquantes. L'Excel doit avoir : CFC, N°appartement, Début, Fin.")
            st.write("Colonnes trouvees :", list(df.columns))
        else:
            # --- NETTOYEUR DE DATES SUISSES ---
            def parse_date_robuste(d):
                if pd.isna(d): return None
                if isinstance(d, datetime): return d
                d_str = str(d).lower().strip()
                # On vire les jours de la semaine et on remplace les points par des slashs
                for day in ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim']:
                    d_str = d_str.replace(day, '')
                d_str = d_str.replace('.', '/').replace(' ', '').strip('/')
                
                # On tente les formats les plus courants
                for fmt in ('%d/%m/%y', '%d/%m/%Y', '%Y-%m-%d'):
                    try:
                        return pd.to_datetime(d_str, format=fmt)
                    except:
                        continue
                return pd.to_datetime(d_str, dayfirst=True, errors='coerce')

            df_clean = df.dropna(subset=[c_cfc, c_apt, c_debut, c_fin]).copy()
            df_clean['Start'] = df_clean[c_debut].apply(parse_date_robuste)
            df_clean['End'] = df_clean[c_fin].apply(parse_date_robuste)
            df_clean = df_clean.dropna(subset=['Start', 'End'])
            
            # Nettoyage numero appartement
            df_clean['Apt'] = df_clean[c_apt].apply(lambda x: str(x).split('.')[0] if '.' in str(x) else str(x))

            # --- FILTRE TEMPOREL ---
            p_start = pd.to_datetime(date_debut_ui)
            p_end = p_start + timedelta(days=nb_semaines_ui * 7)
            df_zoom = df_clean[((df_clean['Start'] < p_end) & (df_clean['End'] >= p_start))].copy()
            
            if df_zoom.empty:
                st.warning(f"📅 Aucune tâche trouvée pour cette période.")
                st.info(f"Ton fichier contient des données du {df_clean['Start'].min().date()} au {df_clean['End'].max().date()}.")
            else:
                # --- DESSIN ---
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

                total_h = sum([max(2.8, h * 2.2) for h, _ in cfc_info.values()])
                fig = plt.figure(figsize=(largeur_pdf, total_h * 1.5 + 10))
                ax = fig.add_axes([0.15, 0.1, 0.82, 0.8])
                ax.set_xlim(mdates.date2num(p_start), mdates.date2num(p_end))
                ax.set_ylim(-4, total_h)
                ax.invert_yaxis()
                
                apt_list = sorted(df_clean['Apt'].unique())
                colors = {a: plt.cm.tab20(i % 20) for i, a in enumerate(apt_list)}

                y_cursor = 0
                for cfc in active_cfcs:
                    h = max(2.8, cfc_info[cfc][0] * 2.2)
                    ax.add_patch(patches.Rectangle((mdates.date2num(p_start), y_cursor), nb_semaines_ui*7, h, color='grey', alpha=0.0
