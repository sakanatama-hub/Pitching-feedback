import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import date
import re

st.set_page_config(layout="wide")

# --- 設定・データ準備 (投手リスト) ---
PLAYER_HANDS = {
    "#11 大栄 陽斗": "右", "#12 村上 崚久": "右", "#13 細川 拓哉": "右", 
    "#14 ヴァデルナ・フェルガス": "左", "#15 渕上 佳輝": "右", "#16 後藤 凌寿": "右", 
    "#17 加藤 泰靖": "右", "#18 市川 祐": "右", "#19 高尾 響": "右", 
    "#20 嘉陽 宗一郎": "右", "#21 池村 健太郎": "右", "#30 平野 大智": "右"
}

ALL_PLAYER_NAMES = list(PLAYER_HANDS.keys())

if 'stored_data' not in st.session_state:
    st.session_state['stored_data'] = {}

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

tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 データ登録"])

# ==========================================
# タブ2：データ登録
# ==========================================
with tab2:
    st.header("選手データ登録")
    col_reg1, col_reg2 = st.columns(2)
    with col_reg1:
        target_player = st.selectbox("選手を選択", ALL_PLAYER_NAMES)
        target_date = st.date_input("測定日を選択", date.today())
    uploaded_file = st.file_uploader("ファイルをアップロード", type=['csv', 'xlsx', 'xls'], key="uploader_tab2")

    if uploaded_file is not None:
        if st.button("データを登録する"):
            try:
                if uploaded_file.name.endswith('.csv'):
                    new_df = pd.read_csv(uploaded_file, skiprows=4)
                else:
                    new_df = pd.read_excel(uploaded_file, skiprows=4)
                if target_player not in st.session_state['stored_data']:
                    st.session_state['stored_data'][target_player] = {}
                st.session_state['stored_data'][target_player][str(target_date)] = new_df
                st.success(f"{target_player} の {target_date} 分のデータを登録しました！")
            except Exception as e:
                st.error(f"エラー: {e}")

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
            display_player = st.selectbox("分析する選手", list(st.session_state['stored_data'].keys()))
        with sel_col2:
            display_date = st.selectbox("日付を選択", list(st.session_state['stored_data'][display_player].keys()))
        
        df = st.session_state['stored_data'][display_player][display_date].copy()
        hand = PLAYER_HANDS.get(display_player, "右")

        c_dir = 'Spin Direction'
        c_rev = 'True Spin (release)'
        c_eff = 'Spin Efficiency (release)'
        c_vb = 'VB (trajectory)'
        c_hb = 'HB (trajectory)'

        for c in [c_rev, c_eff, c_vb, c_hb]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace('%', ''), errors='coerce')

        if 'Pitch Type' in df.columns:
            st.subheader("📊 球種別データサマリー (平均値)")
            display_cols = [c for c in [c_rev, c_eff, c_vb, c_hb] if c in df.columns]
            stats_group = df.groupby('Pitch Type')[display_cols].mean()
            st.dataframe(stats_group.style.format(precision=1), use_container_width=True)

        if c_vb in df.columns and c_hb in df.columns:
            st.divider()
            st.subheader("📈 変化量マップ")
            fig_map = px.scatter(df, x=c_hb, y=c_vb, color='Pitch Type')
            fig_map.update_layout(plot_bgcolor='white', paper_bgcolor='white', height=600)
            st.plotly_chart(fig_map, use_container_width=True)

        # ==========================================
        # 3. スピンビジュアライザー (逆回転ロジック搭載)
        # ==========================================
        if c_dir in df.columns and c_rev in df.columns:
            st.divider()
            st.subheader("⚾️ スピンビジュアライザー")
            
            check_cols = [c for c in [c_dir, c_rev, c_eff] if c in df.columns]
            valid_data = df.dropna(subset=check_cols)
            
            if not valid_data.empty:
                selected_type = st.selectbox("球種を選択して回転を確認:", sorted(valid_data['Pitch Type'].unique()))
                type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
                
                avg_rpm = type_subset[c_rev].mean()
                avg_eff = type_subset[c_eff].mean() if c_eff in type_subset.columns else 100.0
                avg_dir_str = type_subset[c_dir].iloc[0] 
                tilt_deg = time_to_degrees(avg_dir_str)

                # --- 回転の「向き」を球種で判定 ---
                # カット(Cut)、スライダー(Slider)、カーブ(Curve)系はトップスピン/ジャイロ成分として逆転させる判定
                # ※現場の運用に合わせてキーワードを調整してください
                is_reverse = any(keyword in selected_type.lower() for keyword in ["cut", "slider", "sl", "ct"])
                spin_multiplier = -1 if is_reverse else 1
                
                st.write(f"**表示データ平均**: {avg_rpm:.0f} RPM / 効率 {avg_eff:.1f}% / 回転方向 {avg_dir_str} ({'逆回転' if is_reverse else '正回転'})")

                # --- 物理計算 ---
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
                        // multiplierによって回転方向を切り替え
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
