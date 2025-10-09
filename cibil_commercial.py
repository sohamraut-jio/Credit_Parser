import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
import camelot
from io import BytesIO
from tqdm import tqdm
import tempfile


def cibil_commercial_app():
    
    # ----------------------------------
    # PDF Text Extraction
    # ----------------------------------
    def extract_text_from_pdf(file):
        file.seek(0)  # Ensure pointer is at start
        doc = fitz.open(stream=file.read(), filetype="pdf")
        return "\n".join([page.get_text() for page in doc])
    
    # ----------------------------------
    # Borrower Details Extraction
    # ----------------------------------
    def extract_fields(report_text: str) -> dict:
        data = {}
    
        # Company Name
        match = re.search(r'Name:\s*([A-Z\s]+LIMITED)', report_text, re.IGNORECASE)
        data["Company Name"] = match.group(1).strip() if match else None
    
        # Legal Constitution
        match = re.search(r'Legal Constitution:\s*([A-Za-z ]+)', report_text)
        data["Legal Constitution"] = match.group(1).strip() if match else None
    
        # Class of Activity
        match = re.search(r'Class Of Activity:\s*([A-Za-z0-9 ,\-]+)', report_text)
        data["Class of Activity"] = match.group(1).strip() if match else None
    
        # PAN
        match = re.search(r'PAN:\s*([A-Z0-9]+)', report_text)
        data["PAN"] = match.group(1).strip() if match else None
    
        # Date of Incorporation
        match = re.search(r'Date of Incorporation:\s*([0-9]{2}-[A-Za-z]{3}-[0-9]{4})', report_text)
        data["Date of Incorporation"] = match.group(1).strip() if match else None
    
        # CIN/LLPIN
        match = re.search(r'CIN:\s*([A-Z0-9]+)', report_text)
        data["CIN/LLPIN"] = match.group(1).strip() if match else None
    
        # Registered Address
        match = re.search(r'Registered Office Address:\s*(.*?)(?:Telephone|Mobile|Email)', report_text, re.DOTALL)
        data["Regd. Address"] = match.group(1).strip().replace("\n", " ") if match else None
    
        return data
    
    # ----------------------------------
    # Facility Details Extraction
    # ----------------------------------
    def extract_facility_details(a, start, end=None):
        section_a = a[start:end] if end else a[start:]
        details = {}
    
        # Facility number
        match_fac_no = re.search(r'Credit Facility\s*(\d+)', section_a, re.IGNORECASE)
        if match_fac_no:
            details['Facility_No'] = match_fac_no.group(1)
    
        # Type
        match = re.search(r'Type:\s+(.*)', section_a)
        if match:
            details['Type'] = match.group(1).strip()
    
        # DPD / Asset Classification
        match = re.search(r'Last Reported Date.*?\n([A-Z]+\s*\d*)', section_a, flags=re.IGNORECASE | re.DOTALL)
        if match:
            details['DPD/Asset Classification'] = match.group(1).strip().upper()
    
        # Info as of
        match = re.search(r'(\d{2}-[A-Z]{3}-\d{4}|-)\s*[\n ]+(\d{2}-[A-Z]{3}-\d{4}|-)', section_a, flags=re.IGNORECASE)
        if match:
            details['Info. as of'] = match.group(1).strip().upper()
    
        # Sanctioned Date
        match = re.search(r'Sanctioned:\s*(\d{2}-[A-Z]{3}-\d{4}|-)', section_a, flags=re.IGNORECASE)
        if match:
            details['Sanctioned Date'] = match.group(1).strip().upper()
    
        # Sanctioned Amount
        match = re.search(r'Sanctioned (INR|USD|EUR):\s*([\d,]+)', section_a, flags=re.IGNORECASE)
        if match:
            currency = match.group(1).upper()
            amount = match.group(2).strip()
            details['Sanctioned Amount'] = f"{amount} {currency}"
    
        # Current Balance
        match = re.search(r'Outstanding Balance:\s*([\d,]+)', section_a, flags=re.IGNORECASE)
        if match:
            details['Current Balance'] = match.group(1).strip()
    
        # Closed Date
        match = re.search(r'Loan Expiry\s*/\s*Maturity:\s*(\d{2}-[A-Z]{3}-\d{4}|-)', section_a, flags=re.IGNORECASE)
        if match:
            details['Closed Date'] = match.group(1).strip().upper()
    
        # Amount Overdue
        match = re.search(r'Overdue:\s*([\d,]+)', section_a, flags=re.IGNORECASE)
        if match:
            details['Amount Overdue'] = match.group(1).strip()
    
        # Suit Filed
        match = re.search(r'Suit Filed:\s*(\d{2}-[A-Z]{3}-\d{4}|-)', section_a, flags=re.IGNORECASE)
        if match:
            details['Suit Filed Status'] = match.group(1).strip().upper()
    
        # Wilful Defaulter
        match = re.search(r'Wilful Default:\s*(\d{2}-[A-Z]{3}-\d{4}|-)', section_a, flags=re.IGNORECASE)
        if match:
            details['Wilful Defaulter'] = match.group(1).strip().upper()
    
        return details
    
    # ----------------------------------
    # PDF Table Extraction (Camelot)
    # ----------------------------------
    def extract_table_from_pdf(pdf_path, page_num):
        try:
            tables = camelot.read_pdf(pdf_path, pages=str(page_num))
            return tables
        except Exception as e:
            print(f"Error reading tables: {e}")
            return []
    
    # ----------------------------------
    # Streamlit UI
    # ----------------------------------
    st.sidebar.title("📌 How to Use")
    st.sidebar.markdown("""
    **Step 1:** Upload PDF credit report — corporate supported.
    
    **Step 2:** Click **Generate Excel** when done.
    
    **Step 3:** Download your output file from the download button below!
    
    """)
    st.set_page_config(page_title="CIBIL Commercial Report Analyzer", layout="wide")
    st.title("📊 CIBIL Report Analyzer")
    
    uploaded_file = st.file_uploader("Upload your CIBIL PDF report", type=["pdf"])
    
    if uploaded_file:
        with st.spinner("Extracting data... please wait"):
    
            # -----------------------
            # Extract text
            # -----------------------
            text = extract_text_from_pdf(uploaded_file)
            borrower_details = pd.DataFrame([extract_fields(text)]).T
            borrower_details.columns = ["Value"]
    
            # -----------------------
            # Facility extraction
            # -----------------------
            pattern = r'10\. Credit Facility Details - As Borrower'
            result = [m.start() for m in re.finditer(pattern, text)]
            loan_details = pd.DataFrame()
            for i in tqdm(range(len(result))):
                start = result[i]
                end = result[i + 1] if i < len(result) - 1 else None
                details = extract_facility_details(text, start, end)
                loan_details = pd.concat([loan_details, pd.DataFrame([details])], ignore_index=True)
    
            # -----------------------
            # Table extraction via Camelot
            # -----------------------
            uploaded_file.seek(0)  # Reset pointer
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_path = tmp_file.name
    
            # Credit Summary (Page 1)
            tables_page1 = extract_table_from_pdf(tmp_path, 1)
            if len(tables_page1) > 2:
                df = tables_page1[2].df
                credit_summary = df.loc[df.loc[df[df.columns[0]]=='Your Institution'].index[0]:,:]
                columns = [
                    "Category","Total_Lenders","Total_CF_Borrower","Total_CF_Guarantor","Open_CF",
                    "Total_Outstanding_Borrower","Total_Outstanding_Guarantor","Latest_CF_Opened_Date",
                    "Delinquent_CF_Borrower","Delinquent_CF_Guarantor",
                    "Delinquent_Outstanding_Borrower","Delinquent_Outstanding_Guarantor"
                ]
                credit_summary.columns = columns
            else:
                credit_summary = pd.DataFrame()
    
            # Inquiry Summary (Page 2)
            tables_page2 = extract_table_from_pdf(tmp_path, 2)
            if len(tables_page2) > 0:
                df = tables_page2[0].df
                inquiry_summary = df.loc[df.loc[df[df.columns[0]]=='5. Enquiry Summary'].index[0]+1:,:]
            else:
                inquiry_summary = pd.DataFrame()
    
        # -----------------------
        # Display sections
        # -----------------------
        st.success("✅ Extraction completed!")
    
        with st.expander("Borrower Details"):
            st.dataframe(borrower_details)
    
        with st.expander("Loan / Credit Facility Details"):
            st.dataframe(loan_details)
    
        with st.expander("Credit Summary"):
            st.dataframe(credit_summary)
    
        with st.expander("Inquiry Summary"):
            st.dataframe(inquiry_summary)
    
        # -----------------------
        # Excel Export
        # -----------------------
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            borrower_details.to_excel(writer, sheet_name="Borrower Details")
            loan_details.to_excel(writer, sheet_name="Loan Details", index=False)
            credit_summary.to_excel(writer, sheet_name="Credit Summary", index=False)
            inquiry_summary.to_excel(writer, sheet_name="Inquiry Summary", index=False)
        output.seek(0)
    
        st.download_button(
            label="📥 Download Extracted Excel File",
            data=output,
            file_name=f"Parsed_Output_{uploaded_file.name.replace('.pdf', '.xlsx')}",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    else:
        st.info("Please upload a CIBIL report PDF to start analysis.")
