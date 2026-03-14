import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

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

def preparer_tableau(csv_string):
    df = pd.read_csv(io.StringIO(csv_string), sep=";", index_col=False)
    df = df.fillna("")
    df = df.astype(str)
    df = df.replace(r'^\s*CCTP\s*$', '', regex=True)
    
    colonnes_commentaires = []
    if len(df.columns) >= 2:
        col_0 = df.columns[0]
        col_1 = df.columns[1]
        
        # --- NOUVEAUTÉ : Fusion des deux premières colonnes ---
        # On fusionne le texte avec un espace entre les deux
        df[col_1] = df[col_0].str.strip() + " " + df[col_1].str.strip()
        # On supprime l'ancienne première colonne
        df = df.drop(columns=[col_0])
        # On renomme la colonne fusionnée "Besoin"
        df.rename(columns={col_1: "Besoin"}, inplace=True)
        
        nouvel_ordre = ["Besoin"]
        
        for col in df.columns:
            if col != "Besoin":
                nouvel_ordre.append(col)
                valeur_catalogue = str(df[col].iloc[0]).strip()
            else:
                valeur_catalogue = ""
                
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
        
        # La colonne fusionnée "Besoin" devient notre colonne figée
        df = df.set_index("Besoin")
        
    return df, colonnes_commentaires

if uploaded_files:
    noms_fichiers = [f.name for f in uploaded_files]
    fichier_selectionne = st.selectbox("1️⃣ Sélectionnez un fichier :", noms_fichiers)
    
    fichier_actif = next(f for f in uploaded_files if f.name == fichier_selectionne)
    tables_dict = process_csv(fichier_actif)
    
    if tables_dict:
        noms_tableaux = sorted(list(tables_dict.keys()), key=get_type_number)
        
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            for nom_tab in noms_tableaux:
                cle_sauvegarde = f"{fichier_selectionne}_{nom_tab}"
                
                if cle_sauvegarde in st.session_state['sauvegardes']:
                    df_export = st.session_state['sauvegardes'][cle_sauvegarde]
                else:
                    csv_str = "\n".join(tables_dict[nom_tab])
                    df_export, _ = preparer_tableau(csv_str)
                
                nom_onglet = str(nom_tab)[:31]
                nom_onglet = re.sub(r'[\\*?:/\[\]]', '', nom_onglet)
                df_export.to_excel(writer, sheet_name=nom_onglet)
        
        donnees_excel = output_excel.getvalue()
        
        # --- ALERTE AJOUTÉE POUR LA SAUVEGARDE ---
        st.warning("⚠️ Attention : Pensez bien à télécharger le fichier Excel avant de fermer la page, sinon vos saisies seront définitivement perdues !")
        
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
            
            # --- NOUVEAUTÉ : Configuration des largeurs ---
            config_colonnes = {
                # On force la largeur de notre index (la colonne Besoin fusionnée)
                "Besoin": st.column_config.TextColumn(width=300)
            }
            
            for col in df.columns:
                if col.startswith("Proposition"):
                    config_colonnes[col] = st.column_config.TextColumn(width=300)
                elif col in colonnes_commentaires:
                    config_colonnes[col] = st.column_config.TextColumn(width=100)
            
            edited_df = st.data_editor(df_style, use_container_width=True, height=800, column_config=config_colonnes)
            
            st.session_state['sauvegardes'][cle_active] = edited_df
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier.")
else:
    st.info("En attente d'un ou plusieurs fichiers CSV...")
