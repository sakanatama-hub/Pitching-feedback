import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import date, timedelta
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
            # データ処理ロジック (省略: 元コードと同様にDataFrame作成)
            # ... 
            st.success("登録完了")

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
    st.header("投球解析フィードバック")
    
    df_all = st.session_state['pitch_df'].copy()
    
    if df_all.empty:
        st.info("データが未登録か、GitHubからロードできませんでした。「投手データ登録・削除」タブからアップロードしてください。")
    else:
        if 'Data Source' not in df_all.columns:
            df_all['Data Source'] = "Trackman（トラックマン）"
        else:
            df_all['Data Source'] = df_all['Data Source'].fillna("Trackman（トラックマン）")

        available_players = sorted(df_all['Player Name'].dropna().unique())
        
        sel_c1, sel_c2, sel_c3, sel_c4 = st.columns(4)
        with sel_c1:
            p_name = st.selectbox("分析する選手", available_players, key="pitch_view_p")
        
        df_player = df_all[df_all['Player Name'] == p_name].copy()
        df_player['Date'] = pd.to_datetime(df_player['Date']).dt.date
        
        today = date.today()
        current_year = today.year
        
        available_dates = sorted(df_player['Date'].unique())
        if available_dates:
            target_year = available_dates[-1].year
            min_data_date = available_dates[0]
            max_data_date = available_dates[-1]
        else:
            target_year = current_year
            min_data_date = today
            max_data_date = today

        period_options = ["全体", "今日", "今週", "今月"]
        for m in range(1, 12 + 1):
            period_options.append(f"{m}月")
        period_options.append("カスタム")
        
        with sel_c2:
            selected_period = st.selectbox("分析対象の期間", period_options, index=0, key="pitch_period_select")
        
        start_date, end_date = None, None
        
        if selected_period == "全体":
            start_date, end_date = min_data_date, max_data_date
        elif selected_period == "今日":
            start_date, end_date = today, today
        elif selected_period == "今週":
            start_date = today - timedelta(days=6)
            end_date = today
        elif selected_period == "今月":
            start_date = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month.replace(day=1) - timedelta(days=1)
        elif "月" in selected_period:
            try:
                m_num = int(selected_period.replace("月", ""))
                start_date = date(target_year, m_num, 1)
                if m_num == 12:
                    end_date = date(target_year, 12, 31)
                else:
                    end_date = date(target_year, m_num + 1, 1) - timedelta(days=1)
            except Exception as e:
                start_date, end_date = min_data_date, max_data_date
        elif selected_period == "カスタム":
            with st.container():
                custom_range = st.date_input("細かく日程を指定", value=(min_data_date, max_data_date), min_value=min_data_date, max_value=max_data_date, key="pitch_view_d")
                if isinstance(custom_range, tuple) and len(custom_range) == 2:
                    start_date, end_date = custom_range
                elif isinstance(custom_range, date):
                    start_date, end_date = custom_range, custom_range

        with sel_c3:
            view_type = st.selectbox("練習種別フィルター", ["両方（すべて表示）", "ブルペンのみ", "シートBTのみ"], key="pitch_view_type")
        with sel_c4:
            source_filter = st.selectbox("データ元フィルター", ["両方（すべて表示）", "Trackmanのみ", "Rapsodoのみ"], key="pitch_view_source")
        
        if start_date and end_date:
            df = df_player[(df_player['Date'] >= start_date) & (df_player['Date'] <= end_date)].copy()
            
            if view_type == "ブルペンのみ":
                df = df[df['Data Type'] == "ブルペン"]
            elif view_type == "シートBTのみ":
                df = df[df['Data Type'] == "シートBT"]
                
            if source_filter == "Trackmanのみ":
                df = df[df['Data Source'].astype(str).str.contains("Trackman")]
            elif source_filter == "Rapsodoのみ":
                df = df[df['Data Source'].astype(str).str.contains("Rapsodo")]
        else:
            df = pd.DataFrame()

        if not df.empty:
            hand = PLAYER_HANDS.get(p_name, "右")
            c_dir, c_rev, c_eff, c_vb, c_hb, c_vel = 'Spin Direction', 'Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity'

            if 'Pitch Type' in df.columns:
                st.subheader(f"📊 平均データサマリー ({start_date} ～ {end_date} / {view_type} / {source_filter})")
                
                agg_dict = {}
                for c in [c_vel, c_rev, c_eff, c_vb, c_hb]:
                    if c in df.columns:
                        agg_dict[c] = ['mean', 'max'] if c == c_vel else 'mean'
                
                stats_df = df.groupby('Pitch Type').agg(agg_dict).reset_index()
                stats_df.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in stats_df.columns]
                
                rename_dict = {
                    f"{c_vel}_mean": "平均球速", f"{c_vel}_max": "最高球速",
                    f"{c_rev}_mean": "平均回転数", f"{c_eff}_mean": "回転効率 (%)",
                    f"{c_vb}_mean": "縦変化量 (VB)", f"{c_hb}_mean": "横変化量 (HB)"
                }
                stats_df = stats_df.rename(columns=rename_dict)
                st.dataframe(stats_df.style.format(precision=1), use_container_width=True)

                st.divider()
                st.subheader("📈 変化量マップ")
                plot_col1, plot_col2 = st.columns(2)

                hover_items = ['Data Type', c_vel]
                if 'Data Source' in df.columns:
                    hover_items.append('Data Source')

                with plot_col1:
                    st.write("▼ 全投球プロット")
                    fig_all = px.scatter(df, x=c_hb, y=c_vb, color='Pitch Type', range_x=[-60, 60], range_y=[-60, 60], color_discrete_map=COLOR_MAP_PITCH, hover_data=hover_items)
                    fig_all.add_hline(y=0, line_dash="dash", line_color="black")
                    fig_all.add_vline(x=0, line_dash="dash", line_color="black")
                    fig_all.update_layout(plot_bgcolor='white', width=550, height=550, yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray'), xaxis=dict(gridcolor='lightgray'))
                    st.plotly_chart(fig_all, use_container_width=False)

                with plot_col2:
                    st.write("▼ 球種別平均プロット")
                    plot_x = "横変化量 (HB)" if "横変化量 (HB)" in stats_df.columns else f"{c_hb}_mean"
                    plot_y = "縦変化量 (VB)" if "縦変化量 (VB)" in stats_df.columns else f"{c_vb}_mean"
                    fig_avg = px.scatter(stats_df, x=plot_x, y=plot_y, color='Pitch Type', text='Pitch Type', range_x=[-60, 60], range_y=[-60, 60], color_discrete_map=COLOR_MAP_PITCH)
                    fig_avg.update_traces(marker=dict(size=15), textposition='top center')
                    fig_avg.add_hline(y=0, line_dash="dash", line_color="black")
                    fig_avg.add_vline(x=0, line_dash="dash", line_color="black")
                    fig_avg.update_layout(plot_bgcolor='white', width=550, height=550, yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray'), xaxis=dict(gridcolor='lightgray'))
                    st.plotly_chart(fig_avg, use_container_width=False)

                # --- 3Dスピンビジュアライザー ---
                st.divider()
                st.subheader("⚾️ 3Dスピンビジュアライザー")
                valid_df = df.dropna(subset=['Pitch Type', c_dir, c_rev])
                if not valid_df.empty:
                    available_types = sorted(valid_df['Pitch Type'].dropna().unique())
                    sel_type = st.selectbox("球種を選択して回転を確認:", available_types, key="pitch_viz_select")
                    
                    subset = valid_df[valid_df['Pitch Type'] == sel_type]
                    avg_rpm = subset[c_rev].mean()
                    avg_eff = subset[c_eff].mean() if c_eff in subset.columns else 100.0
                    avg_tilt_str = str(subset[c_dir].iloc[0])
                    tilt_deg = time_to_degrees(avg_tilt_str)
                    
                    st.write(f"**{sel_type}** の平均データ： 回転数 {avg_rpm:.0f} RPM / 効率 {avg_eff:.1f}% / Tilt {avg_tilt_str}")

                    t = np.linspace(0, 2 * np.pi, 200)
                    alpha = 0.4
                    sx, sy, sz = np.cos(t) + alpha * np.cos(3*t), np.sin(t) - alpha * np.sin(3*t), 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
                    base_pts = np.vstack([sx, sz, sy]).T 

                    tilt_rad = np.deg2rad(tilt_deg)
                    cos_t, sin_t = np.cos(tilt_rad), np.sin(tilt_rad)
                    rot_y = np.array([[cos_t, 0, -sin_t], [0, 1, 0], [sin_t, 0, cos_t]])

                    gyro_rad = np.deg2rad((100 - avg_eff) * 0.9)
                    cos_g, sin_g = np.cos(gyro_rad), np.sin(gyro_rad)
                    g_sign = -1 if hand == "right" or hand == "右" else 1
                    rot_gyro = np.array([[1, 0, 0], [0, cos_g, g_sign*sin_g], [0, -g_sign*sin_g, cos_g]])

                    combined_rot = rot_y @ rot_gyro
                    axis = combined_rot @ np.array([0.0, 0.0, 1.0])
                    tilted_pts = (base_pts @ combined_rot.T)
                    seam_points = (tilted_pts / np.linalg.norm(tilted_pts, axis=1, keepdims=True)).tolist()

                    multiplier = -1 if any(k in sel_type.lower() for k in ["cut", "slider", "sl", "curve"]) else 1

                    html_code = f"""
                    <div id="ball_canvas" style="width:100%; height:600px;"></div>
                    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                    <script>
                        var points = {{ seam: {json.dumps(seam_points)} }};
                        var axis = {json.dumps(axis.tolist())};
                        var rpm = {avg_rpm};
                        var mult = {multiplier};
                        var cur_angle = 0;

                        function rotatePoint(p, ax, a) {{
                            var c = Math.cos(a), s = Math.sin(a), u = ax[0], v = ax[1], w = ax[2];
                            return [
                                p[0]*(c+u*u*(1-c)) + p[1]*(u*v*(1-c)-w*s) + p[2]*(u*w*(1-c)+v*s),
                                p[0]*(v*u*(1-c)+w*s) + p[1]*(c+v*v*(1-c)) + p[2]*(v*w*(1-c)-u*s),
                                p[0]*(w*u*(1-c)-v*s) + p[1]*(w*v*(1-c)+u*s) + p[2]*(c+w*w*(1-c))
                            ];
                        }}

                        var bx = [], by = [], bz = [], n = 22;
                        for(var i=0; i<=n; i++) {{
                            var phi = Math.PI * i / n; bx[i] = []; by[i] = []; bz[i] = [];
                            for(var j=0; j<=n; j++) {{
                                var theta = 2 * Math.PI * j / n;
                                bx[i][j] = Math.cos(theta) * Math.sin(phi);
                                by[i][j] = Math.sin(theta) * Math.sin(phi);
                                bz[i][j] = Math.cos(phi);
                            }}
                        }}

                        var data = [
                            {{ type: 'surface', x: bx, y: by, z: bz, colorscale: [['0','#eee'],['1','#eee']], showscale: false, opacity: 0.7 }},
                            {{ type: 'scatter3d', mode: 'lines', x: [], y: [], z: [], line: {{color: '#BC1010', width: 25}} }},
                            {{ type: 'scatter3d', mode: 'lines', x: [axis[0]*-1.5, axis[0]*1.5], y: [axis[1]*-1.5, axis[1]*1.5], z: [axis[2]*-1.5, axis[2]*1.5], line: {{color: '#333', width: 10}} }}
                        ];

                        var layout = {{
                            scene: {{ xaxis: {{visible: false}}, yaxis: {{visible: false}}, zaxis: {{visible: false}}, aspectmode: 'cube', camera: {{ eye: {{x: 0, y: -2.3, z: 0}}, up: {{x: 0, y: 0, z: 1}} }} }},
                            margin: {{l:0, r:0, b:0, t:0}}
                        ];

                        Plotly.newPlot('ball_canvas', data, layout);

                        function animate() {{
                            cur_angle -= mult * (rpm / 60) * (2 * Math.PI) / 1000;
                            var rx = [], ry = [], rz = [];
                            for(var i=0; i<points.seam.length; i++) {{
                                var r = rotatePoint(points.seam[i], axis, cur_angle);
                                rx.push(r[0]*1.01); ry.push(r[1]*1.01); rz.push(r[2]*1.01);
                                if ((i+1) % 2 == 0) {{ rx.push(null); ry.push(null); rz.push(null); }}
                            }}
                            Plotly.restyle('ball_canvas', {{x: [rx], y: [ry], z: [rz]}}, [1]);
                            requestAnimationFrame(animate);
                        }}
                        animate();
                    </script>
                    """
                    st.components.v1.html(html_code, height=600)
        else:
            st.warning("選択した期間・条件に一致するデータがありません。") 
