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
st.write("Si vous voyez ce message, l'appli fonctionne !")

# --- BARRE LATERALE ---
with st.sidebar:
    st.header("⚙️ Configuration")
    nb_semaines = st.slider("Nombre de semaines", 1, 6, 2)
    date_debut = st.date_input("Date de debut", date(2026, 5, 4))

uploaded_file = st.file_uploader("📁 Glissez votre fichier Excel (.xlsx) ici", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # --- NETTOYAGE ---
        # On s'assure que les colonnes existent exactement comme dans ton Excel
        df_clean = df.dropna(subset=['CFC', 'N°appartement', 'Début', 'Fin']).copy()
        
        def parse_date(d):
            if pd.isna(d): return None
            if isinstance(d, datetime): return d
            # Tentative de lecture simple
            return pd.to_datetime(str(d), dayfirst=True, errors='coerce')

        df_clean['Start'] = df_clean['Début'].apply(parse_date)
        df_clean['End'] = df_clean['Fin'].apply(parse_date)
        df_clean = df_clean.dropna(subset=['Start', 'End'])
        
        df_clean['Apt'] = df_clean['N°appartement'].apply(lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x))

        # --- DATES ---
        p_start = pd.to_datetime(date_debut)
        p_end = p_start + timedelta(days=nb_semaines * 7)
        
        df_zoom = df_clean[((df_clean['Start'] < p_end) & (df_clean['End'] >= p_start))].copy()

        if df_zoom.empty:
            st.warning(f"📅 Rien a afficher pour cette date ({p_start.date()}). Changez la date a gauche !")
        else:
            active_cfcs = sorted(df_zoom['CFC'].unique(), key=lambda x: str(x))

            # --- DESSIN ---
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
            fig = plt.figure(figsize=(20, total_h * 1.5 + 10))
            ax = fig.add_axes([0.15, 0.1, 0.82, 0.8])
            ax.set_xlim(mdates.date2num(p_start), mdates.date2num(p_end))
            ax.set_ylim(-4, total_h)
            ax.invert_yaxis()
            
            apt_colors = {a: plt.cm.tab20(i % 20) for i, a in enumerate(sorted(df_clean['Apt'].unique()))}

            y_cursor = 0
            for cfc in active_cfcs:
                h = max(2.8, cfc_info[cfc][0] * 2.0)
                ax.add_patch(patches.Rectangle((mdates.date2num(p_start), y_cursor), nb_semaines*7, h, color='grey', alpha=0.03))
                ax.axhline(y_cursor, color='black', linewidth=2)
                ax.text(mdates.date2num(p_start) - 0.1, y_cursor + h/2, f"CFC {cfc}", ha='right', va='center', fontweight='bold', fontsize=15)
                
                tasks = df_zoom[df_zoom['CFC'] == cfc].sort_values('Start')
                for (idx, row), (s, e, lvl) in zip(tasks.iterrows(), cfc_info[cfc][1]):
                    y_t = y_cursor + 1.2 + (lvl * 2.0)
                    ax.add_patch(patches.Rectangle((s, y_t-0.9), e-s, 1.8, facecolor=apt_colors[row['Apt']], edgecolor='black'))
                    txt = f"APP {row['Apt']}\n{row['Nom']}"
                    ax.text(s + (e-s)/2, y_t, txt, ha='center', va='center', fontsize=10, fontweight='bold')
                y_cursor += h

            st.pyplot(fig)

            buf = io.BytesIO()
            plt.savefig(buf, format='pdf', bbox_inches='tight')
            st.download_button("📥 Telecharger PDF", buf.getvalue(), "Planning.pdf", "application/pdf")

    except Exception as e:
        st.error(f"Erreur : {e}")
