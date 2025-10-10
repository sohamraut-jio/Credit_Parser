import streamlit as st
import pandas as pd
import re
from PyPDF2 import PdfReader
from io import BytesIO
from datetime import datetime

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

            # Auto-extract corporate name
            name_match = re.search(r'Name of Borrower\s*[:\-]?\s*(.+)', full_text)
            if not name_match:
                name_match = re.search(r'Company Name\s*[:\-]?\s*(.+)', full_text)
            customer_name = name_match.group(1).strip() if name_match else "Unknown Entity"

            app_type = "Applicant"  # For internal use, can be removed if not needed

            # Extract CMR score
            cmr = re.search(r'CMR-\s*([\d,]+)', full_text)
            cmr_score = cmr.group(1) if cmr else "None"

            summary_rows.append({
                'Name': customer_name,
                'Score': cmr_score
            })

            # Extract each loan block
            matches = re.findall(r'Credit Facility Details(.*?)Overdue Details', full_text, re.DOTALL)

            def parse_corporate(data_str):
                patterns = {
                    'TYPE': r'Type:\s*(.+)',
                    'OPENED': r'Sanctioned:\s*(\d{2}-[A-Za-z]{3}-\d{4})',
                    'SANCTIONED': r'Sanctioned INR:\s*([\d,]+)',
                    'CURRENT BALANCE': r'Outstanding Balance:\s*(-?[\d,]+)',
                    'EMI': r'Installment Amount:\s*([\d,]+)',
                    'REPAYMENT TENURE': r'Repayment Tenure:\s*(\d+)',
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
                    'Financiers': '',
                    'Sanction date (DD/MM/YYYY)': formatted_date,
                    'Seasoning': '',
                    'Sanction amount (INR)/ CC outstanding Amount': parsed.get('SANCTIONED', ''),
                    'Monthly EMI (INR)': parsed.get('EMI', ''),
                    'Current outstanding (INR)': parsed.get('CURRENT BALANCE', ''),
                    'Overdue Amount': parsed.get('OVERDUE', ''),
                    'Max DPD in L12 Months': '',
                    'Max DPD in L36 Months': ''
                }

            for i, entry in enumerate(matches, start=1):
                parsed = parse_corporate(entry)
                all_corporate_rows.append(corporate_row(parsed, i))

            # Display corporate data
            with st.expander("🏢 Corporate Report Summary"):
                summary_df = pd.DataFrame(summary_rows)
                st.dataframe(summary_df)
                corp_df = pd.DataFrame(all_corporate_rows)
                st.dataframe(corp_df)

            # Excel export
            if st.button("✅ Generate Excel"):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, index=False, sheet_name="Summary")
                    corp_df.to_excel(writer, index=False, sheet_name="Corporate_Entity")
                output.seek(0)

                excel_filename = uploaded_file.name.replace(".pdf", ".xlsx")
                st.success("🎉 Excel file generated successfully!")
                st.download_button(
                    label=f"📥 Download {excel_filename}",
                    data=output,
                    file_name=excel_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        # ---------------- PERSONAL REPORT HANDLING ----------------
        else:
            # Auto-extract consumer name
            name_match = re.search(r'CONSUMER:\s*(.+)', full_text)
            customer_name = name_match.group(1).strip() if name_match else "Unknown Individual"

            # Extract personal score
            score_match = re.search(r'CREDITVISION® SCORE\s*(\d{3})', full_text)
            pscore = score_match.group(1) if score_match else "None"

            summary_rows.append({
                'Name': customer_name,
                'Score': pscore
            })

            # Extract each loan block
            matches = re.findall(r'STATUS(.*?)(?:ACCOUNT DATES|ENQUIRIES:)', full_text, re.DOTALL)

            def parse_personal(data_str):
                patterns = {
                    'TYPE': r'TYPE:\s*(.+)',
                    'OWNERSHIP': r'OWNERSHIP:\s*(.+?)(?:OPENED|\n|LAST|REPORTED|CLOSED|PMT|$)',
                    'OPENED': r'OPENED:\s*(\d{2}-\d{2}-\d{4})',
                    'SANCTIONED': r'SANCTIONED:\s*([\d,]+)',
                    'CURRENT BALANCE': r'CURRENT BALANCE:\s*(-?[\d,]+)',
                    'EMI': r'EMI:\s*([\d,]+)',
                    'CLOSED': r'CLOSED:\s*(.+)'
                }
                extracted = {}
                type_match = re.search(patterns['TYPE'], data_str, re.IGNORECASE)
                loan_type = type_match.group(1).strip() if type_match else ''
                extracted['TYPE'] = loan_type

                if loan_type == 'CREDIT CARD':
                    patterns['SANCTIONED'] = r'CREDIT LIMIT:\s*([\d,]+)'

                for key, pattern in patterns.items():
                    match = re.search(pattern, data_str, re.IGNORECASE)
                    extracted[key] = match.group(1).strip() if match else ''
                return extracted

            def personal_row(parsed, sr_no):
                status = "Active" if parsed.get('CLOSED', '') == '' else "Closed"
                sanction_date_str = parsed.get('OPENED', '')
                formatted_date = ''
                if sanction_date_str:
                    try:
                        date_obj = datetime.strptime(sanction_date_str, "%d-%m-%Y")
                        formatted_date = date_obj.strftime("%d/%m/%Y")
                    except ValueError:
                        formatted_date = sanction_date_str

                return {
                    'Sr. No.': sr_no,
                    'Borrower': customer_name,
                    'Type of loan': parsed.get('TYPE', ''),
                    'Financiers': '',
                    'Sanction date (DD/MM/YYYY)': formatted_date,
                    'Seasoning': '',
                    'Sanction amount (INR)/ CC outstanding Amount': parsed.get('SANCTIONED', ''),
                    'Monthly EMI (INR)': parsed.get('EMI', ''),
                    'Current outstanding (INR)': parsed.get('CURRENT BALANCE', ''),
                    'STATUS': status,
                    'Max DPD in L12 Months': '',
                    'Max DPD in L36 Months': '',
                    'Ownership type': parsed.get('OWNERSHIP', '')
                }

            for i, entry in enumerate(matches, start=1):
                parsed = parse_personal(entry)
                all_personal_rows.append(personal_row(parsed, i))

            # Display personal data
            with st.expander("📌 Summary"):
                summary_df = pd.DataFrame(summary_rows)
                st.dataframe(summary_df)

            with st.expander(f"👤 Personal Details: {customer_name}"):
                personal_df = pd.DataFrame(all_personal_rows)
                st.dataframe(personal_df)

            # Excel export
            if st.button("✅ Generate Excel"):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, index=False, sheet_name="Summary")
                    personal_df.to_excel(writer, index=False, sheet_name=f"{customer_name}"[:31])
                output.seek(0)

                excel_filename = uploaded_file.name.replace(".pdf", ".xlsx")
                st.success("🎉 Excel file generated successfully!")
                st.download_button(
                    label=f"📥 Download {excel_filename}",
                    data=output,
                    file_name=excel_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# Run the app
if __name__ == "__main__":
    cibil_consumer_app()
