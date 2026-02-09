import streamlit as st
import pandas as pd
import numpy as np
import json

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：統計データ解析 & スピンビジュアライザー")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    # 1. データ読み込みと前処理
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # 解析対象の列を数値型に変換
    target_cols = ['Velocity', 'Total Spin', 'Spin Efficiency', 'VB (trajectory)', 'HB (trajectory)']
    for col in target_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 2. 球種ごとの統計テーブル作成
    if 'Pitch Type' in df.columns:
        st.subheader("📊 球種別データサマリー (MAX & 平均)")
        
        # 集計処理
        stats_df = df.groupby('Pitch Type')[target_cols].agg(['max', 'mean']).reset_index()
        
        # カラム名を分かりやすく整形
        stats_df.columns = [
            '球種', 
            '球速(MAX)', '球速(平均)', 
            '回転数(MAX)', '回転数(平均)', 
            '効率%(MAX)', '効率%(平均)', 
            '縦変化(MAX)', '縦変化(平均)', 
            '横変化(MAX)', '横変化(平均)'
        ]
        
        # 小数点第1位で丸める
        st.dataframe(stats_df.style.format(precision=1), use_container_width=True)
    
    # 3. スピンビジュアライザー（選択した球種の平均値を表示）
    valid_data = df.dropna(subset=['Spin Direction', 'Total Spin', 'Pitch Type'])
    
    if not valid_data.empty:
        st.divider()
        st.subheader("🔄 スピン・シミュレーション")
        
        # 表示する球種を選択（デフォルトは最初の行）
        available_types = valid_data['Pitch Type'].unique()
        selected_type = st.selectbox("確認する球種を選択:", available_types)
        
        # 選択された球種の平均データを抽出
        type_data = valid_data[valid_data['Pitch Type'] == selected_type].iloc[0]
        spin_str = str(type_data['Spin Direction'])
        rpm = float(type_data['Total Spin'])

        # --- 以下、JavaScriptスピン描画ロジック ---
        try:
            hour, minute = map(int, spin_str.split(':'))
            total_min = (hour % 12) * 60 + minute
            theta = (total_min / 720) * 2 * np.pi 
            axis = [float(np.cos(theta)), 0.0, float(-np.sin(theta))]
        except:
            axis = [1.0, 0.0, 0.0]

        t_st = np.linspace(0, 2 * np.pi, 200)
        alpha = 0.4
        sx = np.cos(t_st) + alpha * np.cos(3*t_st)
        sy = np.sin(t_st) - alpha * np.sin(3*t_st)
        sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        norm = np.sqrt(sx**2 + sy**2 + sz**2)
        pts = np.vstack([sz/norm, sx/norm, sy/norm]).T 
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
                    type: 'surface', x: bx, y: by, z: bz,
                    colorscale: [['0', '#FFFFFF'], ['1', '#FFFFFF']],
                    showscale: false, opacity: 1.0,
                    lighting: {{ambient: 0.85, diffuse: 0.45, specular: 0.05, roughness: 1.0}}
                }},
                {{
                    type: 'scatter3d', mode: 'lines', x: [], y: [], z: [],
                    line: {{color: '#BC1010', width: 35}}
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
                angle += (rpm / 60) * (2 * Math.PI) / 1200; // 0.05倍速を維持
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
        st.components.v1.html(html_code, height=550)
        
    else:
        st.warning("解析可能な球種データが見つかりませんでした。")

else:
    st.info("CSVファイルをアップロードしてください。")
