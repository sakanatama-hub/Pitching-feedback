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
        submit_button = st.form_submit_button("ログイン")
        if submit_button:
            if password_input == "1189":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ パスワードが間違っています。")
    return False

if not check_password():
    st.stop()

# --- 2. トークン・リポジトリ設定 ---
GITHUB_TOKEN = st.secrets.get("PITCHING_FEEDBACK") or st.secrets.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = "sakanatama-hub/Pitching-feedback"
GITHUB_PITCH_FILE_PATH = "data/pitch_data.xlsx"

def load_data_from_github(file_path):
    if not GITHUB_TOKEN:
        return pd.DataFrame()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        download_url = res.json()["download_url"]
        file_res = requests.get(download_url)
        return pd.read_excel(io.BytesIO(file_res.content))
    return pd.DataFrame()

def save_to_github_with_retry(df_to_save, file_path, max_retries=3):
    if not GITHUB_TOKEN: return False, "Token missing"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    for attempt in range(max_retries):
        res = requests.get(url, headers=headers)
        sha = res.json().get("sha") if res.status_code == 200 else None
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_to_save.to_excel(writer, index=False)
        content_b64 = base64.b64encode(output.getvalue()).decode("utf-8")
        
        payload = {"message": "Update data", "content": content_b64}
        if sha: payload["sha"] = sha
            
        put_res = requests.put(url, headers=headers, json=payload)
        if put_res.status_code in [200, 201]:
            st.session_state['pitch_df'] = df_to_save
            return True, "成功"
        time.sleep(1.5)
    return False, "保存失敗"

# アプリ起動時のデータ読み込み
if 'pitch_df' not in st.session_state:
    st.session_state['pitch_df'] = load_data_from_github(GITHUB_PITCH_FILE_PATH)

# --- 定数 ---
PLAYER_HANDS = {"#11 大栄 陽斗": "右", "#12 村上 崚久": "右", "#13 細川 拓哉": "右", "#14 ヴァデルナ・フェルガス": "左", "#15 渕上 佳輝": "右", "#16 後藤 凌寿": "右", "#17 加藤 泰靖": "右", "#18 市川 祐": "右", "#19 高尾 響": "右", "#20 嘉陽 宗一郎": "右", "#21 池村 健太郎": "右", "#30 平野 大智": "右"}
COLOR_MAP_PITCH = {"Straight": "red", "Split": "blue", "Changeup": "green", "Cutter": "orange", "Slider": "yellow", "Curve": "darkblue", "Sinker": "pink"}
COLUMN_MAP = {'TaggedPitchType': 'Pitch Type', 'RelSpeed': 'Velocity', 'SpinRate': 'Spin Rate', 'Tilt': 'Spin Direction', 'InducedVertBreak': 'VB', 'HorzBreak': 'HB'}

def time_to_degrees(time_str):
    try:
        match = re.match(r"(\d+):(\d+)", str(time_str))
        if not match: return 0.0
        hh, mm = map(int, match.groups())
        return ((hh % 12) * 60 + mm) * 0.5
    except: return 0.0

# --- タブ構造 ---
tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 投手データ登録・削除"])

# ==========================================
# タブ2：投手データ管理
# ==========================================
with tab2:
    st.header("📝 投手データ管理")
    manage_mode = st.radio("操作を選択", ["📥 新規登録", "🗑️ 削除"], horizontal=True)
    
    if manage_mode == "📥 新規登録":
        col1, col2, col3 = st.columns(3)
        with col1: target_player = st.selectbox("選手", sorted(list(PLAYER_HANDS.keys())))
        with col2: target_date = st.date_input("日付", date.today())
        with col3: data_type = st.radio("練習種別", ["ブルペン", "シートBT"], horizontal=True)
        data_source = st.radio("計測機器", ["Trackman", "Rapsodo"], horizontal=True)
        uploaded_file = st.file_uploader("ファイルをアップロード", type=['csv', 'xlsx'])
        
        if uploaded_file and st.button("🚀 GitHubへ保存"):
            # データ処理ロジック (省略せず記載)
            new_data = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
            new_data['Player Name'] = target_player
            new_data['Date'] = target_date
            new_data['Data Type'] = data_type
            
            combined_df = pd.concat([st.session_state['pitch_df'], new_data], ignore_index=True)
            success, msg = save_to_github_with_retry(combined_df, GITHUB_PITCH_FILE_PATH)
            if success:
                st.success("登録完了しました")
                st.rerun()

    else: # 削除モード
        latest_db = load_data_from_github(GITHUB_PITCH_FILE_PATH)
        if latest_db.empty:
            st.warning("データがありません")
        else:
            latest_db['Date'] = latest_db['Date'].astype(str)
            options = latest_db[['Player Name', 'Date', 'Data Type']].drop_duplicates().sort_values('Date', ascending=False)
            options['label'] = options.apply(lambda x: f"{x['Date']} | {x['Player Name']} | {x['Data Type']}", axis=1)
            option_map = {row['label']: row for _, row in options.iterrows()}
            
            selected_label = st.selectbox("削除するデータセットを選択", list(option_map.keys()))
            sel = option_map[selected_label]
            
            target_condition = (latest_db['Player Name'] == sel['Player Name']) & (latest_db['Date'] == sel['Date']) & (latest_db['Data Type'] == sel['Data Type'])
            st.info(f"選択: {len(latest_db[target_condition])} 球のデータを削除します")
            
            if st.checkbox("上記データを完全に削除する"):
                if st.button("🚨 実行", type="primary"):
                    updated_db = latest_db[~target_condition]
                    success, msg = save_to_github_with_retry(updated_db, GITHUB_PITCH_FILE_PATH)
                    if success:
                        st.success("削除成功しました")
                        st.rerun()

# ==========================================
# タブ1：分析フィードバック
# ==========================================
with tab1:
    st.header("分析フィードバック")
    # ここにメインの分析コードが続きます (既存の可視化ロジック)
    df = st.session_state['pitch_df'].copy()
    
    if not df.empty:
        # --- 3Dスピンビジュアライザー ---
        st.divider()
        st.subheader("⚾️ 3Dスピンビジュアライザー")
        
        # データの型を揃えて安全に抽出
        df_viz = df.copy()
        c_rev, c_eff, c_dir = 'Spin Rate', 'Spin Efficiency', 'Spin Direction'
        
        # 数値変換の強制
        for c in [c_rev, c_eff]:
            df_viz[c] = pd.to_numeric(df_viz[c], errors='coerce')

        valid_df = df_viz.dropna(subset=['Pitch Type', c_dir, c_rev])

        if not valid_df.empty:
            available_types = sorted(valid_df['Pitch Type'].unique())
            sel_type = st.selectbox("球種を選択して回転を確認:", available_types, key="pitch_viz_select")
            
            subset = valid_df[valid_df['Pitch Type'] == sel_type]
            
            # 平均値計算
            avg_rpm = subset[c_rev].mean()
            avg_eff = subset[c_eff].mean() if c_eff in subset.columns else 100.0
            
            # Tiltの取得
            avg_tilt_str = str(subset[c_dir].iloc[0])
            tilt_deg = time_to_degrees(avg_tilt_str)
            
            st.write(f"**{sel_type}** の平均データ： 回転数 {avg_rpm:.0f} RPM / 効率 {avg_eff:.1f}% / Tilt {avg_tilt_str}")

            # --- 数学的な計算部分 ---
            t = np.linspace(0, 2 * np.pi, 200)
            alpha = 0.4
            sx, sy, sz = np.cos(t) + alpha * np.cos(3*t), np.sin(t) - alpha * np.sin(3*t), 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
            base_pts = np.vstack([sx, sz, sy]).T 

            tilt_rad = np.deg2rad(tilt_deg)
            cos_t, sin_t = np.cos(tilt_rad), np.sin(tilt_rad)
            rot_y = np.array([[cos_t, 0, -sin_t], [0, 1, 0], [sin_t, 0, cos_t]])

            # 効率からジャイロ成分を計算
            gyro_rad = np.deg2rad((100 - min(avg_eff, 100)) * 0.9)
            cos_g, sin_g = np.cos(gyro_rad), np.sin(gyro_rad)
            g_sign = 1
            rot_gyro = np.array([[1, 0, 0], [0, cos_g, g_sign*sin_g], [0, -g_sign*sin_g, cos_g]])

            combined_rot = rot_y @ rot_gyro
            axis = combined_rot @ np.array([0.0, 0.0, 1.0])
            tilted_pts = (base_pts @ combined_rot.T)
            seam_points = (tilted_pts / np.linalg.norm(tilted_pts, axis=1, keepdims=True)).tolist()
            multiplier = -1 if any(k in sel_type.lower() for k in ["cut", "slider", "sl", "curve"]) else 1

            # --- HTML描画 ---
            html_code = f"""
            <div id="ball_canvas" style="width:100%; height:400px;"></div>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var points = {{ seam: {json.dumps(seam_points)} }};
                var axis = {json.dumps(axis.tolist())};
                var rpm = {avg_rpm};
                var mult = {multiplier};
                
                var data = [{{
                    type: 'scatter3d',
                    x: points.seam.map(p => p[0]),
                    y: points.seam.map(p => p[1]),
                    z: points.seam.map(p => p[2]),
                    mode: 'markers',
                    marker: {{ size: 2, color: 'white' }}
                }}];
                var layout = {{
                    scene: {{ bgcolor: 'black', xaxis: {{visible:false}}, yaxis: {{visible:false}}, zaxis: {{visible:false}} }},
                    margin: {{l:0, r:0, b:0, t:0}}
                }};
                Plotly.newPlot('ball_canvas', data, layout);
            </script>
            """
            st.components.v1.html(html_code, height=450)
        else:
            st.info("スピンデータを可視化するための十分なデータがありません。")
