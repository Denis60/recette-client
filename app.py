import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

uploaded_file = st.file_uploader("Chargez votre fichier CSV ici", type=['csv'])

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

if uploaded_file is not None:
    tables_dict = process_csv(uploaded_file)
    
    if tables_dict:
        noms_tableaux = sorted(list(tables_dict.keys()), key=get_type_number)
        selection = st.selectbox("Sélectionnez un luminaire à recetter :", noms_tableaux)
        
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
                        nom_commentaire = f"💬 Notes {col}"
                        df[nom_commentaire] = "" 
                        nouvel_ordre.append(nom_commentaire)
                        colonnes_commentaires.append(nom_commentaire)
                
                df = df[nouvel_ordre]
                df = df.set_index(df.columns[0])
                
                # --- NOUVEAUTÉ : Coloration uniquement si la cellule contient du texte ---
                def colorier_si_texte(val):
                    # Si la cellule n'est pas vide, on la met en orange bien visible
                    if pd.notna(val) and str(val).strip() != "":
                        return 'background-color: #FFD580; color: black;'
                    # Sinon, on laisse par défaut ou on met un très léger gris pour différencier la colonne
                    return 'background-color: #FAFAFA;'
                
                # Application de la couleur cellule par cellule
                try:
                    df_style = df.style.map(colorier_si_texte, subset=colonnes_commentaires)
                except AttributeError:
                    df_style = df.style.applymap(colorier_si_texte, subset=colonnes_commentaires)
                
                st.write(f"### {selection}")
                st.info("💡 Double-cliquez pour ajouter vos commentaires. La cellule se coloriera une fois le texte validé (Touche Entrée).")
                
                config_colonnes = {col: st.column_config.TextColumn(width="small") for col in colonnes_commentaires}
                
                # --- NOUVEAUTÉ : Hauteur forcée (height=800) pour voir plus de lignes ---
                st.data_editor(df_style, use_container_width=True, height=800, column_config=config_colonnes)
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier. Vérifiez votre CSV.")
else:
    st.info("En attente d'un fichier CSV...")
