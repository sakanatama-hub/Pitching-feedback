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
st.set_page_config(layout="wide", page_title="投球解析システム")

# --- 保存用ファイルのパス設定 ---
# ローカル実行環境（PC内）でデータが蓄積されます
DATA_FILE = "pitch_data_storage.pkl"

# --- 永続化のための関数 ---
def load_persistent_data():
    """保存ファイルからデータを読み込む"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            st.error(f"データの読み込みに失敗しました: {e}")
            return {}
    return {}

def save_persistent_data(data):
    """データをファイルに保存する"""
    try:
        with open(DATA_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        st.error(f"データの保存に失敗しました: {e}")

# --- セッション状態の初期化 ---
if 'stored_data' not in st.session_state:
    st.session_state['stored_data'] = load_persistent_data()

# --- 設定・データ準備 (投手リスト) ---
PLAYER_HANDS = {
    "#11 大栄 陽斗": "右", "#12 村上 崚久": "右", "#13 細川 拓哉": "右", 
    "#14 ヴァデルナ・フェルガス": "左", "#15 渕上 佳輝": "右", "#16 後藤 凌寿": "右", 
    "#17 加藤 泰靖": "右", "#18 市川 祐": "右", "#19 高尾 響": "右", 
    "#20 嘉陽 宗一郎": "右", "#21 池村 健太郎": "右", "#30 平野 大智": "右"
}

ALL_PLAYER_NAMES = list(PLAYER_HANDS.keys())

def time_to_degrees(time_str):
    """'12:15' のような形式を角度(12:00基準)に変換"""
    try:
        match = re.match(r"(\d+):(\d+)", str(time_str))
        if not match: return 0.0
        hh, mm = map(int, match.groups())
        total_minutes = (hh % 12) * 60 + mm
        return total_minutes * 0.5
    except:
        return 0.0

# タブ構成
tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 データ登録"])

# ==========================================
# タブ2：データ登録 (蓄積ロジック)
# ==========================================
with tab2:
    st.header("選手データ登録")
    st.info("アップロードしたデータは自動的に蓄積され、次回起動時も保持されます。")
    
    col_reg1, col_reg2 = st.columns(2)
    with col_reg1:
        target_player = st.selectbox("選手を選択", ALL_PLAYER_NAMES, key="reg_player")
        target_date = st.date_input("測定日を選択", date.today(), key="reg_date")
    
    uploaded_file = st.file_uploader("ファイルをアップロード (CSV/Excel)", type=['csv', 'xlsx', 'xls'], key="uploader_tab2")

    if uploaded_file is not None:
        if st.button("データを登録・蓄積する"):
            try:
                # データの読み込み
                if uploaded_file.name.endswith('.csv'):
                    new_df = pd.read_csv(uploaded_file, skiprows=4)
                else:
                    new_df = pd.read_excel(uploaded_file, skiprows=4)
                
                # --- データクレンジング (保存前に実施) ---
                cols_to_fix = [
                    'True Spin (release)', 
                    'Spin Efficiency (release)', 
                    'VB (trajectory)', 
                    'HB (trajectory)'
                ]
                for c in cols_to_fix:
                    if c in new_df.columns:
                        new_df[c] = pd.to_numeric(new_df[c].astype(str).str.replace('%', ''), errors='coerce')

                # --- 蓄積ロジック ---
                if target_player not in st.session_state['stored_data']:
                    st.session_state['stored_data'][target_player] = {}
                
                date_key = str(target_date)
                if date_key in st.session_state['stored_data'][target_player]:
                    # 既存データがある場合は結合して重複削除
                    existing_df = st.session_state['stored_data'][target_player][date_key]
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True).drop_duplicates()
                    st.session_state['stored_data'][target_player][date_key] = combined_df
                else:
                    # 新規登録
                    st.session_state['stored_data'][target_player][date_key] = new_df
                
                # ファイルへ書き出し（永続化）
                save_persistent_data(st.session_state['stored_data'])
                
                st.success(f"✅ {target_player} の {date_key} 分のデータを保存しました！")
                st.balloons()
            except Exception as e:
                st.error(f"登録エラー: {e}")

# ==========================================
# タブ1：分析フィードバック
# ==========================================
with tab1:
    st.header("投球解析フィードバック")
    
    if not st.session_state['stored_data']:
        st.info("「データ登録」タブからファイルをアップロードしてください。")
    else:
        sel_col1, sel_col2 = st.columns(2)
        with sel_col1:
            display_player = st.selectbox("分析する選手", sorted(list(st.session_state['stored_data'].keys())))
        with sel_col2:
            display_date = st.selectbox("日付を選択", sorted(list(st.session_state['stored_data'][display_player].keys()), reverse=True))
        
        df = st.session_state['stored_data'][display_player][display_date].copy()
        hand = PLAYER_HANDS.get(display_player, "右")

        # カラム定義
        c_dir = 'Spin Direction'
        c_rev = 'True Spin (release)'
        c_eff = 'Spin Efficiency (release)'
        c_vb = 'VB (trajectory)'
        c_hb = 'HB (trajectory)'

        # 球種別サマリー
        if 'Pitch Type' in df.columns:
            st.subheader("📊 球種別データサマリー (平均値)")
            display_cols = [c for c in [c_rev, c_eff, c_vb, c_hb] if c in df.columns]
            stats_group = df.groupby('Pitch Type')[display_cols].mean()
            st.dataframe(stats_group.style.format(precision=1), use_container_width=True)

        # 変化量マップ
        if c_vb in df.columns and c_hb in df.columns:
            st.divider()
            st.subheader("📈 変化量マップ")
            fig_map = px.scatter(
                df, x=c_hb, y=c_vb, color='Pitch Type',
                hover_data=['Velocity (release)'] if 'Velocity (release)' in df.columns else None
            )
            # 野球のグラフらしく十字線を引く
            fig_map.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_map.add_vline(x=0, line_dash="dash", line_color="gray")
            fig_map.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=600)
            st.plotly_chart(fig_map, use_container_width=True)

        # スピンビジュアライザー
        if c_dir in df.columns and c_rev in df.columns:
            st.divider()
            st.subheader("⚾️ スピンビジュアライザー")
            
            valid_data = df.dropna(subset=[c_dir, c_rev])
            if not valid_data.empty:
                selected_type = st.selectbox("球種を選択して回転を確認:", sorted(valid_data['Pitch Type'].unique()))
                type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
                
                avg_rpm = type_subset[c_rev].mean()
                avg_eff = type_subset[c_eff].mean() if c_eff in type_subset.columns else 100.0
                avg_dir_str = type_subset[c_dir].iloc[0] 
                tilt_deg = time_to_degrees(avg_dir_str)

                # 回転方向の判定 (カット・スライダー・カーブ系は逆回転判定)
                is_reverse = any(keyword in selected_type.lower() for keyword in ["cut", "slider", "sl", "ct", "curve"])
                spin_multiplier = -1 if is_reverse else 1
                
                st.write(f"**表示データ平均**: {avg_rpm:.0f} RPM / 効率 {avg_eff:.1f}% / 回転方向 {avg_dir_str}")

                # --- 3D描画ロジック ---
                t_st = np.linspace(0, 2 * np.pi, 200)
                alpha = 0.4
                sx = np.cos(t_st) + alpha * np.cos(3*t_st)
                sy = np.sin(t_st) - alpha * np.sin(3*t_st)
                sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
                base_pts = np.vstack([sz, sx, sy]).T 

                tilt_rad = np.deg2rad(tilt_deg)
                cos_t, sin_t = np.cos(tilt_rad), np.sin(tilt_rad)
                rot_z = np.array([[cos_t, sin_t, 0], [-sin_t, cos_t, 0], [0, 0, 1]])

                gyro_deg = (100 - avg_eff) * 0.9
                gyro_rad = np.deg2rad(gyro_deg)
                cos_g, sin_g = np.cos(gyro_rad), np.sin(gyro_rad)
                
                if hand == "右":
                    rot_gyro = np.array([[cos_g, 0, sin_g], [0, 1, 0], [-sin_g, 0, cos_g]])
                else:
                    rot_gyro = np.array([[cos_g, 0, -sin_g], [0, 1, 0], [sin_g, 0, cos_g]])

                combined_rot = rot_gyro @ rot_z
                axis = combined_rot @ np.array([1.0, 0.0, 0.0])
                tilted_pts = (base_pts @ combined_rot.T)
                seam_points = (tilted_pts / np.linalg.norm(tilted_pts, axis=1, keepdims=True)).tolist()

                # JavaScript部分。Pythonのf-stringの展開を防ぐため {{ }} を使用。
                html_code = f"""
                <div id="chart" style="width:100%; height:600px;"></div>
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <script>
                    var seam_base = {{ seam: {json.dumps(seam_points)} }};
                    var axis = {json.dumps(axis.tolist())};
                    var rpm = {avg_rpm};
                    var multiplier = {spin_multiplier};
                    var angle = 0;

                    function rotate(p, ax, a) {{
                        var c = Math.cos(a), s = Math.sin(a);
                        var ux = ax[0], uy = ax[1], uz = ax[2];
                        return [
                            p[0]*(c+ux*ux*(1-c)) + p[1]*(ux*uy*(1-c)-uz*s) + p[2]*(ux*uz*(1-c)+uy*s),
                            p[0]*(uy*ux*(1-c)+uz*s) + p[1]*(c+uy*uy*(1-c)) + p[2]*(uy*uz*(1-c)-ux*s),
                            p[0]*(uz*ux*(1-c)-uy*s) + p[1]*(uz*uy*(1-c)+ux*s) + p[2]*(c+uz*uz*(1-c))
                        ];
                    }}

                    var bx = [], by = [], bz = [];
                    var n = 20;
                    for(var i=0; i<=n; i++) {{
                        var v = Math.PI * i / n; bx[i] = []; by[i] = []; bz[i] = [];
                        for(var j=0; j<=n; j++) {{
                            var u = 2 * Math.PI * j / n;
                            bx[i][j] = Math.cos(u) * Math.sin(v); by[i][j] = Math.sin(u) * Math.sin(v); bz[i][j] = Math.cos(v);
                        }}
                    }}

                    var data = [
                        {{ type: 'surface', x: bx, y: by, z: bz, colorscale: [['0','#FFFFFF'],['1','#FFFFFF']], showscale: false, opacity: 0.6 }},
                        {{ type: 'scatter3d', mode: 'lines', x: [], y: [], z: [], line: {{color: '#BC1010', width: 30}} }},
                        {{ type: 'scatter3d', mode: 'lines', x: [axis[0]*-1.7, axis[0]*1.7], y: [axis[1]*-1.7, axis[1]*1.7], z: [axis[2]*-1.7, axis[2]*1.7], line: {{color: '#000000', width: 15}} }}
                    ];

                    var layout = {{
                        scene: {{
                            xaxis: {{visible: false, range: [-1.7, 1.7]}}, yaxis: {{visible: false, range: [-1.7, 1.7]}}, zaxis: {{visible: false, range: [-1.7, 1.7]}},
                            aspectmode: 'cube', camera: {{ eye: {{x: 0, y: 0, z: 2.2}}, up: {{x: 0, y: 1, z: 0}} }}, dragmode: false
                        }},
                        margin: {{l:0, r:0, b:0, t:0}}
                    }};

                    Plotly.newPlot('chart', data, layout);

                    function update() {{
                        angle += multiplier * (rpm / 60) * (2 * Math.PI) / 1000; 
                        var rx = [], ry = [], rz = [];
                        for(var i=0; i<seam_base.seam.length; i++) {{
                            var r = rotate(seam_base.seam[i], axis, angle);
                            rx.push(r[0]*1.01); ry.push(r[1]*1.01); rz.push(r[2]*1.01);
                            if ((i+1) % 2 == 0) {{ rx.push(null); ry.push(null); rz.push(null); }}
                        }}
                        Plotly.restyle('chart', {{x: [rx], y: [ry], z: [rz]}}, [1]);
                        requestAnimationFrame(update);
                    }}
                    update();
                </script>
                """
                st.components.v1.html(html_code, height=600)
