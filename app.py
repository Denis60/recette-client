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
# On lit les fichiers dispos
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
                        "donnees": json_data,
                        "evaluation": "à évaluer",
                        "commentaire": ""  # On initie le champ vide
                    }).execute()
            st.success(f"{file.name} importé avec succès !")
            st.rerun()

if len(fichiers_en_base) > 0:
    fichier_selectionne = st.selectbox("1️⃣ Sélectionnez un fichier à recetter :", fichiers_en_base)
    st.markdown("---")
    
    # On récupère les tableaux SANS forcer le tri (Garde l'ordre d'insertion/CSV)
    reponse_tableaux = supabase.table("tableaux_recette").select("*").eq("nom_fichier", fichier_selectionne).execute()
    tableaux_tries = reponse_tableaux.data
    noms_tableaux = [row["nom_tableau"] for row in tableaux_tries]
    
    OPTION_DEFAUT = "--- Choisir un luminaire ---"
    liste_choix = [OPTION_DEFAUT] + noms_tableaux
    
    if "choix_luminaire" not in st.session_state:
        st.session_state.choix_luminaire = OPTION_DEFAUT

    if st.session_state.get("quitter_tableau", False):
        st.session_state.choix_luminaire = OPTION_DEFAUT
        st.session_state.quitter_tableau = False

    col_gauche, col_droite = st.columns([2, 1])
    
    with col_gauche:
        selection = st.selectbox("2️⃣ Sélectionnez un luminaire :", liste_choix, key="choix_luminaire")
    
    if selection and selection != OPTION_DEFAUT:
        ligne_bdd = next(row for row in tableaux_tries if row["nom_tableau"] == selection)
        id_ligne = ligne_bdd["id"]
        
        est_verrouille = False
        if ligne_bdd["verrou_user"] and ligne_bdd["verrou_user"] != utilisateur:
            date_verrou = datetime.fromisoformat(ligne_bdd["verrou_date"])
            if datetime.now(timezone.utc) - date_verrou < timedelta(minutes=30):
                est_verrouille = True
                
        if est_verrouille:
            with col_droite:
                st.markdown(
                    f"""
                    <div style='margin-top: 28px; background-color: #fce8e6; color: #c5221f; padding: 0 12px; border-radius: 8px; height: 39px; display: flex; align-items: center; font-size: 15px;'>
                        🔒 En édition par {ligne_bdd['verrou_user']}
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            st.warning("Veuillez patienter qu'il/elle termine, ou choisissez un autre luminaire.")
        else:
            supabase.table("tableaux_recette").update({
                "verrou_user": utilisateur,
                "verrou_date": datetime.now(timezone.utc).isoformat()
            }).eq("id", id_ligne).execute()
            
            with col_droite:
                st.markdown(
                    """
                    <div style='margin-top: 28px; background-color: #e6f4ea; color: #1e4620; padding: 0 12px; border-radius: 8px; height: 39px; display: flex; align-items: center; font-size: 15px;'>
                        🔓 Verrouillé à votre nom. Pensez à enregistrer.
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            # --- NOUVEAUTÉ : Zone de Commentaire Libre ---
            valeur_comm_actuelle = ligne_bdd.get("commentaire", "")
            if valeur_comm_actuelle is None:
                valeur_comm_actuelle = ""
                
            nouveau_commentaire = st.text_area(
                "💬 Notes & Commentaires sur ce luminaire :", 
                value=valeur_comm_actuelle,
                placeholder="Ex: Référence absente, besoin de clarifier la source d'alimentation...",
                key=f"comm_{id_ligne}"
            )
            
            # Sauvegarde automatique dès qu'on sort du champ commentaire
            if nouveau_commentaire != valeur_comm_actuelle:
                supabase.table("tableaux_recette").update({
                    "commentaire": nouveau_commentaire,
                    "verrou_date": datetime.now(timezone.utc).isoformat()
                }).eq("id", id_ligne).execute()
                st.toast("Commentaire sauvegardé !", icon="✅")
                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- Affichage du tableau de données ---
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
            
            edited_df = st.data_editor(
                df_style, 
                use_container_width=True, 
                height=500, 
                column_config=config_colonnes,
                key=f"editeur_{id_ligne}"
            )
            
            df_str = df.reset_index().fillna("").astype(str)
            edited_str = edited_df.reset_index().fillna("").astype(str)
            
            if not df_str.equals(edited_str):
                json_data = json.loads(edited_df.reset_index().to_json(orient='split'))
                supabase.table("tableaux_recette").update({
                    "donnees": json_data,
                    "verrou_date": datetime.now(timezone.utc).isoformat()
                }).eq("id", id_ligne).execute()
                st.toast("Sauvegardé automatiquement !", icon="💾")
            
            st.markdown("<br>", unsafe_allow_html=True)

            with st.expander("➕ Ajouter une nouvelle colonne au tableau"):
                col_new_name, col_add_btn = st.columns([3, 1])
                with col_new_name:
                    nouvelle_colonne = st.text_input("Nom de la colonne à ajouter :", key=f"new_col_{id_ligne}")
                with col_add_btn:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Ajouter la colonne", use_container_width=True):
                        if nouvelle_colonne:
                            if nouvelle_colonne not in edited_df.columns:
                                df_updated = edited_df.reset_index()
                                df_updated[nouvelle_colonne] = "" 
                                json_data = json.loads(df_updated.to_json(orient='split'))
                                
                                supabase.table("tableaux_recette").update({
                                    "donnees": json_data,
                                    "verrou_date": datetime.now(timezone.utc).isoformat()
                                }).eq("id", id_ligne).execute()
                                
                                st.rerun()
                            else:
                                st.warning("Cette colonne existe déjà !")

            st.markdown("<br>", unsafe_allow_html=True)
            col_eval, col_save, col_quit = st.columns([2, 1, 1])
            
            with col_eval:
                options_eval = [
                    "à évaluer", 
                    "OK", 
                    "OK mais ajuster (références non identifiées ou hors sujet)", 
                    "KO : bonnes références non présentées"
                ]
                valeur_actuelle = ligne_bdd.get("evaluation", "à évaluer")
                if valeur_actuelle not in options_eval: 
                    valeur_actuelle = "à évaluer"
                    
                nouvelle_eval = st.selectbox(
                    "📊 Évaluation Sélection :", 
                    options_eval, 
                    index=options_eval.index(valeur_actuelle),
                    key=f"eval_{id_ligne}"
                )
                
                if nouvelle_eval != valeur_actuelle:
                    supabase.table("tableaux_recette").update({"evaluation": nouvelle_eval}).eq("id", id_ligne).execute()
                    st.toast("Évaluation mise à jour !", icon="✅")
                    st.rerun()

            with col_save:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("💾 Enregistrer", type="primary", use_container_width=True):
                    if not df_str.equals(edited_str):
                        json_data = json.loads(edited_df.reset_index().to_json(orient='split'))
                        supabase.table("tableaux_recette").update({
                            "donnees": json_data,
                            "verrou_date": datetime.now(timezone.utc).isoformat()
                        }).eq("id", id_ligne).execute()
                        st.success("✅ Sauvegardé !")
                    else:
                        st.info("Aucune modification par rapport au dernier enregistrement.")

            with col_quit:
                st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                if st.button("🔓 Quitter le tableau", use_container_width=True):
                    if not df_str.equals(edited_str):
                        json_data = json.loads(edited_df.reset_index().to_json(orient='split'))
                        supabase.table("tableaux_recette").update({
                            "donnees": json_data,
                            "verrou_user": None,
                            "verrou_date": None
                        }).eq("id", id_ligne).execute()
                    else:
                        supabase.table("tableaux_recette").update({
                            "verrou_user": None,
                            "verrou_date": None
                        }).eq("id", id_ligne).execute()
                    
                    st.session_state.quitter_tableau = True
                    st.rerun()

    # --- NOUVEAUTÉ : Boutons Globaux déplacés tout en bas ---
    st.markdown("<br><br><br><br><br><br>", unsafe_allow_html=True) # Espacement pour bien séparer
    st.markdown("---")
    st.markdown("### ⚙️ Options globales du fichier")
    
    # On recalcule les données Excel avec les tableaux non triés
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        for row in tableaux_tries:
            df_export = pd.read_json(io.StringIO(json.dumps(row["donnees"])), orient='split')
            nom_onglet = str(row["nom_tableau"])[:31]
            nom_onglet = re.sub(r'[\\*?:/\[\]]', '', nom_onglet)
            df_export.to_excel(writer, sheet_name=nom_onglet, index=False)
            
    col_dl, col_del = st.columns(2)
    
    with col_dl:
        st.download_button(
            label="📥 Télécharger tout ce fichier en Excel",
            data=output_excel.getvalue(),
            file_name=f"Recette_{fichier_selectionne.replace('.csv', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with col_del:
        if st.button("🗑️ Supprimer définitivement ce fichier", use_container_width=True):
            with st.spinner("Suppression en cours..."):
                supabase.table("tableaux_recette").delete().eq("nom_fichier", fichier_selectionne).execute()
                if "choix_luminaire" in st.session_state:
                    del st.session_state["choix_luminaire"]
                st.rerun()

else:
    st.info("La base de données est vide. Veuillez glisser votre premier fichier CSV ci-dessus.")
