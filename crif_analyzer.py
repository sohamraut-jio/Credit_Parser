import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
from io import BytesIO
from tqdm import tqdm

def crif_app():

    st.sidebar.title("📌 How to Use")
    st.sidebar.markdown("""
    **Step 1:** Upload PDF credit report — corporate supported.
    
    **Step 2:** Click **Generate Excel** when done.
    
    **Step 3:** Download your output file from the download button below!
    
    """)
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
    
        details['Regd. Address'] = extract_summary_section(text,"Registered:","GSTIN:").replace('\n',' ') if extract_summary_section(text,"Registered:","GSTIN:") else None
        details['CRIF_Score_Details'] = extract_summary_section(text,"DESCRIPTION","Tip").replace('\n',' ') if extract_summary_section(text,"DESCRIPTION","Tip") else None
        details['Benchmark Score Tip'] = extract_summary_section(text,"Tip:","CRIF HM").replace('\n',' ') if extract_summary_section(text,"Tip:","CRIF HM") else None
        return details
    
    def find_all_indexes(text, sub):
        indexes = []
        start_index = 0
        while True:
            index = text.find(sub, start_index)
            if index == -1: break
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
        for i in df.columns:
            for j in df.index:
                if df.loc[j,i]!='-':
                    l.append(j+' '+str(i)+' '+df.loc[j,i])
        return l
    
    def parse_loan_details(text):
        result = find_all_indexes(text, "Loan Terms For:")
        loan_details = pd.DataFrame()
        for i in range(len(result)):
            if i != len(result)-1:
                section = text[result[i]:result[i+1]]
            else:
                section = text[result[i]:]
            details = {}
            keys = ['Loan Terms For','Type','DPD/Asset Classification','Info. as of','Sanctioned Date','Sanctioned Amount','Current Balance','Closed Date','Amount Overdue','Suit Filed Status','Wilful Defaulter']
            for k in keys:
                match = re.search(rf'{k}:\s*(.*)', section)
                details[k] = match.group(1).strip() if match else None
            details['Payment History/Asset Classification'] = extract_summary_section(section,"Payment History/Asset Classification:","Suit Filed & Wilful Default")
            temp = pd.DataFrame([details])
            loan_details = pd.concat([loan_details,temp], ignore_index=True)
        loan_details['Payment History/Asset Classification'] = loan_details['Payment History/Asset Classification'].apply(lambda x: payment_history_parser(x) if x else None)
        return loan_details
    
    def parse_inquiry_summary(text):
        a = text.split('\n')
        try:
            inquiry_initial_index = [i for i in range(len(a)) if a[i] == 'Inquiries (reported for past 24 months)'][0]
            inquiry_end_index = [i for i in range(len(a)) if a[i] == 'Additional Inquiry Details'][0]
        except IndexError:
            return pd.DataFrame()
        inquiry_list = a[inquiry_initial_index+1:inquiry_end_index]
        data_list = inquiry_list
        headers = data_list[:6]
        data = data_list[6:]
        records = []
        current = []
        for item in data:
            if item == 'XXXX' and current:
                records.append(current)
                current = []
            current.append(item)
        if current: records.append(current)
        for i, r in enumerate(records):
            if len(r) < len(headers):
                records[i] = r + [None]*(len(headers)-len(r))
            elif len(r) > len(headers):
                records[i] = r[:len(headers)]
        return pd.DataFrame(records, columns=headers)
    
    def parse_borrower_summary(text):
        # Similar to raw code: Your Institution / Other Institution parsing
        text_input = extract_summary_section(text, "Borrower Summary", "Credit Profile Summary")
        if not text_input: return pd.DataFrame()
        columns = ["Type","Lender","Total Accts","Live Accts","Delinquent Accts","Sanctioned Amt","Outstanding Amt","Overdue Amt","PAR (90+)"]
        lines = text_input.strip().split('\n')
        data_rows = []
        your_inst = next((i for i,l in enumerate(lines) if l=="Your Institution"), -1)
        other_inst = next((i for i,l in enumerate(lines) if l=="Other Institution"), -1)
        if your_inst!=-1:
            data_rows.append([
                lines[your_inst].strip(),
                int(lines[your_inst+1].strip()),
                int(lines[your_inst+2].strip()),
                int(lines[your_inst+3].strip()),
                int(lines[your_inst+4].strip()),
                lines[your_inst+5].strip(),
                float(lines[your_inst+6].strip()),
                float(lines[your_inst+7].strip()),
                float(lines[your_inst+8].strip())
            ])
        if other_inst!=-1:
            data_rows.append([
                lines[other_inst].strip(),
                int(lines[other_inst+1].strip()),
                int(lines[other_inst+2].strip()),
                int(lines[other_inst+3].strip()),
                lines[other_inst+4].strip(),
                lines[other_inst+5].strip(),
                float(lines[other_inst+6].strip()),
                float(lines[other_inst+7].strip()),
                float(lines[other_inst+8].strip())
            ])
        df = pd.DataFrame(data_rows, columns=columns)
        df['Sanctioned Amt (Value)'] = df['Sanctioned Amt'].apply(lambda x: float(re.search(r'(\d+\.?\d*)', str(x)).group(1)) if pd.notnull(x) and re.search(r'(\d+\.?\d*)', str(x)) else None)
        df['Sanctioned Amt (Percentage)'] = df['Sanctioned Amt'].apply(lambda x: int(re.search(r'\((\d+)%\)', str(x)).group(1)) if pd.notnull(x) and re.search(r'\((\d+)%\)', str(x)) else None)
        return df.drop(columns=['Sanctioned Amt'])
    
    def parse_credit_summary(text):
        text_input = extract_summary_section(text,"Credit Profile Summary","Additional Status")
        if not text_input: return pd.DataFrame()
        text_input = text_input.split('(%) represents utilization')[0]
        asset_classes = ['STD','SMA','SUB','DBT','LOS']
        inquiry_periods = ['<3 m','3-6 m','6-9 m','9-12 m','>12 m']
        facilities = ['Working Cap','Term Loan','Non-Funded','Forex','OTHERS']
        columns = ['Institution','Credit Facility']
        for cls in asset_classes:
            columns.extend([f'{cls} Acct(#)',f'{cls} O/S Amt'])
        columns.extend([f'Inquiries {p}' for p in inquiry_periods])
        sections = re.split(r'(Your Institution|Other Institution)', text_input)
        data=[]
        for i in range(1,len(sections),2):
            inst=sections[i].strip()
            content=sections[i+1].strip().splitlines()
            content=[val for val in content if not re.fullmatch(r"\(\d+(\.\d+)?%\)",val)]
            current=[]
            for line in content:
                line=line.strip()
                if line in facilities:
                    if current:
                        numbers=[item for item in current if item not in ('')]
                        row=[inst,facility]
                        for j in range(5):
                            acct=numbers[j*2] if len(numbers)>j*2 else '-'
                            amt=numbers[j*2+1] if len(numbers)>j*2+1 else '-'
                            row.extend([acct,amt])
                        inquiries=numbers[10:15]
                        while len(inquiries)<5: inquiries.append('-')
                        row.extend(inquiries)
                        data.append(row)
                        current=[]
                    facility=line
                elif line: current.append(line)
            if current:
                numbers=[item for item in current]
                row=[inst,facility]
                for j in range(5):
                    acct=numbers[j*2] if len(numbers)>j*2 else '-'
                    amt=numbers[j*2+1] if len(numbers)>j*2+1 else '-'
                    row.extend([acct,amt])
                inquiries=numbers[10:15]
                while len(inquiries)<5: inquiries.append('-')
                row.extend(inquiries)
                data.append(row)
        return pd.DataFrame(data,columns=columns)
    
    # ------------------- Streamlit UI -------------------
    
    uploaded_file = st.file_uploader("Upload CRIF PDF", type="pdf")
    
    if uploaded_file:
        with st.spinner("Extracting data... please wait"):
            text = extract_text_from_pdf(uploaded_file)
        
            borrower_details_df = pd.DataFrame([extract_borrower_details(text)])
            borrower_summary_df = parse_borrower_summary(text)
            credit_summary_df = parse_credit_summary(text)
            loan_details_df = parse_loan_details(text)
            inquiry_summary_df = parse_inquiry_summary(text)
        # -----------------------
        # Display sections
        # -----------------------
        st.success("✅ Extraction completed!")
    
        # Display in collapsible tabs
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
        st.download_button("Download Excel", data=output, file_name=f"Parsed_CRIF.xlsx")

# Run the app
if __name__ == "__main__":
    crif_app()
