import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：XY平面固定・スピン解析")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    col_map = {'Velocity': '球速', 'Total Spin': '回転数', 'Spin Efficiency': 'スピン効率', 'VB (trajectory)': '縦変化量', 'HB (trajectory)': '横変化量'}
    existing_cols = [c for c in col_map.keys() if c in df.columns]
    for col in existing_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Spin Direction' in df.columns and 'Total Spin' in df.columns:
        valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
        
        if not valid_data.empty:
            available_types = sorted(valid_data['Pitch Type'].unique())
            selected_type = st.selectbox("確認する球種を選択:", available_types)
            
            type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
            avg_rpm = type_subset['Total Spin'].mean()
            rep_data = type_subset.iloc[0]
            spin_str = str(rep_data['Spin Direction'])
            rpm = float(avg_rpm)

            # --- 回転軸の計算（XY平面上に固定） ---
            try:
                hour, minute = map(int, spin_str.split(':'))
                total_min = (hour % 12) * 60 + minute
                # Rapsodo定義: 12:00が真上(Y軸+)。時計回りに角度が増える。
                # 角度をラジアンに変換
                angle_deg = (total_min / 720) * 360
                angle_rad_axis = np.deg2rad(angle_deg)
                
                # XY平面上の軸ベクトル (Zは0に固定)
                # 12:00 -> [0, 1, 0], 3:00 -> [1, 0, 0], 6:00 -> [0, -1, 0]
                axis = [float(np.sin(angle_rad_axis)), float(np.cos(angle_rad_axis)), 0.0]
            except:
                axis = [0.0, 1.0, 0.0]
                angle_rad_axis = 0

            # --- 縫い目の初期配置（バックスピン定義） ---
            t_st = np.linspace(0, 2 * np.pi, 200)
            alpha = 0.4
            sx = np.cos(t_st) + alpha * np.cos(3*t_st)
            sy = np.sin(t_st) - alpha * np.sin(3*t_st)
            sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
            
            # 初期状態で12:00バックスピン（右向きU字）になる配置
            pts = np.vstack([sz, -sx, sy]).T 
            norm = np.linalg.norm(pts, axis=1, keepdims=True)
            pts = pts / norm
            seam_points = pts.tolist()

            html_code = f"""
            <div id="chart" style="width:100%; height:600px;"></div>
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

                var n = 25; var bx = [], by = [], bz = [];
                for(var i=0; i<=n; i++) {{
                    var v = Math.PI * i / n; bx[i] = []; by[i] = []; bz[i] = [];
                    for(var j=0; j<=n; j++) {{
                        var u = 2 * Math.PI * j / n;
                        bx[i][j] = Math.cos(u) * Math.sin(v); 
                        by[i][j] = Math.sin(u) * Math.sin(v); 
                        bz[i][j] = Math.cos(v);
                    }}
                }}

                // XY平面（Z=0）に配置される回転軸（黒い棒）
                var axis_line = {{
                    type: 'scatter3d', mode: 'lines',
                    x: [axis[0] * -1.7, axis[0] * 1.7],
                    y: [axis[1] * -1.7, axis[1] * 1.7],
                    z: [0, 0],
                    line: {{color: '#000000', width: 15}}
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
                        line: {{color: '#BC1010', width: 35}}
                    }},
                    axis_line
                ];

                var layout = {{
                    scene: {{
                        xaxis: {{visible: false, range: [-1.7, 1.7]}},
                        yaxis: {{visible: false, range: [-1.7, 1.7]}},
                        zaxis: {{visible: false, range: [-1.7, 1.7]}},
                        aspectmode: 'cube',
                        camera: {{
                            eye: {{x: 0, y: 0, z: 2.0}}, // Z軸の正面（画面手前）から見る
                            up: {{x: 0, y: 1, z: 0}}     // Y軸を上にする
                        }},
                        dragmode: false // 視点がズレないように固定
                    }},
                    margin: {{l:0, r:0, b:0, t:0}},
                    showlegend: false
                }};

                Plotly.newPlot('chart', data, layout);

                function update() {{
                    angle += (rpm / 60) * (2 * Math.PI) / 1000; 
                    var rx = [], ry = [], rz = [];
                    for(var i=0; i<seam_base.length; i++) {{
                        var p = seam_base[i];
                        // 1. 軸の傾きに合わせて縫い目を配置
                        var r_init = rotate(p, [0,0,1], {angle_rad_axis}); 
                        // 2. その軸(axis)周りに回転
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
