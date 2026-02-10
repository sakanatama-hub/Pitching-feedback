import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：ジャイロ回転・効率加味モデル")

# 保存された利き腕情報
PLAYER_HANDS = {"#1 熊田 任洋": "左", "#2 逢澤 崚介": "左", "#3 三塚 武蔵": "左", "#4 北村 祥治": "右", "#5 前田 健伸": "左", "#6 佐藤 勇基": "右", "#7 西村 友哉": "右", "#8 和田 佳大": "左", "#9 今泉 颯太": "右", "#10 福井 章吾": "左", "#22 高祖 健輔": "左", "#23 箱山 遥人": "右", "#24 坂巻 尚哉": "右", "#26 西村 彰浩": "左", "#27 小畑 尋規": "右", "#28 宮崎 仁斗": "右", "#29 徳本 健太朗": "左", "#39 柳 元珍": "左", "#99 尾瀬 雄大": "左"}

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    col_map = {'Velocity': '球速', 'Total Spin': '回転数', 'Spin Efficiency': 'スピン効率', 'VB (trajectory)': '縦変化量', 'HB (trajectory)': '横変化量'}
    existing_cols = [c for c in col_map.keys() if c in df.columns]
    for col in existing_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Spin Direction' in df.columns and 'Total Spin' in df.columns:
        st.divider()
        valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
        if not valid_data.empty:
            available_types = sorted(valid_data['Pitch Type'].unique())
            selected_type = st.selectbox("球種を選択:", available_types)
            
            type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
            avg_rpm = type_subset['Total Spin'].mean()
            avg_eff = type_subset['Spin Efficiency'].mean() if 'Spin Efficiency' in df.columns else 100.0
            rep_data = type_subset.iloc[0]
            spin_str = str(rep_data['Spin Direction'])
            
            # 簡易的な利き腕判定（ファイル名やデータから選手を特定できない場合はデフォルト右）
            hand = "右" 
            for name, side in PLAYER_HANDS.items():
                if any(part in str(uploaded_file.name) for part in name.split()):
                    hand = side
                    break

            st.subheader(f"🔄 {selected_type} の回転詳細")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("平均回転数", f"{int(avg_rpm)} rpm")
            col_b.metric("代表的な回転方向", f"{spin_str}")
            col_c.metric("平均回転効率", f"{avg_eff:.1f} %")

            # --- 回転軸の計算（ジャイロ加味） ---
            try:
                hour, minute = map(int, spin_str.split(':'))
                total_min = (hour % 12) * 60 + minute
                direction_deg = (total_min / 720) * 360
                
                # XY平面上の軸（100%効率時の軸）
                axis_deg = direction_deg + 90
                axis_rad = np.deg2rad(axis_deg)
                base_x = np.sin(axis_rad)
                base_y = np.cos(axis_rad)
                
                # 効率による奥行き(Z)の計算
                # 効率 100% -> gyro_angle = 0 (XY面), 0% -> gyro_angle = 90 (YZ面)
                gyro_angle_rad = np.arccos(avg_eff / 100.0)
                
                # 利き腕による奥行き方向の反転（右投手：右側が奥へ）
                if hand == "右":
                    z_factor = -np.sin(gyro_angle_rad) 
                else:
                    z_factor = np.sin(gyro_angle_rad)

                # 最終的な3D回転軸
                # 効率が下がるほど Z成分が大きくなり、X,Y成分が小さくなる
                axis = [float(base_x * (avg_eff/100.0)), float(base_y * (avg_eff/100.0)), float(z_factor)]
                direction_rad = np.deg2rad(direction_deg)
            except:
                axis = [1.0, 0.0, 0.0]; direction_rad = 0

            # 縫い目配置（串刺し定義を維持）
            t_st = np.linspace(0, 2 * np.pi, 200)
            alpha = 0.4
            sx = np.cos(t_st) + alpha * np.cos(3*t_st)
            sy = np.sin(t_st) - alpha * np.sin(3*t_st)
            sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
            pts = np.vstack([sy, -sz, sx]).T 
            norm = np.linalg.norm(pts, axis=1, keepdims=True)
            seam_points = (pts / norm).tolist()

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
                    var dot = p[0]*ax[0] + p[1]*ax[1] + p[2]*ax[2];
                    // 軸の長さを正規化して回転
                    var len = Math.sqrt(ax[0]*ax[0] + ax[1]*ax[1] + ax[2]*ax[2]);
                    var ux = ax[0]/len, uy = ax[1]/len, uz = ax[2]/len;
                    return [
                        p[0]*(c+ux*ux*(1-c)) + p[1]*(ux*uy*(1-c)-uz*s) + p[2]*(ux*uz*(1-c)+uy*s),
                        p[0]*(uy*ux*(1-c)+uz*s) + p[1]*(c+uy*uy*(1-c)) + p[2]*(uy*uz*(1-c)-ux*s),
                        p[0]*(uz*ux*(1-c)-uy*s) + p[1]*(uz*uy*(1-c)+ux*s) + p[2]*(c+uz*uz*(1-c))
                    ];
                }}

                var n = 25; var bx = [], by = [], bz = [];
                for(var i=0; i<=n; i++) {{
                    var v = Math.PI * i / n; bx[i] = []; by[i] = []; bz[i] = [];
                    for(var j=0; j<=n; j++) {{
                        var u = 2 * Math.PI * j / n;
                        bx[i][j] = Math.cos(u) * Math.sin(v); by[i][j] = Math.sin(u) * Math.sin(v); bz[i][j] = Math.cos(v);
                    }}
                }}

                var data = [
                    {{ type: 'surface', x: bx, y: by, z: bz, colorscale: [['0','#FFFFFF'],['1','#FFFFFF']], showscale: false, opacity: 1.0 }},
                    {{ type: 'scatter3d', mode: 'lines', x: [], y: [], z: [], line: {{color: '#BC1010', width: 35}} }},
                    {{ type: 'scatter3d', mode: 'lines',
                      x: [axis[0]*-1.7, axis[0]*1.7], y: [axis[1]*-1.7, axis[1]*1.7], z: [axis[2]*-1.7, axis[2]*1.7],
                      line: {{color: '#000000', width: 15}} }}
                ];

                var layout = {{
                    scene: {{
                        xaxis: {{visible: false, range: [-1.7, 1.7]}}, yaxis: {{visible: false, range: [-1.7, 1.7]}}, zaxis: {{visible: false, range: [-1.7, 1.7]}},
                        aspectmode: 'cube', camera: {{ eye: {{x: 0, y: 0, z: 2.2}}, up: {{x: 0, y: 1, z: 0}} }}, dragmode: false
                    }},
                    margin: {{l:0, r:0, b:0, t:0}}, showlegend: false
                }};

                Plotly.newPlot('chart', data, layout);

                function update() {{
                    angle += (rpm / 60) * (2 * Math.PI) / 1000; 
                    var rx = [], ry = [], rz = [];
                    for(var i=0; i<seam_base.seam.length; i++) {{
                        var p = seam_base.seam[i];
                        // 1. まず現在のスピン方向に縫い目を傾ける
                        var r_init = rotate(p, [0,0,1], {direction_rad}); 
                        // 2. その後、奥行きを含めた回転軸(axis)周りに回転
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
