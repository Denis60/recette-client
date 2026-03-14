import streamlit as st
import pandas as pd
import io
import re  # Ajout de la librairie pour détecter les numéros

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

uploaded_file = st.file_uploader("Chargez votre fichier CSV ici", type=['csv'])

def process_csv(file):
    content = file.getvalue().decode("utf-8-sig", errors="replace")
    
    # Nettoyages globaux
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

# --- NOUVEAUTÉ : Fonction pour extraire le numéro et trier ---
def get_type_number(title):
    # Cherche le mot "Type" suivi d'un espace et d'un ou plusieurs chiffres
    match = re.search(r'Type\s+(\d+)', title, re.IGNORECASE)
    if match:
        return int(match.group(1)) # Renvoie le chiffre trouvé
    return 9999 # Si pas de chiffre, on met à la fin

if uploaded_file is not None:
    tables_dict = process_csv(uploaded_file)
    
    if tables_dict:
        # --- NOUVEAUTÉ : Tri de la liste avec notre fonction ---
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
                
                # --- NOUVEAUTÉ : Méthode de coloration plus robuste ---
                def bg_color(col):
                    # Applique la couleur sur toute la colonne si elle fait partie des commentaires
                    if col.name in colonnes_commentaires:
                        return ['background-color: #FFE6CC'] * len(col)
                    return [''] * len(col)
                
                # On utilise apply(..., axis=0) pour traiter colonne par colonne
                df_style = df.style.apply(bg_color, axis=0)
                
                st.write(f"### {selection}")
                st.info("💡 Double-cliquez sur les cellules orange pour ajouter vos commentaires.")
                
                config_colonnes = {col: st.column_config.TextColumn(width="small") for col in colonnes_commentaires}
                
                st.data_editor(df_style, use_container_width=True, column_config=config_colonnes)
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier. Vérifiez votre CSV.")
else:
    st.info("En attente d'un fichier CSV...")
