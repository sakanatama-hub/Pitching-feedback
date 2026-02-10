import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
from datetime import date

st.set_page_config(layout="wide")

# --- 設定・データ準備 ---
PLAYER_HANDS = {"#1 熊田 任洋": "左", "#2 逢澤 崚介": "左", "#3 三塚 武蔵": "左", "#4 北村 祥治": "右", "#5 前田 健伸": "左", "#6 佐藤 勇基": "右", "#7 西村 友哉": "右", "#8 和田 佳大": "左", "#9 今泉 颯太": "右", "#10 福井 章吾": "左", "#22 高祖 健輔": "左", "#23 箱山 遥人": "右", "#24 坂巻 尚哉": "右", "#26 西村 彰浩": "左", "#27 小畑 尋規": "右", "#28 宮崎 仁斗": "右", "#29 徳本 健太朗": "左", "#39 柳 元珍": "左", "#99 尾瀬 雄大": "左"}

NEW_PLAYERS = [
    "#11 大栄 陽斗", "#12 村上 凌久", "#13 細川 拓哉", "#14 ヴァデルナ・フェルガス",
    "#15 渕上 佳輝", "#16 後藤 凌寿", "#17 加藤 泰靖", "#18 市川 祐",
    "#19 高尾 響", "#20 嘉陽 宗一郎", "#21 池村 健太郎", "#30 平野 大智"
]
ALL_PLAYER_NAMES = sorted(list(PLAYER_HANDS.keys()) + NEW_PLAYERS)

if 'stored_data' not in st.session_state:
    st.session_state['stored_data'] = {}

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
    uploaded_file = st.file_uploader("CSVファイルをアップロード", type='csv', key="uploader_tab2")

    if uploaded_file is not None:
        if st.button("データを登録する"):
            new_df = pd.read_csv(uploaded_file, skiprows=4)
            if target_player not in st.session_state['stored_data']:
                st.session_state['stored_data'][target_player] = {}
            st.session_state['stored_data'][target_player][str(target_date)] = new_df
            st.success(f"{target_player} の {target_date} 分のデータを登録しました！")

# ==========================================
# タブ1：分析フィードバック
# ==========================================
with tab1:
    st.header("投球解析フィードバック")
    if not st.session_state['stored_data']:
        st.info("まずは「データ登録」タブからCSVをアップロードしてください。")
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

        if 'Pitch Type' in df.columns and len(existing_cols) > 0:
            st.subheader("📊 球種別データサマリー")
            stats_group = df.groupby('Pitch Type')[existing_cols].agg(['max', 'mean'])
            stats_df = stats_group.reset_index()
            new_columns = ['球種']
            for col, stat in stats_group.columns:
                new_columns.append(f"{col_map.get(col, col)}({'最大' if stat=='max' else '平均'})")
            stats_df.columns = new_columns
            st.dataframe(stats_df.style.format(precision=1), use_container_width=True)

        if 'VB (trajectory)' in df.columns and 'HB (trajectory)' in df.columns:
            st.divider()
            fig_map = px.scatter(df, x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                               labels={'HB (trajectory)': '横変化 (cm)', 'VB (trajectory)': '縦変化 (cm)', 'Pitch Type': '球種'})
            fig_map.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                               xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black', gridcolor='lightgray', range=[-60, 60]),
                               yaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black', gridcolor='lightgray', range=[-60, 60]),
                               height=500)
            st.plotly_chart(fig_map, use_container_width=True)

        if 'Spin Direction' in df.columns and 'Total Spin' in df.columns:
            st.divider()
            valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
            if not valid_data.empty:
                selected_type = st.selectbox("球種を選択:", sorted(valid_data['Pitch Type'].unique()))
                type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
                avg_rpm = type_subset['Total Spin'].mean()
                try:
                    eff_data = pd.to_numeric(type_subset.iloc[:, 10], errors='coerce').dropna()
                    avg_eff = eff_data.mean() if not eff_data.empty else 100.0
                except:
                    avg_eff = 100.0
                
                spin_str = str(type_subset.iloc[0]['Spin Direction'])
                hand = PLAYER_HANDS.get(display_player, "右")

                st.subheader(f"🔄 {selected_type} の回転詳細 ({hand}投げ)")
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("平均回転数", f"{int(avg_rpm)} rpm")
                col_b.metric("代表的な回転方向", f"{spin_str}")
                col_c.metric("平均回転効率", f"{avg_eff:.1f} %")

                try:
                    hour, minute = map(int, spin_str.split(':'))
                    total_min = (hour % 12) * 60 + minute
                    direction_deg = (total_min / 720) * 360
                    axis_deg = direction_deg + 90
                    axis_rad = np.deg2rad(axis_deg)
                    gyro_angle_rad = np.arccos(np.clip(avg_eff / 100.0, 0, 1))
                    base_x, base_y = np.sin(axis_rad), np.cos(axis_rad)
                    z_val = -np.sin(gyro_angle_rad) if hand == "右" else np.sin(gyro_angle_rad)
                    axis = [float(base_x * (avg_eff/100.0)), float(base_y * (avg_eff/100.0)), float(z_val)]
                    direction_rad = np.deg2rad(direction_deg)
                except:
                    axis = [1.0, 0.0, 0.0]; direction_rad = 0

                t_st = np.linspace(0, 2 * np.pi, 200)
                alpha = 0.4
                sx, sy = np.cos(t_st) + alpha * np.cos(3*t_st), np.sin(t_st) - alpha * np.sin(3*t_st)
                sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
                pts = np.vstack([sy, -sz, sx]).T 
                seam_points = (pts / np.linalg.norm(pts, axis=1, keepdims=True)).tolist()

                # JavaScriptの波括弧をすべて {{ }} に置換済み
                html_code = f"""
                <div id="chart" style="width:100%; height:600px;"></div>
                <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                <script>
                    var seam_base = {{ seam: {json.dumps(seam_points)} }};
                    var axis = {json.dumps(axis)};
                    var rpm = {avg_rpm};
                    var angle = 0;
                    function rotate(p, ax, a) {{
                        var c = Math.cos(a), s = Math.sin(a), dot = p[0]*ax[0] + p[1]*ax[1] + p[2]*ax[2];
                        var len = Math.sqrt(ax[0]*ax[0] + ax[1]*ax[1] + ax[2]*ax[2]);
                        var ux = ax[0]/len, uy = ax[1]/len, uz = ax[2]/len;
                        return [
                            p[0]*(c+ux*ux*(1-c)) + p[1]*(ux*uy*(1-c)-uz*s) + p[2]*(ux*uz*(1-c)+uy*s),
                            p[0]*(uy*ux*(1-c)+uz*s) + p[1]*(c+uy*uy*(1-c)) + p[2]*(uy*uz*(1-c)-ux*s),
                            p[0]*(uz*ux*(1-c)-uy*s) + p[1]*(uz*uy*(1-c)+ux*s) + p[2]*(c+uz*uz*(1-c))
                        ];
                    }}
                    var n=20; var bx=[], by=[], bz=[];
                    for(var i=0; i<=n; i++) {{
                        var v = Math.PI * i / n; bx[i]=[]; by[i]=[]; bz[i]=[];
                        for(var j=0; j<=n; j++) {{
                            var u = 2 * Math.PI * j / n;
                            bx[i][j] = Math.cos(u)*Math.sin(v); by[i][j] = Math.sin(u)*Math.sin(v); bz[i][j] = Math.cos(v);
                        }}
                    }}
                    var data = [
                        {{ 
                            type: 'surface', x: bx, y: by, z: bz, 
                            colorscale: [['0','#FFFFFF'],['1','#FFFFFF']], 
                            showscale: false, opacity: 0.6, 
                            lighting: {{ambient: 0.8, diffuse: 0.5, specular: 0.1, roughness: 1.0}} 
                        }},
                        {{ type: 'scatter3d', mode: 'lines', x: [], y: [], z: [], line: {{color: '#BC1010', width: 35}} }},
                        {{ type: 'scatter3d', mode: 'lines', x: [axis[0]*-1.7, axis[0]*1.7], y: [axis[1]*-1.7, axis[1]*1.7], z: [axis[2]*-1.7, axis[2]*1.7], line: {{color: '#000000', width: 15}} }}
                    ];
                    var layout = {{
                        scene: {{ xaxis:{{visible:false, range:[-1.7,1.7]}}, yaxis:{{visible:false, range:[-1.7,1.7]}}, zaxis:{{visible:false, range:[-1.7,1.7]}}, aspectmode:'cube', camera:{{eye:{{x:0, y:0, z:2.2}}, up:{{x:0, y:1, z:0}}}}, dragmode:false }},
                        margin: {{l:0, r:0, b:0, t:0}}, showlegend: false
                    }};
                    Plotly.newPlot('chart', data, layout);
                    function update() {{
                        angle += (rpm / 60) * (2 * Math.PI) / 1000;
                        var rx=[], ry=[], rz=[];
                        for(var i=0; i<seam_base.seam.length; i++) {{
                            var p = seam_base.seam[i];
                            var r_init = rotate(p, [0,0,1], {direction_rad});
                            var r = rotate(r_init, axis, angle);
                            rx.push(r[0]*1.02); ry.push(r[1]*1.02); rz.push(r[2]*1.02);
                            if ((i+1) % 2 == 0) {{ rx.push(null); ry.push(null); rz.push(null); }}
                        }}
                        Plotly.restyle('chart', {{x: [rx], y: [ry], z: [rz]}}, [1]);
                        requestAnimationFrame(update);
                    }}
                    update();
                </script>
                """
                st.components.v1.html(html_code, height=600)
