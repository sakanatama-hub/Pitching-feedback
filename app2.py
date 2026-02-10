import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：縫い目・回転方向 完全定義版")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    
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

    if 'Spin Direction' in df.columns and 'Total Spin' in df.columns:
        st.divider()
        valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
        
        if not valid_data.empty:
            available_types = sorted(valid_data['Pitch Type'].unique())
            selected_type = st.selectbox("確認する球種を選択:", available_types)
            
            type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
            avg_rpm = type_subset['Total Spin'].mean()
            rep_data = type_subset.iloc[0]
            spin_str = str(rep_data['Spin Direction'])
            rpm = float(avg_rpm)

            st.subheader(f"🔄 {selected_type} の回転詳細")
            col_a, col_b = st.columns(2)
            col_a.metric("平均回転数", f"{int(rpm)} rpm")
            col_b.metric("代表的な回転方向", f"{spin_str}")

            # --- 回転軸の計算（定義通り） ---
            try:
                hour, minute = map(int, spin_str.split(':'))
                total_min = (hour % 12) * 60 + minute
                # 角度（12:00 = 0度）
                angle_deg = (total_min / 720) * 360
                angle_rad = np.deg2rad(angle_deg)
                # 軸ベクトル：常に画面に並行な面(XY面)での軸
                axis = [float(np.sin(angle_rad)), float(np.cos(angle_rad)), 0.0]
            except:
                axis = [0.0, 1.0, 0.0]
                angle_rad = 0

            # --- 縫い目データの初期配置調整 ---
            # 12:00の時に「右に倒れたU字」にするための初期回転
            t_st = np.linspace(0, 2 * np.pi, 200)
            alpha = 0.4
            sx = np.cos(t_st) + alpha * np.cos(3*t_st)
            sy = np.sin(t_st) - alpha * np.sin(3*t_st)
            sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
            
            # 基本の縫い目を90度回転させて「右に倒れたU字」をデフォルトにする
            # 12:00の状態（軸が垂直）で、2本の並行線が地面と水平
            pts = np.vstack([sz, sx, -sy]).T 
            norm = np.linalg.norm(pts, axis=1, keepdims=True)
            pts = pts / norm
            seam_points = pts.tolist()

            html_code = f"""
            <div id="chart" style="width:100%; height:550px;"></div>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var seam_base = {json.dumps(seam_points)};
                var axis = {json.dumps(axis)};
                var rpm = {rpm};
                var angle = 0;

                function rotate(p, ax, a) {{
                    var c = Math.cos(a), s = Math.sin(a);
                    var dot = p[0]*ax[0] + p[1]*ax[1] + p[2]*ax[2];
                    return [
                        p[0]*c + (ax[1]*p[2] - ax[2]*p[1])*s + ax[0]*dot*(1-c),
                        p[1]*c + (ax[2]*p[0] - ax[0]*p[2])*s + ax[1]*dot*(1-c),
                        p[2]*c + (ax[0]*p[1] - ax[1]*p[0])*s + ax[2]*dot*(1-c)
                    ];
                }}

                var n = 22; var bx = [], by = [], bz = [];
                for(var i=0; i<=n; i++) {{
                    var v = Math.PI * i / n; bx[i] = []; by[i] = []; bz[i] = [];
                    for(var j=0; j<=n; j++) {{
                        var u = 2 * Math.PI * j / n;
                        bx[i][j] = Math.cos(u) * Math.sin(v); by[i][j] = Math.sin(u) * Math.sin(v); bz[i][j] = Math.cos(v);
                    }}
                }}

                var axis_line = {{
                    type: 'scatter3d', mode: 'lines',
                    x: [axis[0] * -1.6, axis[0] * 1.6],
                    y: [axis[1] * -1.6, axis[1] * 1.6],
                    z: [axis[2] * -1.6, axis[2] * 1.6],
                    line: {{color: '#000000', width: 12}}
                }};

                var data = [
                    {{
                        type: 'surface', x: bx, y: by, z: bz,
                        colorscale: [['0', '#FFFFFF'], ['1', '#FFFFFF']],
                        showscale: false, opacity: 1.0,
                        lighting: {{ambient: 0.8, diffuse: 0.5, specular: 0.1, roughness: 1.0}}
                    }},
                    {{
                        type: 'scatter3d', mode: 'lines', x: [], y: [], z: [],
                        line: {{color: '#BC1010', width: 30}}
                    }},
                    axis_line
                ];

                var layout = {{
                    scene: {{
                        xaxis: {{visible: false, range: [-1.6, 1.6]}},
                        yaxis: {{visible: false, range: [-1.6, 1.6]}},
                        zaxis: {{visible: false, range: [-1.6, 1.6]}},
                        aspectmode: 'cube',
                        camera: {{eye: {{x: 0, y: -1.8, z: 0}}}} 
                    }},
                    margin: {{l:0, r:0, b:0, t:0}},
                    showlegend: false
                }};

                Plotly.newPlot('chart', data, layout);

                function update() {{
                    // 手前から奥（下方向）への回転を実現するために角度をマイナス方向に
                    angle -= (rpm / 60) * (2 * Math.PI) / 1000; 
                    var rx = [], ry = [], rz = [];
                    for(var i=0; i<seam_base.length; i++) {{
                        var p = seam_base[i];
                        // 1. 縫い目自体を回転軸の方向に合わせて傾ける
                        // 2. その後、軸周りに回転させる
                        var r_init = rotate(p, [0,0,1], {angle_rad}); // 軸の傾き分だけ先に縫い目を傾ける
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
