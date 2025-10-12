# --- CIBIL Analyzer (Streamlit Version, Multi-format Personal & Corporate) ---
import streamlit as st
import pandas as pd
import re
from PyPDF2 import PdfReader
from io import BytesIO
from datetime import datetime

# ---------- Helper Functions ----------
def clean_amount(amount_str):
    """Extract only numeric value from a string and convert to int."""
    if not amount_str:
        return 0
    numeric_str = re.sub(r'[^\d]', '', amount_str)
    return int(numeric_str) if numeric_str else 0

def extract_max_dpd(block):
    """Extract maximum DPD from Colab-style personal account block."""
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

def parse_colab_personal_block(block):
    """Parse Colab-style personal account block."""
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

def extract_max_dpd_streamlit(block):
    """
    Extract maximum DPD from Streamlit-style personal block.
    Looks for the DAYS PAST DUE section and returns the maximum numeric value.
    """
    dpd_section_match = re.search(
        r'DAYS PAST DUE/ASSET CLASSIFICATION.*?\n((?:\d{3}\s*\n?)+)', block, re.IGNORECASE
    )
    if not dpd_section_match:
        return 0
    dpd_text = dpd_section_match.group(1)
    # Extract all 3-digit numbers
    dpd_numbers = re.findall(r'\b(\d{3})\b', dpd_text)
    dpd_values = [int(x) for x in dpd_numbers if x.isdigit()]
    return max(dpd_values) if dpd_values else 0

def parse_streamlit_personal_block(block):
    """Parse Streamlit-style personal account block."""
    parsed = {}
    type_match = re.search(r'TYPE:\s*(.+)', block, re.IGNORECASE)
    parsed['TYPE'] = type_match.group(1).strip() if type_match else ''
    
    own_match = re.search(r'OWNERSHIP:\s*(.+?)(?:OPENED|\n|LAST|REPORTED|CLOSED|PMT|$)', block, re.IGNORECASE)
    parsed['OWNERSHIP'] = own_match.group(1).strip() if own_match else ''
    
    opened_match = re.search(r'OPENED:\s*(\d{2}-\d{2}-\d{4})', block)
    parsed['OPENED'] = opened_match.group(1).strip() if opened_match else ''
    
    closed_match = re.search(r'CLOSED:\s*(.+)', block)
    parsed['CLOSED'] = closed_match.group(1).strip() if closed_match else ''
    
    san_match = re.search(r'(?:SANCTIONED|CREDIT LIMIT):\s*([\d,]+)', block)
    parsed['SANCTIONED'] = clean_amount(san_match.group(1)) if san_match else 0
    
    curr_match = re.search(r'CURRENT BALANCE:\s*(-?[\d,]+)', block)
    parsed['CURRENT BALANCE'] = clean_amount(curr_match.group(1)) if curr_match else 0
    
    emi_match = re.search(r'EMI:\s*([\d,]+)', block)
    parsed['EMI'] = clean_amount(emi_match.group(1)) if emi_match else 0
    
    parsed['MAX DPD'] = extract_max_dpd_streamlit(block)
    return parsed

def personal_row(parsed, customer_name, sr_no):
    status = "Active" if parsed.get('CLOSED', '') == '' else "Closed"
    sanction_date_str = parsed.get('OPENED', '')
    formatted_date = ''
    if sanction_date_str:
        try:
            date_obj = datetime.strptime(sanction_date_str, "%d/%m/%Y")
            formatted_date = date_obj.strftime("%d/%m/%Y")
        except ValueError:
            try:
                date_obj = datetime.strptime(sanction_date_str, "%d-%m-%Y")
                formatted_date = date_obj.strftime("%d/%m/%Y")
            except:
                formatted_date = sanction_date_str
    return {
        'Sr. No.': sr_no,
        'Borrower': customer_name,
        'Type of loan': parsed.get('TYPE', ''),
        'Ownership': parsed.get('OWNERSHIP', ''),
        'Sanction date': formatted_date,
        'Closed date': parsed.get('CLOSED', ''),
        'Sanctioned amount': parsed.get('SANCTIONED', ''),
        'Current balance': parsed.get('CURRENT BALANCE', ''),
        'EMI': parsed.get('EMI', ''),
        'Status': status,
        'Max DPD': parsed.get('MAX DPD', 0)
    }

# ---------- Streamlit App ----------
def cibil_consumer_app():
    st.set_page_config(page_title="CIBIL Analyzer", layout="wide")
    st.title("📑 CIBIL Analyzer")

    st.sidebar.title("📌 How to Use")
    st.sidebar.markdown("""
    **Step 1:** Upload a single PDF credit report — corporate or personal supported.  
    **Step 2:** Click **Generate Excel** when done.  
    **Step 3:** Download your formatted Excel output below!  
    """)

    uploaded_file = st.file_uploader(
        "📂 Upload one CIBIL report (PDF only)",
        type="pdf",
        accept_multiple_files=False
    )

    if uploaded_file:
        file_bytes = uploaded_file.read()
        reader = PdfReader(BytesIO(file_bytes))
        full_text = "".join([page.extract_text() + "\n" for page in reader.pages])

        summary_rows = []
        all_corporate_rows = []
        all_personal_rows = []

        # ---------------- CORPORATE REPORT HANDLING ----------------
        if 'COMMERCIAL CREDIT INFORMATION REPORT' in full_text:
            name_match = re.search(r'Name of Borrower\s*[:\-]?\s*(.+)', full_text)
            if not name_match:
                name_match = re.search(r'Name:\s*[:\-]?\s*(.+)', full_text)
            customer_name = name_match.group(1).strip() if name_match else "Unknown Entity"

            cmr = re.search(r'CMR-\s*([\d,]+)', full_text)
            cmr_score = cmr.group(1) if cmr else "None"
            summary_rows.append({'Name': customer_name, 'Score': cmr_score})

            matches = re.findall(r'Credit Facility Details(.*?)Overdue Details', full_text, re.DOTALL)
            def parse_corporate(data_str):
                patterns = {
                    'TYPE': r'Type:\s*(.+)',
                    'OPENED': r'Sanctioned:\s*(\d{2}-[A-Za-z]{3}-\d{4})',
                    'SANCTIONED': r'Sanctioned INR:\s*([\d,]+)',
                    'CURRENT BALANCE': r'Outstanding Balance:\s*(-?[\d,]+)',
                    'EMI': r'Installment Amount:\s*([\d,]+)',
                    'OVERDUE': r'Overdue:\s*(-?[\d,]+)'
                }
                extracted = {}
                for key, pattern in patterns.items():
                    match = re.search(pattern, data_str, re.IGNORECASE)
                    extracted[key] = match.group(1).strip() if match else ''
                return extracted

            def corporate_row(parsed, sr_no):
                sanction_date_str = parsed.get('OPENED', '')
                formatted_date = ''
                if sanction_date_str:
                    try:
                        date_obj = datetime.strptime(sanction_date_str, "%d-%b-%Y")
                        formatted_date = date_obj.strftime("%d/%m/%Y")
                    except ValueError:
                        formatted_date = sanction_date_str
                return {
                    'Sr. No.': sr_no,
                    'Borrower': customer_name,
                    'Type of loan': parsed.get('TYPE', ''),
                    'Sanction date (DD/MM/YYYY)': formatted_date,
                    'Sanction amount (INR)/ CC outstanding Amount': parsed.get('SANCTIONED', ''),
                    'Monthly EMI (INR)': parsed.get('EMI', ''),
                    'Current outstanding (INR)': parsed.get('CURRENT BALANCE', ''),
                    'Overdue Amount': parsed.get('OVERDUE', '')
                }

            for i, entry in enumerate(matches, start=1):
                parsed = parse_corporate(entry)
                all_corporate_rows.append(corporate_row(parsed, i))

            with st.expander("🏢 Corporate Report Summary"):
                st.dataframe(pd.DataFrame(summary_rows))
                st.dataframe(pd.DataFrame(all_corporate_rows))

            if st.button("✅ Generate Excel"):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="Summary")
                    pd.DataFrame(all_corporate_rows).to_excel(writer, index=False, sheet_name="Corporate_Entity")
                output.seek(0)
                st.download_button("📥 Download Excel", output, uploaded_file.name.replace(".pdf", ".xlsx"),
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # ---------------- PERSONAL REPORT HANDLING ----------------
        else:
            # Consumer Name & Score
            name_match = re.search(r'CONSUMER NAME\s*[:\-]?\s*(.+)|CONSUMER\s*[:\-]?\s*(.+)', full_text, re.IGNORECASE)
            customer_name = (name_match.group(1).strip() if name_match and name_match.group(1)else name_match.group(2).strip() if name_match and name_match.group(2)else "Unknown Individual")
            score_match = re.search(r'CREDITVISION® SCORE\s*[:\-]?\s*(\d{3})', full_text, re.IGNORECASE)
            pscore = score_match.group(1) if score_match else "None"
            summary_rows.append({'Name': customer_name, 'Score': pscore})

            # Detect personal report format
            if 'ACCOUNT INFORMATION' in full_text:
                matches = re.split(r'ACCOUNT INFORMATION', full_text)[1:]
                for i, block in enumerate(matches, 1):
                    parsed = parse_colab_personal_block(block)
                    all_personal_rows.append(personal_row(parsed, customer_name, i))
            else:
                matches = re.findall(r'STATUS(.*?)(?:ACCOUNT DATES|ENQUIRIES:)', full_text, re.DOTALL)
                for i, block in enumerate(matches, 1):
                    parsed = parse_streamlit_personal_block(block)
                    all_personal_rows.append(personal_row(parsed, customer_name, i))

            # Display
            with st.expander("📌 Personal Summary"):
                st.dataframe(pd.DataFrame(summary_rows))
            with st.expander(f"👤 Personal Account Details: {customer_name}"):
                st.dataframe(pd.DataFrame(all_personal_rows))

            # Excel export
            if st.button("✅ Generate Excel"):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="Summary")
                    pd.DataFrame(all_personal_rows).to_excel(writer, index=False, sheet_name=f"{customer_name}"[:31])
                output.seek(0)
                st.download_button("📥 Download Excel", output, uploaded_file.name.replace(".pdf", ".xlsx"),
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Run app
if __name__ == "__main__":
    cibil_consumer_app()
