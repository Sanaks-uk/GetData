import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import base64
import time
from datetime import datetime, timedelta
import json

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

# ===== 2️⃣ Simple Authentication =====
def get_token(client_id, client_secret):
    """Get EPO access token - simplified approach"""
    url = "https://ops.epo.org/3.2/auth/accesstoken"
    
    # Use HTTPBasicAuth - the simplest approach
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

# ===== 3️⃣ Batch Patent Search =====
def search_patents_batch(token, start_date, end_date, batch_size=100):
    """Search patents in batches for date range"""
    url = "https://ops.epo.org/3.2/rest-services/published-data/search"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    all_patents = []
    current_start = 1
    
    # Create broader search query for date range
    query = f'pd >= {start_date} AND pd <= {end_date}'
    
    while True:
        params = {
            'q': query,
            'Range': f'{current_start}-{current_start + batch_size - 1}'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                patents = extract_patent_data(data)
                
                if not patents:  # No more results
                    break
                    
                all_patents.extend(patents)
                st.write(f"📥 Extracted {len(all_patents)} patents so far...")
                
                # Check if we got less than requested (end of results)
                if len(patents) < batch_size:
                    break
                    
                current_start += batch_size
                time.sleep(0.5)  # Rate limiting
                
            elif response.status_code == 404:
                break  # No more results
            else:
                st.warning(f"API returned {response.status_code}: {response.text}")
                break
                
        except Exception as e:
            st.error(f"Search error: {e}")
            break
    
    return all_patents

# ===== 4️⃣ Simple Data Extraction =====
def extract_patent_data(api_response):
    """Extract patent data from API response - simplified parsing"""
    patents = []
    
    try:
        # Navigate through EPO's JSON structure
        world_data = api_response.get('ops:world-patent-data', {})
        biblio_search = world_data.get('ops:biblio-search', {})
        search_result = biblio_search.get('ops:search-result', [])
        
        # Handle single result vs multiple results
        if isinstance(search_result, dict):
            search_result = [search_result]
        
        for result in search_result:
            try:
                # Get basic document info
                doc = result.get('exchange-document', {})
                biblio = doc.get('bibliographic-data', {})
                
                # Publication reference
                pub_ref = biblio.get('publication-reference', {})
                doc_id = pub_ref.get('document-id', [{}])
                
                if isinstance(doc_id, list):
                    doc_id = doc_id[0]
                
                # Extract basic fields
                doc_number = safe_extract(doc_id, 'doc-number', '$')
                country = safe_extract(doc_id, 'country', '$')
                kind = safe_extract(doc_id, 'kind', '$')
                pub_date = safe_extract(doc_id, 'date', '$')
                
                # Get title
                title = 'N/A'
                inv_title = biblio.get('invention-title', {})
                if isinstance(inv_title, list) and inv_title:
                    title = safe_extract(inv_title[0], '$')
                elif isinstance(inv_title, dict):
                    title = safe_extract(inv_title, '$')
                
                # Get applicant
                applicant = 'N/A'
                parties = biblio.get('parties', {})
                applicants = parties.get('applicants', {})
                
                if isinstance(applicants, dict):
                    applicant_list = applicants.get('applicant', [])
                    if isinstance(applicant_list, list) and applicant_list:
                        applicant_name = applicant_list[0].get('applicant-name', {})
                        name = applicant_name.get('name', {})
                        applicant = safe_extract(name, '$')
                    elif isinstance(applicant_list, dict):
                        applicant_name = applicant_list.get('applicant-name', {})
                        name = applicant_name.get('name', {})
                        applicant = safe_extract(name, '$')
                
                patents.append({
                    'Document_Number': f"{country}{doc_number}" if country and doc_number else 'N/A',
                    'Country': country or 'N/A',
                    'Publication_Date': pub_date or 'N/A',
                    'Kind_Code': kind or 'N/A',
                    'Title': title or 'N/A',
                    'Applicant': applicant or 'N/A'
                })
                
            except Exception as e:
                continue  # Skip problematic records
                
    except Exception as e:
        st.warning(f"Data extraction error: {e}")
    
    return patents

def safe_extract(data, *keys):
    """Safely extract nested dictionary values"""
    try:
        result = data
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key, 'N/A')
            else:
                return 'N/A'
        return result if result != 'N/A' else 'N/A'
    except:
        return 'N/A'

# ===== 5️⃣ User Interface =====
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
    
    batch_size = st.selectbox("Batch Size", options=[25, 50, 100], index=2,
                             help="Number of patents per API call")

# ===== 6️⃣ Run Button =====
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
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔐 Authenticating...")
        token = get_token(client_id, client_secret)
        progress_bar.progress(20)
        
        if token:
            st.success("✅ Authentication successful!")
            
            # Step 2: Extract data
            status_text.text("📥 Extracting patent data...")
            progress_bar.progress(40)
            
            patents = search_patents_batch(token, start_str, end_str, batch_size)
            progress_bar.progress(80)
            
            if patents:
                # Limit results if needed
                if len(patents) > max_patents:
                    patents = patents[:max_patents]
                    st.warning(f"⚠️ Limited results to {max_patents} patents")
                
                # Create DataFrame
                df = pd.DataFrame(patents)
                progress_bar.progress(100)
                status_text.text("✅ Data extraction complete!")
                
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
                    st.metric("Countries", df['Country'].nunique())
                with col_stat3:
                    st.metric("Date Range", f"{(end_date - start_date).days} days")
                with col_stat4:
                    valid_applicants = len(df[df['Applicant'] != 'N/A'])
                    st.metric("With Applicants", valid_applicants)
                
                # Download button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"📥 Download {len(df)} Patents CSV",
                    data=csv,
                    file_name=f"epo_patents_{start_str}_{end_str}.csv",
                    mime='text/csv'
                )
                
            else:
                st.warning("⚠️ No patents found for the specified date range")
                progress_bar.progress(100)
        else:
            st.error("❌ Authentication failed - check your credentials")
            progress_bar.progress(0)

# ===== 7️⃣ Help Section =====
st.markdown("---")
with st.expander("ℹ️ How to use this tool"):
    st.markdown("""
    ### 📋 Setup Instructions:
    1. **Get EPO API credentials** from https://developers.epo.org/
    2. **Enter your Client ID and Secret** above
    3. **Select date range** for patent search
    4. **Set maximum patents** to extract (recommended: 1000-5000)
    5. **Click Extract** and wait for results
    
    ### 🚀 Features:
    - **Date Range Search**: Extract patents from any date period
    - **Batch Processing**: Efficiently handles large datasets
    - **Rate Limiting**: Respects EPO API limits
    - **Progress Tracking**: Shows real-time extraction progress
    - **CSV Export**: Download results for further analysis
    
    ### ⚡ Tips for Large Extractions:
    - Start with smaller date ranges (1-3 months)
    - Use batch size of 100 for faster processing
    - The tool automatically handles pagination
    - EPO has daily limits, so plan accordingly
    """)
