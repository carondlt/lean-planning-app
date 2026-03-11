from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # Désactive la limite de sécurité pour les grandes images
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from datetime import timedelta, datetime, date
import textwrap
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Générateur de Planning Lean", layout="wide")

st.title("🏗️ Générateur de Planning Lean")
st.write("Chargez votre export Excel pour générer le planning visuel.")

# --- BARRE LATÉRALE (CONFIGURATION) ---
with st.sidebar:
    st.header("⚙️ Configuration")
    nb_semaines_ui = st.slider("Nombre de semaines", 1, 6, 2)
    date_debut_ui = st.date_input("Date de début", date(2026, 9, 7))
    largeur_pdf = st.select_slider("Largeur du PDF (Zoom)", options=[40, 60, 80, 100], value=80)

# --- CHARGEMENT DU FICHIER ---
uploaded_file = st.file_uploader("📁 Glissez votre fichier Excel (.xlsx) ici", type=["xlsx"])

if uploaded_file:
    try:
        # Lecture du fichier chargé
        df = pd.read_excel(uploaded_file)
        
        # --- 2. NETTOYAGE ---
        # On s'adapte aux noms de colonnes (CFC, N°appartement, Début, Fin)
        df_clean = df.dropna(subset=['CFC', 'N°appartement', 'Début', 'Fin']).copy()
        
        month_map = {
            'Janvier': 'January', 'Février': 'February', 'Mars': 'March', 'Avril': 'April', 
            'Mai': 'May', 'Juin': 'June', 'Juillet': 'July', 'Août': 'August', 
            'Septembre': 'September', 'Octobre': 'October', 'Novembre': 'November', 'Décembre': 'December'
        }

        def parse_date(d):
            if pd.isna(d): return None
            if isinstance(d, datetime): return d
            d_str = str(d)
            for fr, en in month_map.items():
                if fr in d_str: d_str = d_str.replace(fr, en); break
            return pd.to_datetime(d_str, format='%d %B %Y %H:%M', errors='coerce')

        df_clean['Start'] = df_clean['Début'].apply(parse_date)
        df_clean['End'] = df_clean['Fin'].apply(parse_date)
        df_clean = df_clean.dropna(subset=['Start', 'End'])
        
        # Formatage du numéro d'appartement
        df_clean['Apt'] = df_clean['N°appartement'].apply(
            lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x)
        )

        # --- 3. DATES (Utilisation des réglages de la sidebar) ---
        p_start = pd.to_datetime(date_debut_ui)
        p_end = p_start + timedelta(days=nb_semaines_ui * 7)
        
        # Filtre sur la période choisie
        df_zoom = df_clean[((df_clean['Start'] < p_end) & (df_clean['End'] >= p_start))].copy()
        
        if df_zoom.empty:
            st.warning(f"⚠️ Aucune tâche trouvée entre le {p_start.date()} et le {p_end.date()}. Ajustez la date à gauche !")
        else:
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
            
            # Création de la figure
            fig = plt.figure(figsize=(largeur_pdf, total_h * 1.6 + 12))
            ax = fig.add_axes([0.15, 0.1, 0.82, 0.8])
            ax.set_xlim(mdates.date2num(p_start), mdates.date2num(p_end))
            ax.set_ylim(-4.5, total_h)
            ax.invert_yaxis()
            
            # Couleurs par appartement
            apt_list = sorted(df_clean['Apt'].unique())
            apt_colors = {a: plt.cm.tab20(i % 20) for i, a in enumerate(apt_list)}

            y_cursor = 0
            for cfc in active_cfcs:
                h = max(2.8, cfc_info[cfc][0] * 2.0)
                ax.add_patch(patches.Rectangle((mdates.date2num(p_start), y_cursor), nb_semaines_ui*7, h, color='grey', alpha=0.03))
                ax.axhline(y_cursor, color='black', linewidth=4)
                ax.text(mdates.date2num(p_start) - 0.1, y_cursor + h/2, f"CFC {cfc}", ha='right', va='center', fontweight='bold', fontsize=35)
                
                tasks = df_zoom[df_zoom['CFC'] == cfc].sort_values('Start')
                for (idx, row), (s, e, lvl) in zip(tasks.iterrows(), cfc_info[cfc][1]):
                    vis_s, vis_e = max(s, mdates.date2num(p_start)), min(e, mdates.date2num(p_end))
                    y_t = y_cursor + 1.3 + (lvl * 2.0)
                    ax.add_patch(patches.Rectangle((s+0.02, y_t-0.9), e-s-0.04, 1.8, facecolor=apt_colors[row['Apt']], edgecolor='black', linewidth=2.5, zorder=5))
                    
                    # Gestion du texte (Nom de la tâche)
                    nom_tache = str(row['Nom']) if 'Nom' in row else "Tâche"
                    txt = f"APP {row['Apt']}\n" + "\n".join(textwrap.wrap(nom_tache, width=20))
                    ax.text(vis_s + (vis_e - vis_s)/2, y_t, txt, ha='center', va='center', fontsize=22, fontweight='bold', zorder=10)
                y_cursor += h

            # En-têtes temporels (Headers)
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
            
            # --- AFFICHAGE DANS L'APPLI ---
            st.pyplot(fig)

            # --- PRÉPARATION DU TÉLÉCHARGEMENT PDF ---
            buf = io.BytesIO()
            plt.savefig(buf, format='pdf', bbox_inches='tight')
            st.download_button(
                label="📥 Télécharger le Planning en PDF",
                data=buf.getvalue(),
                file_name=f"Planning_Athenee_{date_debut_ui}.pdf",
                mime="application/pdf"
            )

    except Exception as e:
        st.error(f"💥 Erreur lors de l'analyse du fichier : {e}")
        st.info("Vérifiez que votre fichier Excel contient bien les colonnes : CFC, N°appartement, Début, Fin, Nom")
voici mon code app.py pourquoi ca ne fonctionne pas
