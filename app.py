import streamlit as st
from io import BytesIO

# Import your individual analyzer modules (or keep functions here)
# from crif_analyzer import crif_commercial_app
# from cibil_consumer import cibil_consumer_app
# from cibil_commercial import cibil_commercial_app

st.set_page_config(page_title="Credit Report Analyzer", layout="wide")
st.title("📊 Credit Report Analyzer")

# Sidebar navigation
app_mode = st.sidebar.radio(
    "Choose Analyzer",
    ["CRIF Report", "CIBIL Consumer", "CIBIL Commercial"]
)

if app_mode == "CIBIL Consumer":
    from cibil_consumer import cibil_consumer_app
    cibil_consumer_app()

elif app_mode == "CIBIL Commercial":
    from cibil_commercial import cibil_commercial_app
    cibil_commercial_app()

elif app_mode == "CRIF Report":
    from crif_analyzer import crif_app
    crif_app()
