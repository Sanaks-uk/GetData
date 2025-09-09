import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import time
import math
import json
import base64
from datetime import datetime

# Try to import lxml, fall back to xml.etree if not available
try:
    from lxml import etree
    XML_PARSER = "lxml"
except ImportError:
    import xml.etree.ElementTree as etree
    XML_PARSER = "builtin"
    st.warning("⚠️ lxml not found, using built-in XML parser. Consider adding lxml to requirements.txt for better performance.")

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
st.markdown("Fill in your credentials and parameters below:")

# ===== 2️⃣ Working Authentication Methods =====
def get_access_token_method1(client_id, client_secret):
    """EPO OAuth2 - Method 1 (Manual base64)"""
    token_url = "https://ops.epo.org/3.2/auth/accesstoken"
    
    # Manual base64 encoding
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode('utf-8')).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'EPO-Patent-App/1.0'
    }
    
    data = 'grant_type=client_credentials'
    
    try:
        response = requests.post(token_url, headers=headers, data=data, timeout=30)
        if response.status_code == 200:
            return response.json().get('access_token')
    except Exception:
        pass
    return None

def get_access_token_method2(client_id, client_secret):
    """EPO OAuth2 - Method 2 (HTTPBasicAuth)"""
    token_url = "https://ops.epo.org/3.2/auth/accesstoken"
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'EPO-Patent-App/1.0'
    }
    
    data = {'grant_type': 'client_credentials'}
    
    try:
        response = requests.post(
            token_url, 
            headers=headers, 
            data=data,
            auth=HTTPBasicAuth(client_id, client_secret),
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get('access_token')
    except Exception:
        pass
    return None

def get_access_token(client_id, client_secret):
    """Try both working authentication methods"""
    # Try Method 1 first
    token = get_access_token_method1(client_id, client_secret)
    if token:
        return token
    
    # Fallback to Method 2
    token = get_access_token_method2(client_id, client_secret)
    return token

def search_patents(access_token, year, max_results=50):
    """Search for patents by publication year"""
    search_url = "https://ops.epo.org/3.2/rest-services/published-data/search"
    
    # Search query for patents published in the specified year
    query = f'pd within "{year}"'
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'User-Agent': 'EPO-Patent-App/1.0'
    }
    
    params = {
        'q': query,
        'Range': f'1-{min(max_results, 100)}'  # EPO limits to 100 per request
    }
    
    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Search failed with status {response.status_code}: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Search failed: {e}")
        return None

def parse_search_results(search_data):
    """Parse search results and extract patent information"""
    patents = []
    
    if not search_data or 'ops:world-patent-data' not in search_data:
        return patents
    
    world_data = search_data['ops:world-patent-data']
    
    if 'ops:biblio-search' not in world_data:
        return patents
    
    biblio_search = world_data['ops:biblio-search']
    
    if 'ops:search-result' not in biblio_search:
        return patents
    
    search_results = biblio_search['ops:search-result']
    
    # Handle both single result and multiple results
    if isinstance(search_results, dict):
        search_results = [search_results]
    
    for result in search_results:
        try:
            exchange_doc = result.get('exchange-document', {})
            biblio_data = exchange_doc.get('bibliographic-data', {})
            
            # Get publication reference
            pub_ref = biblio_data.get('publication-reference', {})
            doc_id = pub_ref.get('document-id', [{}])
            if isinstance(doc_id, list):
                doc_id = doc_id[0]
            
            doc_number = doc_id.get('doc-number', {}).get('$', 'N/A')
            country = doc_id.get('country', {}).get('$', 'N/A')
            kind = doc_id.get('kind', {}).get('$', 'N/A')
            date = doc_id.get('date', {}).get('$', 'N/A')
            
            # Try to get applicant info
            applicant = 'N/A'
            parties = biblio_data.get('parties', {})
            if 'applicants' in parties:
                applicants = parties['applicants'].get('applicant', [])
                if isinstance(applicants, list) and applicants:
                    applicant_name = applicants[0].get('applicant-name', {})
                    if isinstance(applicant_name, dict):
                        name_data = applicant_name.get('name', {})
                        applicant = name_data.get('$', 'N/A') if isinstance(name_data, dict) else str(name_data)
                elif isinstance(applicants, dict):
                    applicant_name = applicants.get('applicant-name', {})
                    if isinstance(applicant_name, dict):
                        name_data = applicant_name.get('name', {})
                        applicant = name_data.get('$', 'N/A') if isinstance(name_data, dict) else str(name_data)
            
            # Try to get title
            title = 'N/A'
            inv_title = biblio_data.get('invention-title', {})
            if isinstance(inv_title, list) and inv_title:
                title = inv_title[0].get('$', 'N/A')
            elif isinstance(inv_title, dict):
                title = inv_title.get('$', 'N/A')
            
            patents.append({
                'DocNumber': f"{country}{doc_number}",
                'Country': country,
                'Kind': kind,
                'PubDate': date,
                'Applicant': applicant,
                'Title': title
            })
            
        except (KeyError, TypeError, IndexError, AttributeError) as e:
            continue
    
    return patents

# ===== 3️⃣ Centered input fields using columns =====
col1, col2, col3 = st.columns([1,2,1])
with col2:
    client_id = st.text_input("Client ID", key="client_id")
    client_secret = st.text_input("Client Secret", type="password", key="client_secret")
    year = st.number_input("Year", min_value=1900, max_value=2100, value=2024, key="year")
    max_rows = st.number_input("Max Rows", min_value=1, max_value=100, value=50, key="max_rows")

# ===== 4️⃣ Run button =====
with col2:
    run_button = st.button("Run")

if run_button:
    if not client_id or not client_secret:
        st.error("❌ Please provide both Client ID and Client Secret")
    else:
        st.success("You got it, now sit back and relax while I cook your CSV")
        
        # Get access token
        with st.spinner("Authenticating with EPO..."):
            access_token = get_access_token(client_id, client_secret)
        
        if access_token:
            st.success("✅ Successfully authenticated!")
            
            # Search for patents
            with st.spinner("Searching for patents..."):
                search_results = search_patents(access_token, year, max_rows)
            
            if search_results:
                # Parse results
                with st.spinner("Processing patent data..."):
                    patents = parse_search_results(search_results)
                
                if patents:
                    df = pd.DataFrame(patents)
                    st.success(f"✅ Found {len(df)} real patents from {year}!")
                    
                    st.markdown("### Patent Results")
                    st.dataframe(df)
                    
                    # ===== 5️⃣ Option to download CSV =====
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"epo_patents_{year}.csv",
                        mime='text/csv'
                    )
                    
                    # Quick stats
                    st.markdown("### Quick Statistics")
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("Total Patents", len(df))
                    with col_stat2:
                        st.metric("Countries", df['Country'].nunique())
                    with col_stat3:
                        st.metric("Unique Applicants", df[df['Applicant'] != 'N/A']['Applicant'].nunique())
                        
                else:
                    st.warning("⚠️ No patents found for the specified year. Try a different year or increase max rows.")
            else:
                st.error("❌ Patent search failed. Please try again.")
        else:
            st.error("❌ Authentication failed. Please check your credentials.")

# ===== 6️⃣ Footer info =====
st.markdown("---")
st.info("💡 **Tip:** Get your EPO API credentials from https://developers.epo.org/")
