import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")
st.title("Validation des Recettes")

uploaded_file = st.file_uploader("Chargez votre fichier CSV ici", type=['csv'])

def process_csv(file):
    content = file.getvalue().decode("utf-8-sig", errors="replace")
    
    # --- NOUVEAUTÉ : Nettoyage des chaînes de caractères indésirables ---
    content = content.replace("source: ", "").replace("value: ", "")
    
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
            
            if len(df.columns) >= 2:
                colonnes = list(df.columns)
                if 'Unnamed' in str(colonnes[0]) or colonnes[0] == '':
                    colonnes[0] = "Caractéristique"
                df.columns = colonnes
                
                # On fige toujours les deux premières colonnes
                df = df.set_index([df.columns[0], df.columns[1]])
            
            st.write(f"### {selection}")
            
            # --- NOUVEAUTÉ : Remplacement de dataframe par data_editor ---
            st.info("💡 Double-cliquez sur une cellule pour la modifier. Vous pouvez étirer les colonnes.")
            
            # st.data_editor rend tout le tableau modifiable par l'utilisateur
            edited_df = st.data_editor(df, use_container_width=True)
            
    else:
        st.warning("Aucun tableau au format <<Titre>> n'a été trouvé dans le fichier. Vérifiez votre CSV.")
else:
    st.info("En attente d'un fichier CSV...")
