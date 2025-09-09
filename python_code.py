import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import time
import math
import json
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
    .stApp {
        background-color: #FFE3EB;
    }
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

# ===== 2️⃣ Helper Functions for EPO API =====
def get_access_token(client_id, client_secret):
    """Get OAuth2 access token from EPO"""
    token_url = "https://ops.epo.org/3.2/auth/accesstoken"
    
    headers = {
        'Authorization': f'Basic {requests.auth._basic_auth_str(client_id, client_secret)}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {'grant_type': 'client_credentials'}
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get access token: {e}")
        return None

def search_patents(access_token, year, max_results=50):
    """Search for patents by publication year"""
    search_url = "https://ops.epo.org/3.2/rest-services/published-data/search"
    
    # Search query for patents published in the specified year
    query = f'pd within "{year}"'
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    params = {
        'q': query,
        'Range': f'1-{min(max_results, 100)}'  # EPO limits to 100 per request
    }
    
    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Search failed: {e}")
        return None

def get_patent_details(access_token, doc_number):
    """Get detailed information for a specific patent"""
    detail_url = f"https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/{doc_number}/biblio"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(detail_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
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
            pub_ref = result['exchange-document']['bibliographic-data']['publication-reference']['document-id'][0]
            
            doc_number = pub_ref.get('doc-number', {}).get('$', 'N/A')
            country = pub_ref.get('country', {}).get('$', 'N/A')
            kind = pub_ref.get('kind', {}).get('$', 'N/A')
            date = pub_ref.get('date', {}).get('$', 'N/A')
            
            # Try to get applicant info
            applicant = 'N/A'
            if 'bibliographic-data' in result['exchange-document']:
                biblio = result['exchange-document']['bibliographic-data']
                if 'parties' in biblio and 'applicants' in biblio['parties']:
                    applicants = biblio['parties']['applicants']['applicant']
                    if isinstance(applicants, list):
                        applicant = applicants[0].get('applicant-name', {}).get('name', {}).get('$', 'N/A')
                    else:
                        applicant = applicants.get('applicant-name', {}).get('name', {}).get('$', 'N/A')
            
            # Try to get title
            title = 'N/A'
            if 'bibliographic-data' in result['exchange-document']:
                biblio = result['exchange-document']['bibliographic-data']
                if 'invention-title' in biblio:
                    inv_title = biblio['invention-title']
                    if isinstance(inv_title, list):
                        title = inv_title[0].get('$', 'N/A')
                    else:
                        title = inv_title.get('$', 'N/A')
            
            patents.append({
                'DocNumber': f"{country}{doc_number}",
                'Country': country,
                'Kind': kind,
                'PubDate': date,
                'Applicant': applicant,
                'Title': title
            })
            
        except (KeyError, TypeError, IndexError) as e:
            continue
    
    return patents

# ===== 3️⃣ User Interface =====
col1, col2, col3 = st.columns([1,2,1])
with col2:
    client_id = st.text_input("Client ID", key="client_id", help="Your EPO API client ID")
    client_secret = st.text_input("Client Secret", type="password", key="client_secret", help="Your EPO API client secret")
    year = st.number_input("Year", min_value=1900, max_value=2100, value=2024, key="year")
    max_rows = st.number_input("Max Rows", min_value=1, max_value=100, value=25, key="max_rows", 
                              help="Maximum number of patents to retrieve (EPO limit: 100)")

# ===== 4️⃣ Run button and main logic =====
with col2:
    run_button = st.button("🚀 Get Real EPO Data")

if run_button:
    if not client_id or not client_secret:
        st.error("❌ Please provide both Client ID and Client Secret")
    else:
        st.success("🔄 Fetching real EPO patent data...")
        
        with st.spinner("Getting access token..."):
            access_token = get_access_token(client_id, client_secret)
        
        if access_token:
            st.success("✅ Successfully authenticated with EPO API")
            
            with st.spinner("Searching for patents..."):
                search_results = search_patents(access_token, year, max_rows)
            
            if search_results:
                with st.spinner("Parsing patent data..."):
                    patents = parse_search_results(search_results)
                
                if patents:
                    df = pd.DataFrame(patents)
                    st.success(f"✅ Successfully retrieved {len(df)} real patents from {year}")
                    
                    # Display results
                    st.markdown("### 📊 Patent Search Results")
                    st.dataframe(df, use_container_width=True)
                    
                    # Download button
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Real Patent Data CSV",
                        data=csv,
                        file_name=f"epo_real_patents_{year}.csv",
                        mime='text/csv'
                    )
                    
                    # Show some statistics
                    st.markdown("### 📈 Quick Stats")
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("Total Patents", len(df))
                    with col_stat2:
                        st.metric("Unique Countries", df['Country'].nunique())
                    with col_stat3:
                        st.metric("Unique Applicants", df['Applicant'].nunique())
                        
                else:
                    st.warning("⚠️ No patents found for the specified criteria")
            else:
                st.error("❌ Failed to search patents. Check your credentials and try again.")
        else:
            st.error("❌ Authentication failed. Please check your Client ID and Secret.")

# ===== 5️⃣ Information section =====
st.markdown("---")
st.markdown("### ℹ️ How to get EPO API credentials:")
st.markdown("""
1. Register at [EPO Open Patent Services](https://developers.epo.org/)
2. Create an application to get your Client ID and Secret
3. The EPO API has rate limits, so be patient with large requests
4. This app searches for patents published in the specified year
""")

st.markdown("### 🔧 Technical Notes:")
st.info(f"Using {XML_PARSER} XML parser | EPO API Version: 3.2")
