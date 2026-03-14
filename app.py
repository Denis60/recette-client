import streamlit as st
import pandas as pd

# Configuration de base de la page
st.set_page_config(page_title="Recette Fonctionnelle", layout="wide")

st.title("Validation des Recettes")

# Zone de téléchargement du fichier CSV
uploaded_file = st.file_uploader("Chargez votre fichier CSV ici", type=['csv'])

if uploaded_file is not None:
    st.success("Fichier chargé avec succès ! (L'affichage arrivera à la prochaine étape)")
else:
    st.info("En attente d'un fichier CSV...")
