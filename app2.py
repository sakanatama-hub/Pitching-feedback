import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import date

st.set_page_config(layout="wide")

# --- 設定・データ準備 (投手リスト) ---
PLAYER_HANDS = {
    "#11 大栄 陽斗": "右", "#12 村上 凌久": "右", "#13 細川 拓哉": "右", 
    "#14 ヴァデルナ・フェルガス": "左", "#15 渕上 佳輝": "右", "#16 後藤 凌寿": "右", 
    "#17 加藤 泰靖": "右", "#18 市川 祐": "右", "#19 高尾 響": "右", 
    "#20 嘉陽 宗一郎": "右", "#21 池村 健太郎": "右", "#30 平野 大智": "右"
}

ALL_PLAYER_NAMES = list(PLAYER_HANDS.keys())

if 'stored_data' not in st.session_state:
    st.session_state['stored_data'] = {}

tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 データ登録"])

# ==========================================
# タブ2：データ登録 (そのまま)
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
        
        df = st.session_state['stored_data'][display_player][display_date]

        col_map = {'Velocity': '球速', 'Total Spin': '回転数', 'Spin Efficiency': 'スピン効率', 'VB (trajectory)': '縦変化量', 'HB (trajectory)': '横変化量'}
        existing_cols = [c for c in col_map.keys() if c in df.columns]
        for col in existing_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 1. サマリー表示 (そのまま)
        if 'Pitch Type' in df.columns and len(existing_cols) > 0:
            st.subheader("📊 球種別データサマリー (最大 & 平均)")
            stats_group = df.groupby('Pitch Type')[existing_cols].agg(['max', 'mean'])
            stats_df = stats_group.reset_index()
            new_columns = ['球種']
            for col, stat in stats_group.columns:
                new_columns.append(f"{col_map.get(col, col)}({'最大' if stat=='max' else '平均'})")
            stats_df.columns = new_columns
            st.dataframe(stats_df.style.format(precision=1), use_container_width=True)

        # 2. 変化量マップ (復元)
        if 'VB (trajectory)' in df.columns and 'HB (trajectory)' in df.columns:
            st.divider()
            st.subheader("📈 変化量マップ (ムーブメントチャート)")
            fig_map = px.scatter(df, x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                               labels={'HB (trajectory)': '横変化 (cm)', 'VB (trajectory)': '縦変化 (cm)', 'Pitch Type': '球種'})
            fig_map.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                               xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black', gridcolor='lightgray', range=[-60, 60]),
                               yaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black', gridcolor='lightgray', range=[-60, 60]),
                               height=600)
            st.plotly_chart(fig_map, use_container_width=True)

        # ==========================================
        # 4. スピンビジュアライザー (位置関係の再調整)
        # ==========================================
        if 'Spin Direction' in df.columns and 'Total Spin' in df.columns:
            st.divider()
            valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
            if not valid_data.empty:
                selected_type = st.selectbox("球種を選択:", sorted(valid_data['Pitch Type'].unique()))
                type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
                avg_rpm = type_subset['Total Spin'].mean()
                
                # --- 縫い目定義 ---
                t_st = np.linspace(0, 2 * np.pi, 200)
                alpha = 0.4
                sx = np.cos(t_st) + alpha * np.cos(3*t_st)
                sy = np.sin(t_st) - alpha * np.sin(3*t_st)
                sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
                
                # 軸[1, 0, 0]が Uの開口部の中心 と 膨らみの頂点 を貫くように配置
                # 座標を入れ替えて、X軸がUのど真ん中を刺すように調整
                pts = np.vstack([sx, sy, sz]).T 
                seam_points = (pts / np.linalg.norm(pts, axis=1, keepdims=True)).tolist()

                # まずは水平[1, 0, 0]で固定
                axis = [1.0, 0.0, 0.0]

                html_code = f"""
                <div id="chart" style="width:100%; height:600px;"></div>
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <script>
                    var seam_base = {{ seam: {json.dumps(seam_points)} }};
                    var axis = {json.dumps(axis)};
                    var rpm = {avg_rpm};
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

                    var n = 20; var bx = [], by = [], bz = [];
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
                        {{ type: 'scatter3d', mode: 'lines', x: [-1.7, 1.7], y: [0, 0], z: [0, 0], line: {{color: '#000000', width: 15}} }}
                    ];

                    var layout = {{
                        scene: {{
                            xaxis: {{visible: false, range: [-1.7, 1.7]}}, yaxis: {{visible: false, range: [-1.7, 1.7]}}, zaxis: {{visible: false, range: [-1.7, 1.7]}},
                            aspectmode: 'cube', camera: {{ eye: {{x: 0, y: 0, z: 2.2}} }}
                        }},
                        margin: {{l:0, r:0, b:0, t:0}}
                    }};

                    Plotly.newPlot('chart', data, layout);

                    function update() {{
                        angle += (rpm / 60) * (2 * Math.PI) / 1000; 
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
