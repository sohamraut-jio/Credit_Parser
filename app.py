import streamlit as st
from crif_analyzer import crif_app
from cibil_consumer import cibil_consumer_app
from cibil_commercial import cibil_commercial_app

st.set_page_config(page_title="Credit Report Analyzer Suite", layout="wide")
st.title("📊 Credit Report Analyzer Suite")

st.sidebar.title("Select Analyzer")
choice = st.sidebar.radio(
    "Choose which analyzer to use:",
    [
        "CRIF Report Analyzer",
        "CIBIL Consumer Analyzer",
        "CIBIL Commercial Analyzer"
    ]
)

if choice == "CRIF Report Analyzer":
    crif_app()

elif choice == "CIBIL Consumer Analyzer":
    cibil_consumer_app()

elif choice == "CIBIL Commercial Analyzer":
    cibil_commercial_app()
