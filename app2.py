import streamlit as st
import pandas as pd
import numpy as np
import json

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：リアルタイム・スピン解析（完全自動）")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    # CSV読み込み
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # 数値変換の徹底
    for col in ['Velocity', 'Total Spin']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # データが存在するかチェック
    valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
    
    if not valid_data.empty:
        # 最初の1投分を抽出
        row = valid_data.iloc[0]
        spin_str = str(row['Spin Direction'])
        rpm = float(row['Total Spin'])
        p_type = str(row['Pitch Type']) if 'Pitch Type' in row else "Unknown"
        
        # 1. 回転軸の計算 (12:48などの方向に吸い込まれる軸)
        try:
            hour, minute = map(int, spin_str.split(':'))
            total_min = (hour % 12) * 60 + minute
            theta = (total_min / 720) * 2 * np.pi 
            # ターゲット方向に対して垂直な回転軸（奥向き順回転用）
            axis = [float(np.cos(theta)), 0.0, float(-np.sin(theta))]
        except:
            axis = [1.0, 0.0, 0.0] # パース失敗時のデフォルト

        # 2. 縫い目の点群生成 (Pythonで骨格を作成)
        t_st = np.linspace(0, 2 * np.pi, 108)
        alpha = 0.4
        sx = np.cos(t_st) + alpha * np.cos(3*t_st)
        sy = np.sin(t_st) - alpha * np.sin(3*t_st)
        sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        norm = np.sqrt(sx**2 + sy**2 + sz**2)
        
        # 初期姿勢：左に膨らんだU (⊂)
        # 座標軸を入れ替えて初期の向きを調整
        pts = np.vstack([sz/norm, sx/norm, sy/norm]).T 
        seam_points = pts.tolist()

        # 3. ブラウザ側での描画（JavaScript）
        # Playボタンなし、60FPS、無限ループ
        html_code = f"""
        <div id="chart" style="width:100%; height:550px;"></div>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script>
            var seam_base = {json.dumps(seam_points)};
            var axis = {json.dumps(axis)};
            var rpm = {rpm};
            var angle = 0;

            // 回転行列の計算関数
            function rotate(p, ax, a) {{
                var c = Math.cos(a), s = Math.sin(a);
                var dot = p[0]*ax[0] + p[1]*ax[1] + p[2]*ax[2];
                return [
                    p[0]*c + (ax[1]*p[2] - ax[2]*p[1])*s + ax[0]*dot*(1-c),
                    p[1]*c + (ax[2]*p[0] - ax[0]*p[2])*s + ax[1]*dot*(1-c),
                    p[2]*c + (ax[0]*p[1] - ax[1]*p[0])*s + ax[2]*dot*(1-c)
                ];
            }}

            // 球体のメッシュ（白）
            var n = 22;
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
                    colorscale: [['0', 'white'], ['1', 'white']],
                    showscale: false,
                    opacity: 1.0,
                    lighting: {{ambient: 0.8, diffuse: 0.5, specular: 0.1, roughness: 0.5}}
                }},
                {{
                    type: 'scatter3d',
                    mode: 'lines',
                    x: [], y: [], z: [],
                    line: {{color: 'red', width: 10}}
                }}
            ];

            var layout = {{
                scene: {{
                    xaxis: {{visible: false, range: [-1.1, 1.1]}},
                    yaxis: {{visible: false, range: [-1.1, 1.1]}},
                    zaxis: {{visible: false, range: [-1.1, 1.1]}},
                    aspectmode: 'cube',
                    camera: {{eye: {{x: 0, y: -1.8, z: 0}}}}
                }},
                margin: {{l:0, r:0, b:0, t:0}},
                showlegend: false
            }};

            Plotly.newPlot('chart', data, layout);

            function update() {{
                // RPMに基づいた1フレーム(1/60秒)あたりの角度。60FPS計算
                angle += (rpm / 60) * (2 * Math.PI) / 60; 
                
                var rx = [], ry = [], rz = [];
                var off = 0.04; // 縫い目の厚み
                
                for(var i=0; i<seam_base.length; i++) {{
                    var p = seam_base[i];
                    var r1 = rotate(p, axis, angle);
                    
                    // 縫い目の左右の端を生成して「線」として描画
                    var r2 = rotate([p[0]*1.015, p[1]*1.015, p[2]*1.015], axis, angle);
                    
                    rx.push(r1[0], r2[0], null);
                    ry.push(r1[1], r2[1], null);
                    rz.push(r1[2], r2[2], null);
                }}
                
                // 縫い目データ(Scatter3d)のみを高速更新
                Plotly.restyle('chart', {{x: [rx], y: [ry], z: [rz]}}, [1]);
                requestAnimationFrame(update);
            }}

            update();
        </script>
        """
        st.components.v1.html(html_code, height=600)

        # データ表示
        st.subheader(f"解析データ: {p_type}")
        col1, col2 = st.columns(2)
        col1.metric("回転数", f"{int(rpm)} RPM")
        col2.metric("回転軸方向", spin_str)
        
    else:
        st.warning("表示可能なデータが見つかりませんでした。CSVの内容を確認してください。")

else:
    st.info("CSVファイルをアップロードしてください。")
