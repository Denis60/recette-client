import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

uploaded_file = st.file_uploader("Chargez votre fichier CSV ici", type=['csv'])

def process_csv(file):
    # Lire le fichier en texte
    content = file.getvalue().decode("utf-8", errors="replace")
    lines = content.split('\n')
    
    tables = {}
    current_title = None
    current_data = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Détection d'un nouveau titre de tableau entre << >>
        if line.startswith("<<") and ">>" in line:
            # On sauvegarde le tableau précédent s'il y en a un
            if current_title and current_data:
                tables[current_title] = current_data
                
            # Nouveau titre (on nettoie les << >> et les points-virgules)
            current_title = line.split(">>")[0].replace("<<", "").strip()
            current_data = []
        else:
            if current_title is not None:
                current_data.append(line)
                
    # Sauvegarder le tout dernier tableau
    if current_title and current_data:
        tables[current_title] = current_data
        
    return tables

if uploaded_file is not None:
    # 1. Découpage du fichier
    tables_dict = process_csv(uploaded_file)
    
    if tables_dict:
        # 2. Liste déroulante pour choisir le tableau
        noms_tableaux = list(tables_dict.keys())
        selection = st.selectbox("Sélectionnez un luminaire à recetter :", noms_tableaux)
        
        # 3. Affichage du tableau sélectionné
        if selection:
            # On convertit les lignes de texte en tableau de données (DataFrame)
            csv_string = "\n".join(tables_dict[selection])
            df = pd.read_csv(io.StringIO(csv_string), sep=";", index_col=False)
            
            # Nettoyage des colonnes complètement vides à droite
            df = df.dropna(how='all', axis=1)
            
            # Astuce pour figer les DEUX premières colonnes au scroll : on les définit comme "Index"
            if len(df.columns) >= 2:
                colonnes = list(df.columns)
                # On donne un nom générique à la première colonne si elle est vide
                if 'Unnamed' in str(colonnes[0]) or colonnes[0] == '':
                    colonnes[0] = "Caractéristique"
                df.columns = colonnes
                
                # On fige les deux premières colonnes
                df = df.set_index([df.columns[0], df.columns[1]])
            
            st.write(f"### {selection}")
            
            # On affiche le tableau. Streamlit fige automatiquement l'index !
            st.dataframe(df, use_container_width=True)
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier. Vérifiez votre CSV.")
else:
    st.info("En attente d'un fichier CSV...")
