import streamlit as st
from supabase import create_client

url = str(st.secrets["SUPABASE_URL"]).strip()
key = str(st.secrets["SUPABASE_SERVICE_ROLE_KEY"]).strip()

print("URL:", url)
print("KEY长度:", len(key))

client = create_client(url, key)

print("客户端创建成功")

result = client.table("users").select("*").limit(1).execute()

print("数据库请求成功")
print(result.data)
