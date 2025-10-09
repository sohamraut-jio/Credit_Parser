
import streamlit as st

st.set_page_config(page_title="Credit Report Analyzer", layout="centered")

st.title("📊 Credit Report Analyzer Suite")

option = st.selectbox(
    "Select an Analyzer to Launch",
    ["-- Choose --", "CRIF Report Analyzer", "CIBIL Consumer Analyzer", "CIBIL Commercial Analyzer"]
)

if option == "CRIF Report Analyzer":
    st.write("👉 Run: `streamlit run crif_analyzer.py`")

elif option == "CIBIL Consumer Analyzer":
    st.write("👉 Run: `streamlit run cibil_consumer.py`")

elif option == "CIBIL Commercial Analyzer":
    st.write("👉 Run: `streamlit run cibil_commercial.py`")
