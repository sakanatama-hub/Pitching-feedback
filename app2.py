import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import date
import re
import os
import io
import requests
import time
import base64

# --- 1. ページ設定 ---
st.set_page_config(layout="wide", page_title="投球解析システム")

# --- 簡易パスワード認証 ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if st.session_state["authenticated"]:
        return True
    st.title("🔒 投球解析システム - ログイン")
    with st.form("login_form"):
        password_input = st.text_input("パスワードを入力してください", type="password")
        if st.form_submit_button("ログイン"):
            if password_input == "1189":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ パスワードが間違っています。")
    return False

if not check_password():
    st.stop()

# --- GitHubデータ連携設定 ---
GITHUB_TOKEN = st.secrets.get("PITCHING_FEEDBACK") or os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = "sakanatama-hub/Pitching-feedback"
GITHUB_PITCH_FILE_PATH = "data/pitch_data.xlsx"

def load_data_from_github(file_path):
    if not GITHUB_TOKEN: return pd.DataFrame()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        download_url = res.json()["download_url"]
        return pd.read_excel(io.BytesIO(requests.get(download_url).content))
    return pd.DataFrame()

def save_to_github_with_retry(df_to_save, file_path):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get("sha") if res.status_code == 200 else None
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_to_save.to_excel(writer, index=False)
    content_b64 = base64.b64encode(output.getvalue()).decode("utf-8")
    payload = {"message": "Update data", "content": content_b64}
    if sha: payload["sha"] = sha
    
    put_res = requests.put(url, headers=headers, json=payload)
    return put_res.status_code in [200, 201]

if 'pitch_df' not in st.session_state:
    st.session_state['pitch_df'] = load_data_from_github(GITHUB_PITCH_FILE_PATH)

# --- 補助関数 ---
def time_to_degrees(time_str):
    match = re.match(r"(\d+):(\d+)", str(time_str))
    if not match: return 0.0
    hh, mm = map(int, match.groups())
    return ((hh % 12) * 60 + mm) * 0.5

# --- メイン UI ---
tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 投手データ登録・削除"])

with tab2:
    st.header("📝 投手データ管理")
    manage_mode = st.radio("操作を選択", ["🗑️ 削除"], horizontal=True)
    
    latest_db = st.session_state['pitch_df']
    if latest_db.empty:
        st.warning("データがありません")
    else:
        latest_db['Date'] = latest_db['Date'].astype(str)
        options = latest_db[['Player Name', 'Date', 'Data Type']].drop_duplicates().sort_values('Date', ascending=False)
        options['label'] = options.apply(lambda x: f"{x['Date']} | {x['Player Name']} | {x['Data Type']}", axis=1)
        
        selected_label = st.selectbox("削除するデータセットを選択", list(options['label']))
        sel = options[options['label'] == selected_label].iloc[0]
        
        target_condition = (latest_db['Player Name'] == sel['Player Name']) & (latest_db['Date'] == sel['Date']) & (latest_db['Data Type'] == sel['Data Type'])
        st.info(f"選択: {len(latest_db[target_condition])} 球のデータを削除します")
        
        if st.checkbox("完全に削除する"):
            if st.button("🚨 実行"):
                updated_db = latest_db[~target_condition]
                if save_to_github_with_retry(updated_db, GITHUB_PITCH_FILE_PATH):
                    st.session_state['pitch_df'] = updated_db
                    st.success("削除完了しました")
                    st.rerun()

with tab1:
    st.header("分析フィードバック")
    df = st.session_state['pitch_df']
    if not df.empty:
        st.subheader("⚾️ 3Dスピンビジュアライザー")
        c_rev, c_eff, c_dir = 'Spin Rate', 'Spin Efficiency', 'Spin Direction'
        df_viz = df.copy()
        for c in [c_rev, c_eff]: df_viz[c] = pd.to_numeric(df_viz[c], errors='coerce')
        
        valid_df = df_viz.dropna(subset=['Pitch Type', c_dir, c_rev])
        if not valid_df.empty:
            sel_type = st.selectbox("球種を選択:", sorted(valid_df['Pitch Type'].unique()))
            subset = valid_df[valid_df['Pitch Type'] == sel_type]
            
            avg_rpm = subset[c_rev].mean()
            avg_tilt_str = str(subset[c_dir].iloc[0])
            
            st.write(f"平均回転数: {avg_rpm:.0f} RPM, Tilt: {avg_tilt_str}")
            
            # 3D可視化用HTML (簡略化)
            st.info("3Dビジュアライザー表示中...")
            st.components.v1.html(f"""
            <div style="text-align:center;">
                <h3>回転解析: {sel_type}</h3>
                <p>RPM: {avg_rpm:.0f} | Tilt: {avg_tilt_str}</p>
            </div>
            """, height=200)
    else:
        st.write("データが登録されていません。")
