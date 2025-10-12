import streamlit as st
import pandas as pd
import re
from PyPDF2 import PdfReader
from io import BytesIO
from datetime import datetime

def clean_amount(amount_str):
    """Extract only numeric value from a string and convert to int."""
    if not amount_str:
        return 0
    numeric_str = re.sub(r'[^\d]', '', amount_str)
    return int(numeric_str) if numeric_str else 0

def extract_max_dpd(block):
    """
    Extract the maximum DPD from a CIBIL personal account block.
    Handles multi-line YEAR / MONTH tables with DPD numbers.
    """
    dpd_section_match = re.search(
        r'DAYS PAST DUE/ASSET CLASSIFICATION.*?\n(?:YEAR.*\n)((?:.*\n)*?)(?:ACCOUNT|$)',
        block, re.IGNORECASE
    )
    if not dpd_section_match:
        return 0
    dpd_text = dpd_section_match.group(1)
    dpd_numbers = re.findall(r'\b(\d{3})\b', dpd_text)
    dpd_values = [int(x) for x in dpd_numbers]
    return max(dpd_values) if dpd_values else 0

def parse_personal_block(block):
    def extract(pattern):
        m = re.search(pattern, block, re.IGNORECASE)
        return m.group(1).strip() if m else ''

    parsed = {}
    parsed['TYPE'] = extract(r'ACCOUNT\s*TYPE\s*[:\-]?\s*(.+)')
    parsed['OWNERSHIP'] = extract(r'OWNERSHIP\s*[:\-]?\s*(.+)')
    parsed['OPENED'] = extract(r'DATE OPENED\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})')
    parsed['CLOSED'] = extract(r'DATE CLOSED\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})')
    parsed['SANCTIONED'] = clean_amount(extract(r'CREDIT LIMIT\s*[:\-]?\s*(.+)'))
    parsed['CURRENT BALANCE'] = clean_amount(extract(r'BALANCE\s*[:\-]?\s*(.+)'))
    parsed['HIGH CREDIT'] = clean_amount(extract(r'HIGH CREDIT\s*AMOUNT\s*[:\-]?\s*(.+)'))
    parsed['CASH LIMIT'] = clean_amount(extract(r'CASH LIMIT\s*[:\-]?\s*(.+)'))
    parsed['EMI'] = clean_amount(extract(r'EMI\s*[:\-]?\s*(.+)'))
    parsed['ACTUAL PAYMENT'] = clean_amount(extract(r'ACTUAL PAYMENT\s*[:\-]?\s*(.+)'))
    parsed['PAYMENT FREQUENCY'] = extract(r'PAYMENT FREQUENCY\s*[:\-]?\s*(.+)')
    parsed['STATUS'] = extract(r'STATUS\s*[:\-]?\s*(.+)')
    parsed['MAX DPD'] = extract_max_dpd(block)
    return parsed

def personal_row(parsed, customer_name, sr_no):
    status = "Active" if parsed.get('CLOSED', '') == '' else "Closed"
    return {
        'Sr. No.': sr_no,
        'Borrower': customer_name,
        'Type of loan': parsed.get('TYPE', ''),
        'Ownership': parsed.get('OWNERSHIP', ''),
        'Sanction date': parsed.get('OPENED', ''),
        'Closed date': parsed.get('CLOSED', ''),
        'Sanctioned amount': parsed.get('SANCTIONED', ''),
        'Current balance': parsed.get('CURRENT BALANCE', ''),
        'High credit amount': parsed.get('HIGH CREDIT', ''),
        'Cash limit': parsed.get('CASH LIMIT', ''),
        'EMI': parsed.get('EMI', ''),
        'Actual payment': parsed.get('ACTUAL PAYMENT', ''),
        'Payment frequency': parsed.get('PAYMENT FREQUENCY', ''),
        'Status': status,
        'Max DPD': parsed.get('MAX DPD', 0)
    }

def parse_corporate_block(block, customer_name):
    patterns = {
        'TYPE': r'Type:\s*(.+)',
        'OPENED': r'Sanctioned:\s*(\d{2}-[A-Za-z]{3}-\d{4})',
        'SANCTIONED': r'Sanctioned INR:\s*([\d,]+)',
        'CURRENT BALANCE': r'Outstanding Balance:\s*(-?[\d,]+)',
        'EMI': r'Installment Amount:\s*([\d,]+)',
        'OVERDUE': r'Overdue:\s*(-?[\d,]+)'
    }
    parsed = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, block, re.IGNORECASE)
        parsed[key] = match.group(1).strip() if match else ''

    # Format sanction date
    formatted_date = parsed.get('OPENED', '')
    try:
        formatted_date = datetime.strptime(parsed.get('OPENED', ''), "%d-%b-%Y").strftime("%d/%m/%Y")
    except:
        pass

    return {
        'Sr. No.': 1,
        'Borrower': customer_name,
        'Type of loan': parsed.get('TYPE', ''),
        'Sanction date (DD/MM/YYYY)': formatted_date,
        'Sanction amount (INR)/ CC outstanding Amount': parsed.get('SANCTIONED', ''),
        'Monthly EMI (INR)': parsed.get('EMI', ''),
        'Current outstanding (INR)': parsed.get('CURRENT BALANCE', ''),
        'Overdue Amount': parsed.get('OVERDUE', ''),
        'Max DPD in L12 Months': '',
        'Max DPD in L36 Months': ''
    }

# ---------------- STREAMLIT APP ----------------
def cibil_consumer_app():
    st.set_page_config(page_title="CIBIL Analyzer", layout="wide")
    st.title("📑 CIBIL Analyzer")

    st.sidebar.title("📌 How to Use")
    st.sidebar.markdown("""
    **Step 1:** Upload a single PDF credit report (personal or corporate).  
    **Step 2:** Click **Generate Excel** when done.  
    **Step 3:** Download your formatted Excel output below!
    """)

    uploaded_file = st.file_uploader("📂 Upload one CIBIL report (PDF only)", type="pdf")

    if uploaded_file:
        file_bytes = uploaded_file.read()
        reader = PdfReader(BytesIO(file_bytes))
        full_text = "".join([page.extract_text() + "\n" for page in reader.pages])

        summary_rows = []
        all_personal_rows = []
        all_corporate_rows = []

        # Detect report type
        if 'COMMERCIAL CREDIT INFORMATION REPORT' in full_text:
            # Corporate
            name_match = re.search(r'Name of Borrower\s*[:\-]?\s*(.+)', full_text)
            customer_name = name_match.group(1).strip() if name_match else "Unknown Entity"
            summary_rows.append({'Name': customer_name, 'Score': re.search(r'CMR-\s*([\d,]+)', full_text).group(1) if re.search(r'CMR-\s*([\d,]+)', full_text) else 'None'})

            matches = re.findall(r'Credit Facility Details(.*?)Overdue Details', full_text, re.DOTALL)
            for i, block in enumerate(matches, 1):
                all_corporate_rows.append(parse_corporate_block(block, customer_name))

            summary_df = pd.DataFrame(summary_rows)
            corporate_df = pd.DataFrame(all_corporate_rows)

            with st.expander("🏢 Corporate Report Summary"):
                st.dataframe(summary_df)
                st.dataframe(corporate_df)

            if st.button("✅ Generate Excel"):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, index=False, sheet_name="Summary")
                    corporate_df.to_excel(writer, index=False, sheet_name="Corporate_Entity")
                output.seek(0)
                st.download_button("📥 Download Excel", output, uploaded_file.name.replace(".pdf", ".xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        else:
            # Personal
            # Detect consumer name
name_match = re.search(r'CONSUMER NAME\s*[:\-]?\s*(.+)', full_text, re.IGNORECASE)
customer_name = name_match.group(1).strip() if name_match else "Unknown Individual"

# Extract personal score
score_match = re.search(r'CREDITVISION® SCORE\s*[:\-]?\s*(\d{3})', full_text, re.IGNORECASE)
pscore = score_match.group(1) if score_match else "None"

summary_rows.append({'Name': customer_name, 'Score': pscore})

# ---------------- Detect which personal format ----------------
if 'ACCOUNT INFORMATION' in full_text:
    # ----- Colab-style personal report -----
    matches = re.split(r'ACCOUNT INFORMATION', full_text)[1:]
    for i, block in enumerate(matches, 1):
        parsed = parse_personal_block(block)
        all_personal_rows.append(personal_row(parsed, customer_name, i))
else:
    # ----- Streamlit-style personal report -----
    matches = re.findall(r'STATUS(.*?)(?:ACCOUNT DATES|ENQUIRIES:)', full_text, re.DOTALL)
    for i, block in enumerate(matches, 1):
        parsed = parse_streamlit_personal_block(block)
        all_personal_rows.append(personal_row(parsed, customer_name, i))

# Create DataFrames
summary_df = pd.DataFrame(summary_rows)
personal_df = pd.DataFrame(all_personal_rows)

# Display in Streamlit
with st.expander("📌 Personal Summary"):
    st.dataframe(summary_df)
with st.expander(f"👤 Personal Account Details: {customer_name}"):
    st.dataframe(personal_df)

# Excel export
if st.button("✅ Generate Excel"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        personal_df.to_excel(writer, index=False, sheet_name=f"{customer_name}"[:31])
    output.seek(0)
    st.download_button(
        "📥 Download Excel",
        output,
        uploaded_file.name.replace(".pdf", ".xlsx"),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    cibil_consumer_app()
