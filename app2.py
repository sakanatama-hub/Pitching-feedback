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

# --- ページ設定 ---
st.set_page_config(layout="wide", page_title="投球解析システム")

# ==========================================
# 🔒 簡易パスワード認証システム
# ==========================================
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

# --- GitHub連携設定 ---
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

# --- 定数・ヘルパー ---
def time_to_degrees(time_str):
    match = re.match(r"(\d+):(\d+)", str(time_str))
    if not match: return 0.0
    hh, mm = map(int, match.groups())
    return ((hh % 12) * 60 + mm) * 0.5

# --- メインロジック ---
tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 投手データ登録・削除"])

with tab2:
    st.header("📝 投手データ管理")
    manage_mode = st.radio("操作を選択", ["📥 新規登録", "🗑️ 削除"], horizontal=True)
    
    if manage_mode == "📥 新規登録":
        st.write("新規登録機能は既存のアップロード処理を継続してください。")
    else:
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
    df = st.session_state['pitch_df'].copy()
    
    if not df.empty:
        st.subheader("⚾️ 3Dスピンビジュアライザー")
        c_rev, c_eff, c_dir = 'Spin Rate', 'Spin Efficiency', 'Spin Direction'
        for c in [c_rev, c_eff]: df[c] = pd.to_numeric(df[c], errors='coerce')
        
        valid_df = df.dropna(subset=['Pitch Type', c_dir, c_rev])
        if not valid_df.empty:
            sel_type = st.selectbox("球種を選択:", sorted(valid_df['Pitch Type'].unique()))
            subset = valid_df[valid_df['Pitch Type'] == sel_type]
            avg_rpm = subset[c_rev].mean()
            avg_eff = subset[c_eff].mean() if c_eff in subset.columns else 100.0
            avg_tilt_str = str(subset[c_dir].iloc[0])
            tilt_deg = time_to_degrees(avg_tilt_str)
            
            # --- 数学計算ロジック ---
            t = np.linspace(0, 2 * np.pi, 200)
            alpha = 0.4
            sx, sy, sz = np.cos(t) + alpha * np.cos(3*t), np.sin(t) - alpha * np.sin(3*t), 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
            base_pts = np.vstack([sx, sz, sy]).T 
            
            tilt_rad = np.deg2rad(tilt_deg)
            cos_t, sin_t = np.cos(tilt_rad), np.sin(tilt_rad)
            rot_y = np.array([[cos_t, 0, -sin_t], [0, 1, 0], [sin_t, 0, cos_t]])
            
            gyro_rad = np.deg2rad((100 - min(avg_eff, 100)) * 0.9)
            cos_g, sin_g = np.cos(gyro_rad), np.sin(gyro_rad)
            g_sign = 1 # 簡易化
            rot_gyro = np.array([[1, 0, 0], [0, cos_g, g_sign*sin_g], [0, -g_sign*sin_g, cos_g]])
            
            combined_rot = rot_y @ rot_gyro
            axis = combined_rot @ np.array([0.0, 0.0, 1.0])
            tilted_pts = (base_pts @ combined_rot.T)
            seam_points = (tilted_pts / np.linalg.norm(tilted_pts, axis=1, keepdims=True)).tolist()
            
            # --- 描画用HTML ---
            html_code = f"""
            <div id="ball_canvas" style="width:100%; height:400px;"></div>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var seamPoints = {json.dumps(seam_points)};
                var axis = {json.dumps(axis.tolist())};
                var data = [{{
                    type: 'scatter3d',
                    x: seamPoints.map(p => p[0]),
                    y: seamPoints.map(p => p[1]),
                    z: seamPoints.map(p => p[2]),
                    mode: 'markers',
                    marker: {{ size: 2, color: 'white' }}
                }}];
                Plotly.newPlot('ball_canvas', data, {{
                    scene: {{ bgcolor: 'black', xaxis: {{visible:false}}, yaxis: {{visible:false}}, zaxis: {{visible:false}} }},
                    margin: {{l:0, r:0, b:0, t:0}}
                }});
            </script>
            """
            st.components.v1.html(html_code, height=450)
            st.write(f"平均回転数: {avg_rpm:.0f} RPM, Tilt: {avg_tilt_str}, 効率: {avg_eff:.1f}%")
    else:
        st.write("データがありません。")
