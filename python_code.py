import streamlit as st
import pandas as pd
import requests
import time
import base64
import json
from urllib.parse import quote

# ===== Alternative Method 1: Different Authentication Approach =====
def get_access_token_v1(client_id, client_secret):
    """EPO OAuth2 - Method 1"""
    token_url = "https://ops.epo.org/3.2/auth/accesstoken"
    
    # Method 1: Manual base64 encoding
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode('utf-8')).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'EPO-Patent-App/1.0'
    }
    
    data = 'grant_type=client_credentials'
    
    try:
        response = requests.post(token_url, headers=headers, data=data, timeout=30)
        st.write(f"Status: {response.status_code}, Response: {response.text}")
        
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            return None
    except Exception as e:
        st.error(f"Auth Method 1 failed: {e}")
        return None

# ===== Alternative Method 2: Using requests.auth =====
def get_access_token_v2(client_id, client_secret):
    """EPO OAuth2 - Method 2"""
    from requests.auth import HTTPBasicAuth
    
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
        st.write(f"Status: {response.status_code}, Response: {response.text}")
        
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            return None
    except Exception as e:
        st.error(f"Auth Method 2 failed: {e}")
        return None

# ===== Alternative Method 3: No-Auth Search (Limited) =====
def search_patents_no_auth(year, max_results=25):
    """Search patents without authentication (limited functionality)"""
    search_url = "https://ops.epo.org/3.2/rest-services/published-data/search"
    
    # Simple query for patents published in year
    query = f'pd within "{year}"'
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'EPO-Patent-App/1.0'
    }
    
    params = {
        'q': query,
        'Range': f'1-{min(max_results, 25)}'  # No-auth limit is usually lower
    }
    
    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=30)
        st.write(f"No-auth search status: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        else:
            st.write(f"No-auth response: {response.text}")
            return None
    except Exception as e:
        st.error(f"No-auth search failed: {e}")
        return None

# ===== Alternative Method 4: Using REST API directly =====
def search_patents_rest(doc_number):
    """Get specific patent by document number (no auth needed for some endpoints)"""
    if not doc_number.startswith(('EP', 'WO', 'US')):
        doc_number = f"EP{doc_number}"
    
    detail_url = f"https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc/{doc_number}"
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'EPO-Patent-App/1.0'
    }
    
    try:
        response = requests.get(detail_url, headers=headers, timeout=30)
        st.write(f"REST API status for {doc_number}: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        st.error(f"REST API failed: {e}")
        return None

# ===== UI for Testing Different Methods =====
st.title("🔧 EPO API Troubleshooting")
st.markdown("Let's try different authentication methods:")

# Test credentials
test_client_id = st.text_input("Client ID")
test_client_secret = st.text_input("Client Secret", type="password")
test_year = st.number_input("Year", value=2024)

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("Test Method 1"):
        if test_client_id and test_client_secret:
            st.write("🧪 Testing Manual Base64...")
            token = get_access_token_v1(test_client_id, test_client_secret)
            if token:
                st.success(f"✅ Method 1 Success! Token: {token[:20]}...")
            else:
                st.error("❌ Method 1 Failed")

with col2:
    if st.button("Test Method 2"):
        if test_client_id and test_client_secret:
            st.write("🧪 Testing HTTPBasicAuth...")
            token = get_access_token_v2(test_client_id, test_client_secret)
            if token:
                st.success(f"✅ Method 2 Success! Token: {token[:20]}...")
            else:
                st.error("❌ Method 2 Failed")

with col3:
    if st.button("Test No-Auth"):
        st.write("🧪 Testing No-Auth Search...")
        results = search_patents_no_auth(test_year, 10)
        if results:
            st.success("✅ No-Auth Search Works!")
            st.json(results)
        else:
            st.error("❌ No-Auth Failed")

with col4:
    test_doc = st.text_input("Doc Number", placeholder="EP1234567")
    if st.button("Test REST") and test_doc:
        st.write(f"🧪 Testing REST API for {test_doc}...")
        results = search_patents_rest(test_doc)
        if results:
            st.success("✅ REST API Works!")
            st.json(results)
        else:
            st.error("❌ REST API Failed")

# ===== Troubleshooting Guide =====
st.markdown("---")
st.markdown("### 🔍 Troubleshooting EPO API Issues:")

st.markdown("""
**Common causes of 500 errors:**

1. **Invalid Credentials Format**
   - Make sure your Client ID doesn't have spaces
   - Check for special characters in Client Secret
   - Verify credentials are from EPO Developer Portal

2. **EPO Server Issues**
   - Try again in a few minutes
   - EPO API sometimes has maintenance

3. **Request Format Issues**
   - Different EPO endpoints expect different formats
   - Some require XML, others JSON

4. **Rate Limiting**
   - EPO has strict rate limits
   - Wait between requests

**Alternative Solutions:**
- Use the No-Auth method for basic searches (limited results)
- Try the REST API for specific document lookups
- Contact EPO support if credentials are definitely correct
""")

st.markdown("### 📝 EPO Credential Checklist:")
st.markdown("""
- [ ] Registered at https://developers.epo.org/
- [ ] Created an application in your account
- [ ] Got Consumer Key (Client ID) and Consumer Secret
- [ ] Credentials are active (not expired)
- [ ] No special characters causing encoding issues
""")
