import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

uploaded_file = st.file_uploader("Chargez votre fichier CSV ici", type=['csv'])

def process_csv(file):
    content = file.getvalue().decode("utf-8-sig", errors="replace")
    
    # Nettoyages globaux demandés
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

if uploaded_file is not None:
    tables_dict = process_csv(uploaded_file)
    
    if tables_dict:
        noms_tableaux = list(tables_dict.keys())
        selection = st.selectbox("Sélectionnez un luminaire à recetter :", noms_tableaux)
        
        if selection:
            csv_string = "\n".join(tables_dict[selection])
            df = pd.read_csv(io.StringIO(csv_string), sep=";", index_col=False)
            
            # Nettoyage de la chaîne "CCTP" si c'est la seule chose dans la cellule (ignorer les espaces)
            df = df.replace(r'^\s*CCTP\s*$', '', regex=True)
            
            if len(df.columns) >= 1:
                colonnes = list(df.columns)
                if 'Unnamed' in str(colonnes[0]) or colonnes[0] == '':
                    colonnes[0] = "Caractéristique"
                df.columns = colonnes
                
                # --- NOUVEAUTÉ : Création intelligente des colonnes de commentaires ---
                nouvel_ordre = [df.columns[0]] # On garde "Caractéristique" en premier
                colonnes_commentaires = []
                
                for col in df.columns[1:]:
                    nouvel_ordre.append(col)
                    
                    # On vérifie la ligne 0 (qui correspond à la ligne 'catalogue')
                    valeur_catalogue = str(df[col].iloc[0]).strip()
                    is_besoin = (col == 'Besoin')
                    # Valide si ça commence par Proposition ET que le catalogue n'est pas vide
                    is_prop_valide = col.startswith('Proposition') and valeur_catalogue != "" and valeur_catalogue.lower() != "nan"
                    
                    if is_besoin or is_prop_valide:
                        nom_commentaire = f"💬 Notes {col}"
                        df[nom_commentaire] = "" # On crée la colonne vide
                        nouvel_ordre.append(nom_commentaire)
                        colonnes_commentaires.append(nom_commentaire)
                
                # On applique ce nouvel ordre au tableau
                df = df[nouvel_ordre]
                
                # On fige toujours la première colonne
                df = df.set_index(df.columns[0])
                
                # --- NOUVEAUTÉ : Mise en couleur orange ---
                def surligner_commentaires(val):
                    return 'background-color: #FFE6CC' # Code couleur orange clair
                
                # Compatibilité pour appliquer la couleur uniquement sur nos colonnes de notes
                try:
                    df_style = df.style.map(surligner_commentaires, subset=colonnes_commentaires)
                except AttributeError:
                    df_style = df.style.applymap(surligner_commentaires, subset=colonnes_commentaires)
                
                st.write(f"### {selection}")
                st.info("💡 Double-cliquez sur les cellules orange pour ajouter vos commentaires.")
                
                # Rendre les colonnes de commentaires plus étroites par défaut
                config_colonnes = {col: st.column_config.TextColumn(width="small") for col in colonnes_commentaires}
                
                # Affichage
                st.data_editor(df_style, use_container_width=True, column_config=config_colonnes)
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier. Vérifiez votre CSV.")
else:
    st.info("En attente d'un fichier CSV...")
