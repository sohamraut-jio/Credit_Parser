import streamlit as st
from io import BytesIO

# Import your individual analyzer modules (or keep functions here)
from crif_analyzer import crif_app
from cibil_consumer import cibil_consumer_app
from cibil_commercial import cibil_commercial_app

st.set_page_config(page_title="Credit Report Analyzer", layout="wide")
st.title("📊 Credit Report Analyzer")

# Sidebar navigation
app_mode = st.sidebar.radio(
    "Choose Analyzer",
    ["CRIF Report", "CIBIL Consumer", "CIBIL Commercial"]
)

if app_mode == "CRIF Report":
    crif_app()

elif app_mode == "CIBIL Consumer":
    cibil_consumer_app()

elif app_mode == "CIBIL Commercial":
    cibil_commercial_app()
