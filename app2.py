import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：総合データ解析ダッシュボート")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    # 1. データ読み込み
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # 英語名と日本語名のマッピング
    col_map = {
        'Velocity': '球速',
        'Total Spin': '回転数',
        'Spin Efficiency': 'スピン効率',
        'VB (trajectory)': '縦変化量',
        'HB (trajectory)': '横変化量'
    }
    
    existing_cols = [c for c in col_map.keys() if c in df.columns]
    for col in existing_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 2. 統計テーブル
    if 'Pitch Type' in df.columns and len(existing_cols) > 0:
        st.subheader("📊 球種別データサマリー (最大 & 平均)")
        stats_group = df.groupby('Pitch Type')[existing_cols].agg(['max', 'mean'])
        new_columns = []
        for col, stat in stats_group.columns:
            jp_name = col_map.get(col, col)
            stat_name = "最大" if stat == 'max' else "平均"
            new_columns.append(f"{jp_name}({stat_name})")
        stats_df = stats_group.reset_index()
        stats_df.columns = ['球種'] + new_columns
        st.dataframe(stats_df.style.format(precision=1), use_container_width=True)

    # 3. 変化量グラフ (白背景・グリッド強調)
    if 'VB (trajectory)' in df.columns and 'HB (trajectory)' in df.columns:
        st.divider()
        st.subheader("📈 変化量マップ (ムーブメントチャート)")
        
        fig_map = px.scatter(
            df, 
            x='HB (trajectory)', 
            y='VB (trajectory)', 
            color='Pitch Type',
            hover_data=['Velocity', 'Total Spin'],
            labels={'HB (trajectory)': '横変化 (cm)', 'VB (trajectory)': '縦変化 (cm)', 'Pitch Type': '球種'},
        )
        
        # 背景を白に、グリッドをグレーに設定
        fig_map.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                zeroline=True, zerolinewidth=2, zerolinecolor='black', 
                gridcolor='lightgray', range=[-60, 60]
            ),
            yaxis=dict(
                zeroline=True, zerolinewidth=2, zerolinecolor='black', 
                gridcolor='lightgray', range=[-60, 60]
            ),
            width=800,
            height=600
        )
        st.plotly_chart(fig_map, use_container_width=True)

    # 4. スピンビジュアライザー (以前の安定版コード)
    if 'Spin Direction' in df.columns and 'Total Spin' in df.columns:
        st.divider()
        valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
        
        if not valid_data.empty:
            available_types = sorted(valid_data['Pitch Type'].unique()) if 'Pitch Type' in df.columns else []
            selected_type = st.selectbox("確認する球種を選択:", available_types)
            
            type_subset = valid_data[valid_data['Pitch Type'] == selected_type]
            avg_rpm = type_subset['Total Spin'].mean()
            rep_data = type_subset.iloc[0]
            spin_str = str(rep_data['Spin Direction'])
            rpm = float(avg_rpm)

            st.subheader(f"🔄 {selected_type} の回転詳細")
            col_a, col_b = st.columns(2)
            col_a.metric("平均回転数", f"{int(rpm)} rpm")
            col_b.metric("代表的な回転軸", f"{spin_str} 方向")

            # 回転軸計算
            try:
                hour, minute = map(int, spin_str.split(':'))
                total_min = (hour % 12) * 60 + minute
                theta = (total_min / 720) * 2 * np.pi 
                axis = [float(np.cos(theta)), 0.0, float(-np.sin(theta))]
            except:
                axis = [1.0, 0.0, 0.0]

            # 縫い目データ
            t_st = np.linspace(0, 2 * np.pi, 200)
            alpha = 0.4
            sx = np.cos(t_st) + alpha * np.cos(3*t_st)
            sy = np.sin(t_st) - alpha * np.sin(3*t_st)
            sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
            norm = np.sqrt(sx**2 + sy**2 + sz**2)
            pts = np.vstack([sz/norm, sx/norm, sy/norm]).T 
            seam_points = pts.tolist()

            # JSコード (波括弧のエスケープ済)
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
                    angle += (rpm / 60) * (2 * Math.PI) / 1200; 
                    var rx = [], ry = [], rz = [];
                    for(var i=0; i<seam_base.length; i++) {{
                        var p = seam_base[i];
                        var r1 = rotate([p[0]*1.01, p[1]*1.01, p[2]*1.01], axis, angle);
                        var r2 = rotate([p[0]*1.05, p[1]*1.05, p[2]*1.05], axis, angle);
                        rx.push(r1[0], r2[0], null); ry.push(r1[1], r2[1], null); rz.push(r1[2], r2[2], null);
                    }}
                    Plotly.restyle('chart', {{x: [rx], y: [ry], z: [rz]}}, [1]);
                    requestAnimationFrame(update);
                }}
                update();
            </script>
            """
            st.components.v1.html(html_code, height=600)

else:
    st.info("CSVファイルをアップロードしてください。")
