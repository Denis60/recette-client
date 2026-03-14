import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

# --- NOUVEAUTÉ : Autorise le chargement de multiples fichiers ---
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

# Si au moins un fichier est chargé
if uploaded_files:
    # --- NOUVEAUTÉ : Menu déroulant pour le choix du fichier ---
    noms_fichiers = [f.name for f in uploaded_files]
    fichier_selectionne = st.selectbox("1️⃣ Sélectionnez un fichier :", noms_fichiers)
    
    # On récupère le fichier correspondant au choix
    fichier_actif = next(f for f in uploaded_files if f.name == fichier_selectionne)
    
    tables_dict = process_csv(fichier_actif)
    
    if tables_dict:
        noms_tableaux = sorted(list(tables_dict.keys()), key=get_type_number)
        
        # Le menu des luminaires se met à jour en fonction du fichier choisi au-dessus
        selection = st.selectbox("2️⃣ Sélectionnez un luminaire à recetter :", noms_tableaux)
        
        if selection:
            csv_string = "\n".join(tables_dict[selection])
            df = pd.read_csv(io.StringIO(csv_string), sep=";", index_col=False)
            df = df.replace(r'^\s*CCTP\s*$', '', regex=True)
            
            if len(df.columns) >= 1:
                colonnes = list(df.columns)
                if 'Unnamed' in str(colonnes[0]) or colonnes[0] == '':
                    colonnes[0] = "Caractéristique"
                df.columns = colonnes
                
                nouvel_ordre = [df.columns[0]]
                colonnes_commentaires = []
                
                for col in df.columns[1:]:
                    nouvel_ordre.append(col)
                    valeur_catalogue = str(df[col].iloc[0]).strip()
                    is_besoin = (col == 'Besoin')
                    is_prop_valide = col.startswith('Proposition') and valeur_catalogue != "" and valeur_catalogue.lower() != "nan"
                    
                    if is_besoin or is_prop_valide:
                        # --- NOUVEAUTÉ : Ajout de DEUX colonnes ---
                        col_ekla = f"Eklalight ({col})"
                        col_memo = f"Memorandum ({col})"
                        
                        df[col_ekla] = "" 
                        df[col_memo] = "" 
                        
                        nouvel_ordre.extend([col_ekla, col_memo])
                        colonnes_commentaires.extend([col_ekla, col_memo])
                
                df = df[nouvel_ordre]
                
                # Figeage UNIQUEMENT de la première colonne (sinon l'appli plante)
                df = df.set_index(df.columns[0])
                
                def colorier_si_texte(val):
                    if pd.notna(val) and str(val).strip() != "":
                        return 'background-color: #FFD580; color: black;'
                    return 'background-color: #FAFAFA;'
                
                try:
                    df_style = df.style.map(colorier_si_texte, subset=colonnes_commentaires)
                except AttributeError:
                    df_style = df.style.applymap(colorier_si_texte, subset=colonnes_commentaires)
                
                st.write(f"### {selection}")
                st.info("💡 Double-cliquez pour ajouter vos commentaires.")
                
                # On ajuste la largeur pour que les 2 colonnes ne prennent pas trop de place
                config_colonnes = {col: st.column_config.TextColumn(width="small") for col in colonnes_commentaires}
                
                st.data_editor(df_style, use_container_width=True, height=800, column_config=config_colonnes)
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier. Vérifiez votre CSV.")
else:
    st.info("En attente d'un ou plusieurs fichiers CSV...")
