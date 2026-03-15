import streamlit as st
import pandas as pd
import io
import re
import json
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

st.set_page_config(page_title="Recette Fonctionnelle V2", layout="wide")
st.title("Validation des Recettes (Connecté)")

# --- INITIALISATION SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Impossible de se connecter à la base de données. Vérifiez vos clés dans Streamlit Secrets.")
    st.stop()

# --- IDENTIFICATION ---
st.markdown("### 👤 Identification")
utilisateur = st.text_input("Veuillez entrer votre prénom ou pseudo pour éditer les tableaux :")

if not utilisateur:
    st.warning("⚠️ L'identification est obligatoire pour ne pas se marcher sur les pieds avec les autres collaborateurs.")
    st.stop()

st.success(f"Connecté en tant que : **{utilisateur}**")
st.markdown("---")

def process_csv(file):
    content = file.getvalue().decode("utf-8-sig", errors="replace")
    content = content.replace("source: ", "").replace("value: ", "").replace("unit: ", "")
    lines = content.split('\n')
    tables = {}
    current_title = None
    current_data = []
    for line in lines:
        line = line.strip()
        if not line: continue
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
    if match: return int(match.group(1))
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
        df[col_1] = df[col_0].str.strip() + " " + df[col_1].str.strip()
        df = df.drop(columns=[col_0])
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
        df = df.set_index("Besoin")
    return df, colonnes_commentaires

# --- GESTION DES FICHIERS ---
reponse_fichiers = supabase.table("tableaux_recette").select("nom_fichier").execute()
fichiers_en_base = sorted(list(set([row["nom_fichier"] for row in reponse_fichiers.data])))

st.markdown("### 📁 Chargement et Sélection")
uploaded_files = st.file_uploader("Glissez un NOUVEAU fichier CSV ici pour l'ajouter à la base de données :", type=['csv'], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        if file.name not in fichiers_en_base:
            with st.spinner(f"Installation de {file.name} dans la base de données..."):
                tables_dict = process_csv(file)
                for nom_tab, donnees_brutes in tables_dict.items():
                    csv_str = "\n".join(donnees_brutes)
                    df_initial, _ = preparer_tableau(csv_str)
                    
                    json_data = json.loads(df_initial.reset_index().to_json(orient='split'))
                    
                    id_unique = f"{file.name}_{nom_tab}"
                    supabase.table("tableaux_recette").insert({
                        "id": id_unique,
                        "nom_fichier": file.name,
                        "nom_tableau": nom_tab,
                        "donnees": json_data
                    }).execute()
            st.success(f"{file.name} importé avec succès !")
            st.rerun()

if len(fichiers_en_base) > 0:
    fichier_selectionne = st.selectbox("1️⃣ Sélectionnez un fichier à recetter :", fichiers_en_base)
    
    reponse_excel = supabase.table("tableaux_recette").select("nom_tableau, donnees").eq("nom_fichier", fichier_selectionne).execute()
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        tableaux_tries = sorted(reponse_excel.data, key=lambda x: get_type_number(x["nom_tableau"]))
        for row in tableaux_tries:
            df_export = pd.read_json(io.StringIO(json.dumps(row["donnees"])), orient='split')
            nom_onglet = str(row["nom_tableau"])[:31]
            nom_onglet = re.sub(r'[\\*?:/\[\]]', '', nom_onglet)
            df_export.to_excel(writer, sheet_name=nom_onglet, index=False)
            
    st.download_button(
        label="📥 Télécharger tout ce fichier en Excel",
        data=output_excel.getvalue(),
        file_name=f"Recette_{fichier_selectionne.replace('.csv', '')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown("---")
    
    reponse_tableaux = supabase.table("tableaux_recette").select("*").eq("nom_fichier", fichier_selectionne).execute()
    tableaux_tries = sorted(reponse_tableaux.data, key=lambda x: get_type_number(x["nom_tableau"]))
    noms_tableaux = [row["nom_tableau"] for row in tableaux_tries]
    
    selection = st.selectbox("2️⃣ Sélectionnez un luminaire :", noms_tableaux)
    
    if selection:
        ligne_bdd = next(row for row in tableaux_tries if row["nom_tableau"] == selection)
        id_ligne = ligne_bdd["id"]
        
        est_verrouille = False
        if ligne_bdd["verrou_user"] and ligne_bdd["verrou_user"] != utilisateur:
            date_verrou = datetime.fromisoformat(ligne_bdd["verrou_date"])
            if datetime.now(timezone.utc) - date_verrou < timedelta(minutes=30):
                est_verrouille = True
                
        if est_verrouille:
            st.error(f"🔒 **ATTENTION** : Ce tableau est actuellement en cours d'édition par **{ligne_bdd['verrou_user']}**.")
            st.warning("Veuillez patienter qu'il/elle termine, ou choisissez un autre luminaire.")
        else:
            supabase.table("tableaux_recette").update({
                "verrou_user": utilisateur,
                "verrou_date": datetime.now(timezone.utc).isoformat()
            }).eq("id", id_ligne).execute()
            
            st.success(f"🔓 Tableau verrouillé à votre nom. Vous seul pouvez le modifier.")
            st.warning("⚠️ Tapez autant de texte que vous voulez. **N'oubliez pas de cliquer sur le bouton bleu 'Enregistrer' tout en bas** avant de changer de luminaire !")

            df = pd.read_json(io.StringIO(json.dumps(ligne_bdd["donnees"])), orient='split')
            
            if 'Besoin' not in df.columns and df.index.name == 'Besoin':
                df = df.reset_index()
            if 'Besoin' in df.columns:
                df = df.set_index('Besoin')
            else:
                df = df.set_index(df.columns[0])
            
            colonnes_commentaires = [col for col in df.columns if col.startswith("Eklalight") or col.startswith("Memorandum")]
            
            def colorier_si_texte(val):
                if str(val).strip() != "" and str(val).lower() != "nan":
                    return 'background-color: #FFD580; color: black;'
                return 'background-color: #FAFAFA;'
            
            try:
                df_style = df.style.map(colorier_si_texte, subset=colonnes_commentaires)
            except AttributeError:
                df_style = df.style.applymap(colorier_si_texte, subset=colonnes_commentaires)
            
            config_colonnes = {"Besoin": st.column_config.TextColumn(width=300)}
            for col in df.columns:
                if col.startswith("Proposition"):
                    config_colonnes[col] = st.column_config.TextColumn(width=300)
                elif col in colonnes_commentaires:
                    config_colonnes[col] = st.column_config.TextColumn(width=100)
            
            # --- MODIFICATION DE LA HAUTEUR ICI (670 pixels = ~18 lignes + en-tête) ---
            edited_df = st.data_editor(
                df_style, 
                use_container_width=True, 
                height=600, 
                column_config=config_colonnes,
                key=f"editeur_{id_ligne}"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            
            df_str = df.reset_index().fillna("").astype(str)
            edited_str = edited_df.reset_index().fillna("").astype(str)
            
            with col1:
                if st.button("💾 Enregistrer mes modifications", type="primary", use_container_width=True):
                    if not df_str.equals(edited_str):
                        json_data = json.loads(edited_df.reset_index().to_json(orient='split'))
                        supabase.table("tableaux_recette").update({
                            "donnees": json_data,
                            "verrou_date": datetime.now(timezone.utc).isoformat()
                        }).eq("id", id_ligne).execute()
                        st.success("✅ Vos modifications ont été sauvegardées dans la base de données !")
                    else:
                        st.info("Aucune modification détectée.")
                        
            with col2:
                if st.button("🔓 J'ai terminé (Libérer le verrou)", use_container_width=True):
                    supabase.table("tableaux_recette").update({
                        "verrou_user": None,
                        "verrou_date": None
                    }).eq("id", id_ligne).execute()
                    st.rerun()

else:
    st.info("La base de données est vide. Veuillez glisser votre premier fichier CSV ci-dessus.")
