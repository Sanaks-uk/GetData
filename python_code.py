import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from lxml import etree
import time
from datetime import datetime, timedelta
import math

# ===== 1️⃣ Page config and CSS styling =====
st.set_page_config(page_title="EPO Patent Data", layout="centered")
st.markdown(
    """
    <style>
    /* Page background */
    .stApp {
        background-color: #FFE3EB;
    }
    /* Center container */
    .centered-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    /* Custom Run button color */
    div.stButton > button:first-child {
        background-color: #FF69B4;
        color: white;
        height: 3em;
        width: 150px;
        font-size: 16px;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📄 EPO Patent & Register Data")
st.markdown("Extract patent data for date ranges - Built for large-scale data extraction")

# ===== 2️⃣ Authentication Function =====
def get_token(client_id, client_secret):
    """Get EPO access token"""
    url = "https://ops.epo.org/3.2/auth/accesstoken"
    
    try:
        response = requests.post(
            url,
            auth=HTTPBasicAuth(client_id, client_secret),
            data={'grant_type': 'client_credentials'},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            st.error(f"Auth failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

# ===== 3️⃣ XML Namespaces =====
ns = {
    "ops": "http://ops.epo.org",
    "ex": "http://www.epo.org/exchange",
    "epo": "http://www.epo.org/exchange",
    "xlink": "http://www.w3.org/1999/xlink"
}

# ===== 4️⃣ Helper Functions =====
def safe_xpath(root, xpath_str, namespaces, return_all=False):
    try:
        res = root.xpath(xpath_str, namespaces=namespaces)
        if return_all:
            return res
        return res[0].strip() if res and hasattr(res[0], 'strip') else (res[0] if res else "")
    except Exception:
        return [] if return_all else ""

def fetch_register_data(doc_num, headers):
    """Fetch register data (representatives, oppositions, appeals)"""
    data = {
        "RepName": "", "RepCountry": "",
        "OpponentName": "", "OppositionFilingDate": "",
        "AppealNr": "", "AppealResult": "", "AppealDate": ""
    }
    
    endpoints = {
        "rep": f"https://register.epo.org/api/publication/epodoc/{doc_num}/representatives",
        "opp": f"https://register.epo.org/api/publication/epodoc/{doc_num}/oppositions",
        "appeal": f"https://register.epo.org/api/publication/epodoc/{doc_num}/appeals"
    }
    
    for key, url in endpoints.items():
        try:
            time.sleep(1)  # Rate limiting
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200 and resp.content:
                try:
                    j = resp.json()
                except ValueError:
                    continue
                    
                if key == "rep" and j.get("representatives"):
                    r = j["representatives"][0]
                    data["RepName"] = r.get("name", "")
                    data["RepCountry"] = r.get("countryCode", "")
                elif key == "opp" and j.get("oppositions"):
                    o = j["oppositions"][0]
                    data["OpponentName"] = o.get("name", "")
                    data["OppositionFilingDate"] = o.get("dateFiled", "")
                elif key == "appeal" and j.get("appeals"):
                    a = j["appeals"][0]
                    data["AppealNr"] = a.get("number", "")
                    data["AppealResult"] = a.get("result", "")
                    data["AppealDate"] = a.get("resultDate", "")
        except Exception:
            continue  # Skip on error
            
    return data

def extract_biblio_data(doc_num, headers):
    """Extract bibliographic data with better error handling"""
    biblio_urls = [
        f"https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/{doc_num}/biblio",
        f"https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/{doc_num}/biblio"
    ]
    
    for biblio_url in biblio_urls:
        try:
            time.sleep(1)  # Rate limiting
            b_resp = requests.get(biblio_url, headers=headers, timeout=15)
            
            if b_resp.status_code == 404:
                continue
            if b_resp.status_code != 200 or not b_resp.content:
                continue
                
            b_root = etree.fromstring(b_resp.content)
            
            # Try multiple XPath patterns for publication date
            pub_date_paths = [
                ".//ex:publication-reference/ex:document-id[@document-id-type='epodoc']/ex:date/text()",
                ".//ex:publication-reference/ex:document-id[@document-id-type='docdb']/ex:date/text()", 
                ".//ex:publication-reference/ex:document-id/ex:date/text()",
                ".//ex:document-id[@document-id-type='epodoc']/ex:date/text()",
                ".//ex:document-id[@document-id-type='docdb']/ex:date/text()",
                ".//ex:date/text()",
                "//ex:date/text()"
            ]
            
            pub_date = ""
            for path in pub_date_paths:
                pub_date = safe_xpath(b_root, path, ns)
                if pub_date:
                    break
            
            # Try multiple XPath patterns for applicant name
            applicant_name_paths = [
                ".//ex:applicants/ex:applicant/ex:applicant-name/ex:name/text()",
                ".//ex:applicants/ex:applicant/ex:name/text()", 
                ".//ex:applicant/ex:applicant-name/ex:name/text()",
                ".//ex:applicant/ex:name/text()",
                ".//ex:applicant-name/ex:name/text()",
                "//ex:applicant-name/ex:name/text()",
                "//ex:applicant//ex:name/text()"
            ]
            
            applicant_name = ""
            for path in applicant_name_paths:
                applicant_name = safe_xpath(b_root, path, ns)
                if applicant_name:
                    break
            
            # Try multiple XPath patterns for applicant country
            applicant_country_paths = [
                ".//ex:applicants/ex:applicant/ex:addressbook/ex:address/ex:country/text()",
                ".//ex:applicants/ex:applicant/ex:residence/ex:country/text()",
                ".//ex:applicant/ex:addressbook/ex:address/ex:country/text()",
                ".//ex:applicant/ex:residence/ex:country/text()", 
                ".//ex:address/ex:country/text()",
                "//ex:residence/ex:country/text()",
                "//ex:country/text()"
            ]
            
            applicant_country = ""
            for path in applicant_country_paths:
                applicant_country = safe_xpath(b_root, path, ns)
                if applicant_country:
                    break
            
            return pub_date, applicant_name, applicant_country
            
        except Exception:
            continue
    
    return "", "", ""

def extract_cpc_data(doc_num, headers):
    """Extract CPC classification data"""
    cpc_urls = [
        f"https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/{doc_num}/classifications",
        f"https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/{doc_num}/classifications"
    ]
    
    for cpc_url in cpc_urls:
        try:
            time.sleep(1)  # Rate limiting
            cpc_resp = requests.get(cpc_url, headers=headers, timeout=15)
            
            if cpc_resp.status_code == 404:
                continue
            if cpc_resp.status_code != 200 or not cpc_resp.content:
                continue
                
            cpc_root = etree.fromstring(cpc_resp.content)
            
            # Try multiple CPC paths
            cpc_paths = [
                "//ex:classification-cpc",
                "//ex:cpc", 
                ".//ex:classification-cpc",
                "//ex:classification"
            ]
            
            cpc_main = ""
            cpc_full = []
            
            for cpc_path in cpc_paths:
                cpcs = cpc_root.xpath(cpc_path, namespaces=ns)
                if cpcs:
                    for c in cpcs:
                        # Try different symbol paths
                        symbol_paths = [
                            ".//ex:symbol/text()", 
                            ".//ex:cpc-symbol/text()",
                            ".//text()[normalize-space()]",
                            "./text()"
                        ]
                        
                        code = ""
                        for symbol_path in symbol_paths:
                            results = c.xpath(symbol_path, namespaces=ns)
                            if results:
                                code = results[0].strip() if hasattr(results[0], 'strip') else str(results[0]).strip()
                                if code:
                                    break
                        
                        if code:
                            code_clean = str(code).replace(" ", "").replace("/", "")
                            cpc_full.append(code_clean)
                            if not cpc_main and len(code_clean) >= 4:
                                cpc_main = code_clean[:4]
                    break
            
            return cpc_main, cpc_full
            
        except Exception:
            continue
    
    return "", []

# ===== 5️⃣ Main Patent Search Function =====
def search_patents_comprehensive(token, start_date, end_date, max_patents=1000, batch_size=5, include_register=False):
    """Comprehensive patent search with biblio and optional register data"""
    
    # Setup
    headers = {"Authorization": f"Bearer {token}"}
    search_url = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
    
    # Create query for date range
    query = f'pd within "{start_date} {end_date}"'
    
    # Get total results first
    params = {"q": query, "Range": f"1-{batch_size}"}
    try:
        search_resp = requests.get(search_url, headers=headers, params=params, timeout=30)
        search_resp.raise_for_status()
        search_root = etree.fromstring(search_resp.content)
        total_results = int(search_root.xpath("string(//ops:biblio-search/@total-result-count)", namespaces=ns))
        st.info(f"📊 Found {total_results} patents in date range")
    except Exception as e:
        st.error(f"Failed to get search results: {e}")
        return []
    
    # Process batches
    all_records = []
    total_to_fetch = min(total_results, max_patents)
    total_batches = math.ceil(total_to_fetch / batch_size)
    
    progress_bar = st.progress(0)
    status_container = st.empty()
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size + 1
        end_idx = min(start_idx + batch_size - 1, total_to_fetch)
        
        status_container.text(f"📥 Processing batch {batch_num+1}/{total_batches} (records {start_idx}-{end_idx})")
        
        # Get batch (use existing results for first batch)
        if batch_num == 0:
            batch_root = search_root
        else:
            try:
                params = {"q": query, "Range": f"{start_idx}-{end_idx}"}
                batch_resp = requests.get(search_url, headers=headers, params=params, timeout=30)
                if batch_resp.status_code != 200:
                    st.warning(f"Batch {batch_num+1} failed: {batch_resp.status_code}")
                    continue
                batch_root = etree.fromstring(batch_resp.content)
                time.sleep(1)  # Rate limiting between batches
            except Exception as e:
                st.warning(f"Batch {batch_num+1} error: {e}")
                continue
        
        # Process documents in batch
        documents = batch_root.xpath("//ex:exchange-document", namespaces=ns)
        
        for i, doc in enumerate(documents):
            if len(all_records) >= max_patents:
                break
                
            # Get document number
            doc_num = doc.attrib.get("doc-number")
            if not doc_num:
                doc_id_elem = doc.xpath(".//ex:document-id[@document-id-type='epodoc']", namespaces=ns)
                if doc_id_elem:
                    doc_num = safe_xpath(doc_id_elem[0], "./ex:doc-number", ns)
            
            oid = doc.attrib.get("doc-id", "")
            
            if not doc_num:
                continue
            
            # Extract basic info from search results
            try:
                pub_ref = doc.xpath(".//ex:publication-reference/ex:document-id[@document-id-type='epodoc']", namespaces=ns)
                search_pub_date = ""
                search_applicant = ""
                full_doc_number = ""
                
                if pub_ref:
                    country = safe_xpath(pub_ref[0], "./ex:country/text()", ns)
                    number = safe_xpath(pub_ref[0], "./ex:doc-number/text()", ns) 
                    kind = safe_xpath(pub_ref[0], "./ex:kind/text()", ns)
                    date_elem = pub_ref[0].xpath("./ex:date/text()", namespaces=ns)
                    
                    if country and number:
                        full_doc_number = f"{country}{number}{kind}" if kind else f"{country}{number}"
                        
                    if date_elem:
                        search_pub_date = date_elem[0] if date_elem[0] else ""
                
                # Get applicant from search results  
                applicant_elem = doc.xpath(".//ex:applicant-name/ex:name", namespaces=ns)
                if applicant_elem and hasattr(applicant_elem[0], 'text') and applicant_elem[0].text:
                    search_applicant = applicant_elem[0].text.strip()
                    
                # Get applicant country from search results
                search_applicant_country = ""
                country_elem = doc.xpath(".//ex:applicant/ex:addressbook/ex:address/ex:country", namespaces=ns)
                if country_elem and hasattr(country_elem[0], 'text') and country_elem[0].text:
                    search_applicant_country = country_elem[0].text.strip()
                
                # Update doc_num to full format if found
                if full_doc_number:
                    doc_num = full_doc_number
                    
            except Exception:
                search_pub_date, search_applicant, search_applicant_country = "", "", ""
            
            # Fetch detailed Biblio data
            pub_date, applicant_name, applicant_country = extract_biblio_data(doc_num, headers)
            
            # Use search results as fallback
            if not pub_date:
                pub_date = search_pub_date
            if not applicant_name:
                applicant_name = search_applicant
            if not applicant_country:
                applicant_country = search_applicant_country
            
            # Fetch CPC classifications
            cpc_main, cpc_full = extract_cpc_data(doc_num, headers)
            
            # Fetch Register data if requested
            reg_data = {}
            if include_register:
                reg_data = fetch_register_data(doc_num, headers)
            
            # Create record
            record = {
                "OID": oid,
                "Document_Number": doc_num,
                "Publication_Date": pub_date,
                "Applicant_Name": applicant_name,
                "Applicant_Country": applicant_country,
                "CPC_Main": cpc_main,
                "CPC_Full": ";".join(cpc_full),
                **reg_data
            }
            
            all_records.append(record)
            
        # Update progress
        progress = min((len(all_records) / max_patents) * 100, 100)
        progress_bar.progress(int(progress))
        
        if len(all_records) >= max_patents:
            break
    
    status_container.text("✅ Data extraction complete!")
    return all_records

# ===== 6️⃣ User Interface =====
col1, col2, col3 = st.columns([1,2,1])

with col2:
    st.markdown("### 🔐 Authentication")
    client_id = st.text_input("Client ID", key="client_id")
    client_secret = st.text_input("Client Secret", type="password", key="client_secret")
    
    st.markdown("### 📅 Date Range")
    col_date1, col_date2 = st.columns(2)
    
    with col_date1:
        start_date = st.date_input("Start Date", value=datetime(2024, 1, 1))
    with col_date2:
        end_date = st.date_input("End Date", value=datetime(2024, 12, 31))
    
    st.markdown("### ⚙️ Settings")
    max_patents = st.number_input("Maximum Patents", min_value=100, max_value=10000, value=1000, step=100,
                                 help="Maximum number of patents to extract")
    
    batch_size = st.selectbox("Batch Size", options=[2, 5, 10], index=2,
                             help="Number of patents per API call")
    
    include_register = st.checkbox("Include Register Data", value=False,
                                  help="Include representatives, oppositions, and appeals data (slower)")

# ===== 7️⃣ Run Button =====
with col2:
    run_button = st.button("🚀 Extract Patent Data")

if run_button:
    if not client_id or not client_secret:
        st.error("❌ Please enter your EPO API credentials")
    else:
        # Format dates for EPO API
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        st.success(f"🔄 Extracting patents from {start_date} to {end_date}")
        
        # Step 1: Authentication
        main_progress = st.progress(0)
        main_status = st.empty()
        
        main_status.text("🔐 Authenticating...")
        token = get_token(client_id, client_secret)
        main_progress.progress(20)
        
        if token:
            st.success("✅ Authentication successful!")
            
            # Step 2: Extract data
            main_status.text("📥 Starting comprehensive data extraction...")
            main_progress.progress(40)
            
            patents = search_patents_comprehensive(
                token, start_str, end_str, max_patents, batch_size, include_register
            )
            main_progress.progress(100)
            
            if patents:
                # Create DataFrame
                df = pd.DataFrame(patents)
                main_status.text("✅ Data extraction complete!")
                
                # Display results
                st.success(f"🎉 Successfully extracted {len(df)} patents!")
                
                # Show preview
                st.markdown("### 📊 Data Preview")
                st.dataframe(df.head(10), use_container_width=True)
                
                # Statistics
                st.markdown("### 📈 Statistics")
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                
                with col_stat1:
                    st.metric("Total Patents", len(df))
                with col_stat2:
                    countries = df['Applicant_Country'].replace('', 'Unknown').nunique()
                    st.metric("Countries", countries)
                with col_stat3:
                    st.metric("Date Range", f"{(end_date - start_date).days} days")
                with col_stat4:
                    valid_applicants = len(df[df['Applicant_Name'].str.strip() != ''])
                    st.metric("With Applicants", valid_applicants)
                
                # Data quality metrics
                st.markdown("### 📋 Data Quality")
                col_qual1, col_qual2, col_qual3, col_qual4 = st.columns(4)
                
                with col_qual1:
                    complete_dates = len(df[df['Publication_Date'].str.strip() != ''])
                    st.metric("With Pub Dates", f"{complete_dates} ({complete_dates/len(df)*100:.1f}%)")
                with col_qual2:
                    complete_cpc = len(df[df['CPC_Main'].str.strip() != ''])
                    st.metric("With CPC", f"{complete_cpc} ({complete_cpc/len(df)*100:.1f}%)")
                with col_qual3:
                    if include_register:
                        with_reps = len(df[df.get('RepName', pd.Series([''] * len(df))).str.strip() != ''])
                        st.metric("With Reps", f"{with_reps} ({with_reps/len(df)*100:.1f}%)")
                    else:
                        st.metric("Register Data", "Not included")
                with col_qual4:
                    complete_records = len(df[(df['Publication_Date'].str.strip() != '') & 
                                             (df['Applicant_Name'].str.strip() != '') & 
                                             (df['Applicant_Country'].str.strip() != '')])
                    st.metric("Complete Biblio", f"{complete_records} ({complete_records/len(df)*100:.1f}%)")
                
                # Download button
                csv = df.to_csv(index=False).encode('utf-8')
                download_filename = f"epo_patents_comprehensive_{start_str}_{end_str}.csv"
                if include_register:
                    download_filename = f"epo_patents_full_{start_str}_{end_str}.csv"
                
                st.download_button(
                    label=f"📥 Download {len(df)} Patents CSV",
                    data=csv,
                    file_name=download_filename,
                    mime='text/csv'
                )
                
            else:
                st.warning("⚠️ No patents found for the specified date range")
                main_progress.progress(100)
        else:
            st.error("❌ Authentication failed - check your credentials")
            main_progress.progress(0)

# ===== 8️⃣ Help Section =====
st.markdown("---")
with st.expander("ℹ️ How to use this tool"):
    st.markdown("""
    ### 📋 Setup Instructions:
    1. **Get EPO API credentials** from https://developers.epo.org/
    2. **Enter your Client ID and Secret** above
    3. **Select date range** for patent search
    4. **Set maximum patents** to extract (recommended: 1000-5000)
    5. **Choose whether to include Register data** (representatives, oppositions, appeals)
    6. **Click Extract** and wait for results
    
    ### 🚀 Features:
    - **Comprehensive Data**: Bibliographic data, CPC classifications, optional register data
    - **Smart Fallbacks**: Uses search results when detailed data unavailable
    - **Rate Limiting**: Respects EPO API limits with built-in delays
    - **Progress Tracking**: Shows real-time extraction progress
    - **Data Quality Metrics**: Shows completeness statistics
    - **CSV Export**: Download results for further analysis
    
    ### 📊 Data Fields:
    - **Basic**: Document number, publication date, applicant name/country
    - **Classifications**: Main CPC class and full CPC list
    - **Register** (optional): Representatives, oppositions, appeals
    
    ### ⚡ Performance Tips:
    - Start with smaller date ranges (1-3 months) for testing
    - Register data significantly increases extraction time
    - Use batch size of 100 for optimal performance
    - The tool handles rate limiting automatically
    - EPO has daily API limits, so plan accordingly
    
    ### 🔧 Technical Details:
    - Uses EPO OPS API v3.2 for search and detailed data
    - Implements robust XML parsing with multiple XPath fallbacks
    - Handles both epodoc and docdb document ID formats
    - Includes comprehensive error handling and recovery
    """)
