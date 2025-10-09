import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
from io import BytesIO
from tqdm import tqdm

def crif_app():

    st.set_page_config(page_title="CRIF Report Analyzer", layout="wide")
    st.title("CRIF Report Analyzer")

    # ------------------- Helper Functions -------------------
    def extract_text_from_pdf(file):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        return "\n".join([page.get_text() for page in doc])

    def extract_summary_section(text, start_label, end_label):
        pattern = rf'{start_label}(.*?){end_label}'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    def extract_borrower_details(text):
        details = {}
        details['Company Name'] = re.search(r'Name:\s+(.*)', text)
        details['Legal Constitution'] = re.search(r'Legal Constitution:\s+(.*)', text)
        details['Class of Activity'] = re.search(r'Class of Activity:\s+(.*)', text)
        details['PAN'] = re.search(r'PAN:\s+([A-Z]{5}\d{4}[A-Z])', text)
        details['Date of Incorporation'] = re.search(r'Date of Incorporation:\s+(\d{2}-\d{2}-\d{4})', text)
        details['CIN/LLPIN'] = re.search(r'CIN/LLPIN:\s+([^\s]+)', text)
        details['Loan Amt. Applied for'] = re.search(r'Applied Amount:\s+([^\s]+)', text)
        details = {k: v.group(1).strip() if v else None for k, v in details.items()}

        regd = extract_summary_section(text, "Registered:", "GSTIN:")
        details['Regd. Address'] = regd.replace('\n', ' ') if regd else None

        crif_score = extract_summary_section(text, "DESCRIPTION", "Tip")
        details['CRIF_Score_Details'] = crif_score.replace('\n', ' ') if crif_score else None

        benchmark = extract_summary_section(text, "Tip:", "CRIF HM")
        details['Benchmark Score Tip'] = benchmark.replace('\n', ' ') if benchmark else None

        return details

    def find_all_indexes(text, sub):
        indexes = []
        start_index = 0
        while True:
            index = text.find(sub, start_index)
            if index == -1: 
                break
            indexes.append(index)
            start_index = index + 1
        return indexes

    def payment_history_parser(data):
        lines = [line.strip() for line in data.strip().splitlines() if line.strip()]
        months = lines[:12]
        rest = lines[12:]
        data_dict = {'Month': months}
        i = 0
        while i < len(rest):
            year = rest[i]
            year_values = rest[i+1:i+13]
            data_dict[year] = year_values
            i += 13
        df = pd.DataFrame(data_dict).set_index('Month')
        l = []
        for col in df.columns:
            for idx in df.index:
                if df.loc[idx, col] != '-':
                    l.append(f"{idx} {col} {df.loc[idx, col]}")
        return l

    def parse_loan_details(text):
        result = find_all_indexes(text, "Loan Terms For:")
        loan_details = pd.DataFrame()
        for i in range(len(result)):
            section = text[result[i]:result[i+1]] if i != len(result)-1 else text[result[i]:]
            details = {}
            keys = ['Loan Terms For','Type','DPD/Asset Classification','Info. as of','Sanctioned Date','Sanctioned Amount','Current Balance','Closed Date','Amount Overdue','Suit Filed Status','Wilful Defaulter']
            for k in keys:
                match = re.search(rf'{k}:\s*(.*)', section)
                details[k] = match.group(1).strip() if match else None
            ph = extract_summary_section(section, "Payment History/Asset Classification:", "Suit Filed & Wilful Default")
            details['Payment History/Asset Classification'] = payment_history_parser(ph) if ph else None
            loan_details = pd.concat([loan_details, pd.DataFrame([details])], ignore_index=True)
        return loan_details

    def parse_inquiry_summary(text):
        lines = text.split('\n')
        try:
            start_idx = next(i for i, l in enumerate(lines) if l == 'Inquiries (reported for past 24 months)')
            end_idx = next(i for i, l in enumerate(lines) if l == 'Additional Inquiry Details')
        except StopIteration:
            return pd.DataFrame()
        data_lines = lines[start_idx+1:end_idx]
        headers = data_lines[:6]
        data = data_lines[6:]
        records = []
        current = []
        for item in data:
            if item == 'XXXX' and current:
                records.append(current)
                current = []
            current.append(item)
        if current: 
            records.append(current)
        # normalize length
        for i, r in enumerate(records):
            if len(r) < len(headers):
                records[i] += [None]*(len(headers)-len(r))
            elif len(r) > len(headers):
                records[i] = r[:len(headers)]
        return pd.DataFrame(records, columns=headers)

    def parse_borrower_summary(text):
        summary_text = extract_summary_section(text, "Borrower Summary", "Credit Profile Summary")
        if not summary_text: return pd.DataFrame()
        columns = ["Type","Lender","Total Accts","Live Accts","Delinquent Accts","Sanctioned Amt","Outstanding Amt","Overdue Amt","PAR (90+)"]
        lines = summary_text.strip().split('\n')
        data_rows = []
        for inst_label in ["Your Institution", "Other Institution"]:
            idx = next((i for i, l in enumerate(lines) if l == inst_label), -1)
            if idx != -1:
                row = [lines[idx].strip()]
                row += [float(x.strip()) if x.replace('.','',1).isdigit() else x.strip() for x in lines[idx+1:idx+9]]
                data_rows.append(row)
        df = pd.DataFrame(data_rows, columns=columns)
        return df

    def parse_credit_summary(text):
        summary_text = extract_summary_section(text, "Credit Profile Summary", "Additional Status")
        if not summary_text: return pd.DataFrame()
        columns = ['Institution','Credit Facility','STD Acct(#)','STD O/S Amt','SMA Acct(#)','SMA O/S Amt',
                   'SUB Acct(#)','SUB O/S Amt','DBT Acct(#)','DBT O/S Amt','LOS Acct(#)','LOS O/S Amt',
                   'Inquiries <3 m','Inquiries 3-6 m','Inquiries 6-9 m','Inquiries 9-12 m','Inquiries >12 m']
        # Dummy parsing (you can improve further)
        data = []
        return pd.DataFrame(data, columns=columns)

    # ------------------- Streamlit UI -------------------
    uploaded_file = st.file_uploader("Upload CRIF PDF", type="pdf")
    if uploaded_file:
        text = extract_text_from_pdf(uploaded_file)
        borrower_details_df = pd.DataFrame([extract_borrower_details(text)])
        borrower_summary_df = parse_borrower_summary(text)
        credit_summary_df = parse_credit_summary(text)
        loan_details_df = parse_loan_details(text)
        inquiry_summary_df = parse_inquiry_summary(text)

        # Display in tabs
        with st.expander("Borrower Details"):
            st.dataframe(borrower_details_df)

        with st.expander("Borrower Summary"):
            st.dataframe(borrower_summary_df)

        with st.expander("Credit Summary"):
            st.dataframe(credit_summary_df)

        with st.expander("Loan Details"):
            st.dataframe(loan_details_df)

        with st.expander("Inquiry Summary"):
            st.dataframe(inquiry_summary_df)

        # Download Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            borrower_details_df.T.to_excel(writer, sheet_name="Borrower Details", header=False)
            borrower_summary_df.to_excel(writer, sheet_name="Borrower Summary", index=False)
            credit_summary_df.to_excel(writer, sheet_name="Credit Summary", index=False)
            loan_details_df.to_excel(writer, sheet_name="Loan Details", index=False)
            inquiry_summary_df.to_excel(writer, sheet_name="Inquiry Summary", index=False)
        output.seek(0)
        st.download_button("Download Excel", data=output, file_name="Parsed_CRIF.xlsx")

# Run the app
if __name__ == "__main__":
    crif_app()
