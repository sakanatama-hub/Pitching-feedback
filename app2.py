import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import date
import re
import os
import pickle

# --- ページ設定 ---
st.set_page_config(layout="wide", page_title="投球解析システム (Rapsodo/Trackman対応)")

# --- データの永続化設定 ---
DATA_FILE = "pitch_data_storage.pkl"

def load_persistent_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "rb") as f:
                return pickle.load(f)
        except:
            return {}
    return {}

def save_persistent_data(data):
    try:
        with open(DATA_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        st.error(f"データの保存に失敗しました: {e}")

if 'stored_data' not in st.session_state:
    st.session_state['stored_data'] = load_persistent_data()

# 投手リスト
PLAYER_HANDS = {
    "#11 大栄 陽斗": "右", "#12 村上 崚久": "右", "#13 細川 拓哉": "右", 
    "#14 ヴァデルナ・フェルガス": "左", "#15 渕上 佳輝": "右", "#16 後藤 凌寿": "右", 
    "#17 加藤 泰靖": "右", "#18 市川 祐": "右", "#19 高尾 響": "右", 
    "#20 嘉陽 宗一郎": "右", "#21 池村 健太郎": "右", "#30 平野 大智": "右"
}
ALL_PLAYER_NAMES = list(PLAYER_HANDS.keys())

# カラム名マッピング
COLUMN_MAP = {
    'TaggedPitchType': 'Pitch Type',
    'RelSpeed': 'Velocity',
    'SpinRate': 'Spin Rate',
    'Tilt': 'Spin Direction',
    'InducedVertBreak': 'VB',
    'HorzBreak': 'HB',
    'SpinEfficiency': 'Spin Efficiency',
    'True Spin (release)': 'Spin Rate',
    'Spin Efficiency (release)': 'Spin Efficiency',
    'VB (trajectory)': 'VB',
    'HB (trajectory)': 'HB'
}

def time_to_degrees(time_str):
    try:
        match = re.match(r"(\d+):(\d+)", str(time_str))
        if not match: return 0.0
        hh, mm = map(int, match.groups())
        total_minutes = (hh % 12) * 60 + mm
        return total_minutes * 0.5
    except:
        return 0.0

tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 データ登録"])

# ==========================================
# タブ2：データ登録
# ==========================================
with tab2:
    st.header("データ登録 (Rapsodo / Trackman)")
    col_reg1, col_reg2 = st.columns(2)
    with col_reg1:
        target_player = st.selectbox("選手を選択", ALL_PLAYER_NAMES, key="reg_p")
        target_date = st.date_input("測定日を選択", date.today(), key="reg_d")
    
    uploaded_file = st.file_uploader("CSVファイルをアップロード", type=['csv'])

    if uploaded_file is not None:
        if st.button("データを登録・蓄積する"):
            try:
                temp_df = pd.read_csv(uploaded_file, nrows=10, header=None)
                skip = 0
                for i, row in temp_df.iterrows():
                    row_str = row.astype(str).values
                    if any(k in s for s in row_str for k in ["PitchNo", "Pitcher", "TaggedPitchType"]):
                        skip = i
                        break
                uploaded_file.seek(0)
                new_df = pd.read_csv(uploaded_file, skiprows=skip)

                new_df = new_df.rename(columns=COLUMN_MAP)
                cols_to_num = ['Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity']
                for c in cols_to_num:
                    if c in new_df.columns:
                        new_df[c] = pd.to_numeric(new_df[c].astype(str).str.replace('%', ''), errors='coerce')

                if target_player not in st.session_state['stored_data']:
                    st.session_state['stored_data'][target_player] = {}
                
                date_key = str(target_date)
                if date_key in st.session_state['stored_data'][target_player]:
                    existing = st.session_state['stored_data'][target_player][date_key]
                    new_df = pd.concat([existing, new_df], ignore_index=True).drop_duplicates()
                
                st.session_state['stored_data'][target_player][date_key] = new_df
                save_persistent_data(st.session_state['stored_data'])
                st.success(f"{target_player} のデータを保存しました。")
                st.balloons()
            except Exception as e:
                st.error(f"読み込みエラー: {e}")

# ==========================================
# タブ1：分析フィードバック
# ==========================================
with tab1:
    st.header("投球解析フィードバック")
    
    if not st.session_state['stored_data']:
        st.info("データが登録されていません。")
    else:
        c1, c2 = st.columns(2)
        with c1:
            p_name = st.selectbox("選手", sorted(st.session_state['stored_data'].keys()))
        with c2:
            p_date = st.selectbox("日付", sorted(st.session_state['stored_data'][p_name].keys(), reverse=True))
        
        df = st.session_state['stored_data'][p_name][p_date].copy()
        hand = PLAYER_HANDS.get(p_name, "右")

        c_dir, c_rev, c_eff, c_vb, c_hb = 'Spin Direction', 'Spin Rate', 'Spin Efficiency', 'VB', 'HB'

        if 'Pitch Type' in df.columns:
            st.subheader("📊 平均データ")
            stats_cols = [c for c in [c_rev, c_eff, c_vb, c_hb] if c in df.columns]
            st.dataframe(df.groupby('Pitch Type')[stats_cols].mean().style.format(precision=1), use_container_width=True)

            # --- 変化量マップ (正方形・範囲指定版) ---
            st.divider()
            st.subheader("📈 変化量マップ")
            
            # グラフの作成
            fig = px.scatter(
                df, x=c_hb, y=c_vb, color='Pitch Type',
                hover_data=['Velocity'] if 'Velocity' in df.columns else None,
                # 軸の範囲を -60 から 60 に設定
                range_x=[-60, 60], range_y=[-60, 60]
            )

            # ゼロ線の追加
            fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1)
            fig.add_vline(x=0, line_dash="dash", line_color="black", line_width=1)

            # 正方形（アスペクト比 1:1）に固定し、グリッドを見やすく設定
            fig.update_layout(
                plot_bgcolor='white',
                width=700, height=700, # 描画エリア自体を正方形に近づける
                yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray'),
                xaxis=dict(gridcolor='lightgray'),
                xaxis_title="Horizontal Break (HB)",
                yaxis_title="Vertical Break (VB)"
            )
            
            st.plotly_chart(fig, use_container_width=False) # container無視で指定サイズ優先

            # --- 3Dスピンビジュアライザー ---
            st.divider()
            st.subheader("⚾️ 3Dスピンビジュアライザー")
            valid_df = df.dropna(subset=['Pitch Type', c_dir, c_rev])
            if not valid_df.empty:
                sel_type = st.selectbox("確認する球種を選択:", sorted(valid_df['Pitch Type'].dropna().unique()))
                subset = valid_df[valid_df['Pitch Type'] == sel_type]
                
                avg_rpm = subset[c_rev].mean()
                avg_eff = subset[c_eff].mean() if c_eff in subset.columns else 100.0
                avg_tilt = str(subset[c_dir].iloc[0])
                tilt_deg = time_to_degrees(avg_tilt)
                
                st.write(f"平均回転数: {avg_rpm:.0f} RPM | 効率: {avg_eff:.1f}% | Tilt: {avg_tilt}")

                t = np.linspace(0, 2 * np.pi, 200)
                alpha = 0.4
                sx, sy, sz = np.cos(t) + alpha * np.cos(3*t), np.sin(t) - alpha * np.sin(3*t), 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
                base_pts = np.vstack([sz, sx, sy]).T 

                tilt_rad = np.deg2rad(tilt_deg)
                cos_t, sin_t = np.cos(tilt_rad), np.sin(tilt_rad)
                rot_z = np.array([[cos_t, sin_t, 0], [-sin_t, cos_t, 0], [0, 0, 1]])
                gyro_rad = np.deg2rad((100 - avg_eff) * 0.9)
                cos_g, sin_g = np.cos(gyro_rad), np.sin(gyro_rad)
                g_sign = 1 if hand == "右" else -1
                rot_gyro = np.array([[cos_g, 0, g_sign*sin_g], [0, 1, 0], [-g_sign*sin_g, 0, cos_g]])

                combined_rot = rot_gyro @ rot_z
                axis = combined_rot @ np.array([1.0, 0.0, 0.0])
                tilted_pts = (base_pts @ combined_rot.T)
                seam_points = (tilted_pts / np.linalg.norm(tilted_pts, axis=1, keepdims=True)).tolist()
                multiplier = -1 if any(k in sel_type.lower() for k in ["cut", "slider", "sl", "curve"]) else 1

                html_code = f"""
                <div id="canvas_3d" style="width:100%; height:600px;"></div>
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <script>
                    var points = {{ seam: {json.dumps(seam_points)} }};
                    var axis = {json.dumps(axis.tolist())};
                    var rpm = {avg_rpm};
                    var mult = {multiplier};
                    var cur_angle = 0;
                    function rot_p(p, ax, a) {{
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
                            bx[i][j] = Math.cos(theta) * Math.sin(phi); by[i][j] = Math.sin(theta) * Math.sin(phi); bz[i][j] = Math.cos(phi);
                        }}
                    }}
                    var data = [
                        {{ type: 'surface', x: bx, y: by, z: bz, colorscale: [['0','#eee'],['1','#eee']], showscale: false, opacity: 0.7 }},
                        {{ type: 'scatter3d', mode: 'lines', x: [], y: [], z: [], line: {{color: '#BC1010', width: 25}} }},
                        {{ type: 'scatter3d', mode: 'lines', x: [axis[0]*-1.5, axis[0]*1.5], y: [axis[1]*-1.5, axis[1]*1.5], z: [axis[2]*-1.5, axis[2]*1.5], line: {{color: '#333', width: 10}} }}
                    ];
                    var layout = {{
                        scene: {{ xaxis: {{visible: false}}, yaxis: {{visible: false}}, zaxis: {{visible: false}}, aspectmode: 'cube', camera: {{ eye: {{x: 0, y: 0, z: 2.3}} }} }},
                        margin: {{l:0, r:0, b:0, t:0}}
                    }};
                    Plotly.newPlot('canvas_3d', data, layout);
                    function animate() {{
                        cur_angle += mult * (rpm / 60) * (2 * Math.PI) / 1000;
                        var rx = [], ry = [], rz = [];
                        for(var i=0; i<points.seam.length; i++) {{
                            var r = rot_p(points.seam[i], axis, cur_angle);
                            rx.push(r[0]*1.01); ry.push(r[1]*1.01); rz.push(r[2]*1.01);
                            if ((i+1) % 2 == 0) {{ rx.push(null); ry.push(null); rz.push(null); }}
                        }}
                        Plotly.restyle('canvas_3d', {{x: [rx], y: [ry], z: [rz]}}, [1]);
                        requestAnimationFrame(animate);
                    }}
                    animate();
                </script>
                """
                st.components.v1.html(html_code, height=600)
