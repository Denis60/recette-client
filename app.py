import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

# --- NOUVEAUTÉ : Initialisation de la mémoire pour conserver les frappes entre les tableaux ---
if 'sauvegardes' not in st.session_state:
    st.session_state['sauvegardes'] = {}

uploaded_files = st.file_uploader("Chargez vos fichiers CSV ici", type=['csv'], accept_multiple_files=True)

def process_csv(file):
    content = file.getvalue().decode("utf-8-sig", errors="replace")
    content = content.replace("source: ", "").replace("value: ", "").replace("unit: ", "")
    lines = content.split('\n')
    
    tables = {}
    current_title = None
    current_data = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if "<<" in line and ">>" in line:
            if current_title and current_data:
                tables[current_title] = current_data
            current_title = line.split(">>")[0].replace("<<", "").strip()
            current_data = []
        else:
            if current_title is not None:
                current_data.append(line)
                
    if current_title and current_data:
        tables[current_title] = current_data
        
    return tables

def get_type_number(title):
    match = re.search(r'Type\s+(\d+)', title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 9999

# Fonction pour préparer un tableau brut avec les nouvelles colonnes
def preparer_tableau(csv_string):
    df = pd.read_csv(io.StringIO(csv_string), sep=";", index_col=False)
    df = df.fillna("")
    df = df.astype(str)
    df = df.replace(r'^\s*CCTP\s*$', '', regex=True)
    
    colonnes_commentaires = []
    if len(df.columns) >= 1:
        colonnes = list(df.columns)
        if 'Unnamed' in str(colonnes[0]) or colonnes[0] == '':
            colonnes[0] = "Caractéristique"
        df.columns = colonnes
        
        nouvel_ordre = [df.columns[0]]
        
        for col in df.columns[1:]:
            nouvel_ordre.append(col)
            valeur_catalogue = str(df[col].iloc[0]).strip()
            is_besoin = (col == 'Besoin')
            is_prop_valide = col.startswith('Proposition') and valeur_catalogue != "" and valeur_catalogue.lower() != "nan"
            
            if is_besoin or is_prop_valide:
                col_ekla = f"Eklalight ({col})"
                col_memo = f"Memorandum ({col})"
                
                if col_ekla not in df.columns: df[col_ekla] = "" 
                if col_memo not in df.columns: df[col_memo] = "" 
                
                nouvel_ordre.extend([col_ekla, col_memo])
                colonnes_commentaires.extend([col_ekla, col_memo])
        
        df = df[nouvel_ordre]
        df = df.set_index(df.columns[0])
        
    return df, colonnes_commentaires

if uploaded_files:
    noms_fichiers = [f.name for f in uploaded_files]
    fichier_selectionne = st.selectbox("1️⃣ Sélectionnez un fichier :", noms_fichiers)
    
    fichier_actif = next(f for f in uploaded_files if f.name == fichier_selectionne)
    tables_dict = process_csv(fichier_actif)
    
    if tables_dict:
        noms_tableaux = sorted(list(tables_dict.keys()), key=get_type_number)
        
        # --- NOUVEAUTÉ : Génération du Classeur Excel global ---
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            for nom_tab in noms_tableaux:
                cle_sauvegarde = f"{fichier_selectionne}_{nom_tab}"
                
                # Si on a modifié ce tableau, on prend la version modifiée. Sinon, la version brute.
                if cle_sauvegarde in st.session_state['sauvegardes']:
                    df_export = st.session_state['sauvegardes'][cle_sauvegarde]
                else:
                    csv_str = "\n".join(tables_dict[nom_tab])
                    df_export, _ = preparer_tableau(csv_str)
                
                # Nettoyage du nom de l'onglet (Excel limite à 31 caractères et interdit certains symboles)
                nom_onglet = str(nom_tab)[:31]
                nom_onglet = re.sub(r'[\\*?:/\[\]]', '', nom_onglet)
                df_export.to_excel(writer, sheet_name=nom_onglet)
        
        donnees_excel = output_excel.getvalue()
        
        # Le bouton de téléchargement est toujours visible en haut
        st.download_button(
            label="📥 Télécharger le travail en Excel (Classeur complet)",
            data=donnees_excel,
            file_name=f"Recette_{fichier_selectionne.replace('.csv', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown("---")
        
        selection = st.selectbox("2️⃣ Sélectionnez un luminaire à recetter :", noms_tableaux)
        
        if selection:
            cle_active = f"{fichier_selectionne}_{selection}"
            
            # On charge le tableau depuis la mémoire, ou on le crée s'il n'a pas encore été ouvert
            if cle_active not in st.session_state['sauvegardes']:
                csv_string = "\n".join(tables_dict[selection])
                df_initial, cols_comm = preparer_tableau(csv_string)
                st.session_state['sauvegardes'][cle_active] = df_initial
                st.session_state[f"cols_{cle_active}"] = cols_comm
            
            df = st.session_state['sauvegardes'][cle_active]
            colonnes_commentaires = st.session_state[f"cols_{cle_active}"]
            
            def colorier_si_texte(val):
                if str(val).strip() != "":
                    return 'background-color: #FFD580; color: black;'
                return 'background-color: #FAFAFA;'
            
            try:
                df_style = df.style.map(colorier_si_texte, subset=colonnes_commentaires)
            except AttributeError:
                df_style = df.style.applymap(colorier_si_texte, subset=colonnes_commentaires)
            
            st.write(f"### {selection}")
            st.info("💡 Vos saisies sont gardées en mémoire quand vous changez de luminaire. N'oubliez pas de télécharger le fichier Excel à la fin !")
            
            # --- NOUVEAUTÉ : Rapport de largeur 1 pour 3 ---
            config_colonnes = {}
            for col in df.columns:
                if col == "Besoin" or col.startswith("Proposition"):
                    config_colonnes[col] = st.column_config.TextColumn(width=300)
                elif col in colonnes_commentaires:
                    config_colonnes[col] = st.column_config.TextColumn(width=100)
            
            # Le tableau s'affiche et on capture immédiatement les modifications
            edited_df = st.data_editor(df_style, use_container_width=True, height=800, column_config=config_colonnes)
            
            # Mise à jour de la mémoire avec ce qui vient d'être tapé
            st.session_state['sauvegardes'][cle_active] = edited_df
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier.")
else:
    st.info("En attente d'un ou plusieurs fichiers CSV...")
