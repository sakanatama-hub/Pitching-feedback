import streamlit as st
import pandas as pd
import numpy as np
import json

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：超スロー・高精細スピン解析")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    for col in ['Velocity', 'Total Spin']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
    
    if not valid_data.empty:
        row = valid_data.iloc[0]
        spin_str = str(row['Spin Direction'])
        rpm = float(row['Total Spin'])
        p_type = str(row['Pitch Type']) if 'Pitch Type' in row else "Unknown"
        
        # 1. 回転軸の計算
        try:
            hour, minute = map(int, spin_str.split(':'))
            total_min = (hour % 12) * 60 + minute
            theta = (total_min / 720) * 2 * np.pi 
            axis = [float(np.cos(theta)), 0.0, float(-np.sin(theta))]
        except:
            axis = [1.0, 0.0, 0.0]

        # 2. 縫い目の点群生成
        t_st = np.linspace(0, 2 * np.pi, 180)
        alpha = 0.4
        sx = np.cos(t_st) + alpha * np.cos(3*t_st)
        sy = np.sin(t_st) - alpha * np.sin(3*t_st)
        sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        norm = np.sqrt(sx**2 + sy**2 + sz**2)
        
        # 初期姿勢：左に膨らんだU (⊂)
        pts = np.vstack([sz/norm, sx/norm, sy/norm]).T 
        seam_points = pts.tolist()

        # 3. ブラウザ側での描画（JavaScript）
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

            var n = 20; 
            var bx = [], by = [], bz = [];
            for(var i=0; i<=n; i++) {{
                var v = Math.PI * i / n;
                bx[i] = []; by[i] = []; bz[i] = [];
                for(var j=0; j<=n; j++) {{
                    var u = 2 * Math.PI * j / n;
                    bx[i][j] = Math.cos(u) * Math.sin(v);
                    by[i][j] = Math.sin(u) * Math.sin(v);
                    bz[i][j] = Math.cos(v);
                }}
            }}

            var data = [
                {{
                    type: 'surface',
                    x: bx, y: by, z: bz,
                    colorscale: [['0', '#FFFFFF'], ['1', '#FFFFFF']],
                    showscale: false, opacity: 1.0,
                    lighting: {{ambient: 0.8, diffuse: 0.5, specular: 0.05, roughness: 0.9}}
                }},
                {{
                    type: 'scatter3d',
                    mode: 'lines',
                    x: [], y: [], z: [],
                    line: {{color: '#BC1010', width: 30}} // ★さらに太く設定
                }}
            ];

            var layout = {{
                scene: {{
                    xaxis: {{visible: false, range: [-1.1, 1.1]}},
                    yaxis: {{visible: false, range: [-1.1, 1.1]}},
                    zaxis: {{visible: false, range: [-1.1, 1.1]}},
                    aspectmode: 'cube',
                    camera: {{eye: {{x: 0, y: -1.7, z: 0}}}}
                }},
                margin: {{l:0, r:0, b:0, t:0}},
                showlegend: false
            }};

            Plotly.newPlot('chart', data, layout);

            function update() {{
                // ★さらに速度を半分に（分母を240に変更：実データの1/4速度）
                angle += (rpm / 60) * (2 * Math.PI) / 240; 
                
                var rx = [], ry = [], rz = [];
                for(var i=0; i<seam_base.length; i++) {{
                    var p = seam_base[i];
                    var r1 = rotate([p[0]*1.01, p[1]*1.01, p[2]*1.01], axis, angle);
                    var r2 = rotate([p[0]*1.05, p[1]*1.05, p[2]*1.05], axis, angle);
                    
                    rx.push(r1[0], r2[0], null);
                    ry.push(r1[1], r2[1], null);
                    rz.push(r1[2], r2[2], null);
                }}
                
                Plotly.restyle('chart', {{x: [rx], y: [ry], z: [rz]}}, [1]);
                requestAnimationFrame(update);
            }}
            update();
        </script>
        """
        st.components.v1.html(html_code, height=620)

        st.subheader(f"解析対象: {p_type}")
        c1, c2 = st.columns(2)
        c1.metric("Total Spin (Actual)", f"{int(rpm)} RPM")
        c2.metric("Display Speed", "0.25x (Super Slow)")
        
    else:
        st.warning("データが見つかりません。")
else:
    st.info("CSVファイルをアップロードしてください。")
