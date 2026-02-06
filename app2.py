import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ リアル・スピン・ビジュアライザー (Rapsodo準拠)")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # データクレンジング
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 統計・チャート表示
    st.subheader("📊 解析データ概要")
    col1, col2 = st.columns(2)
    with col1:
        stats = df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna().round(1)
        stats.columns = ['平均球速', '最高球速', '平均回転数', '最高回転数']
        st.dataframe(stats)
    with col2:
        import plotly.express as px
        fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                             x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                             template="plotly_white", range_x=[-60, 60], range_y=[-60, 60],
                             title="変化量チャート (cm)")
        fig_mov.update_layout(width=400, height=400)
        st.plotly_chart(fig_mov)

    # --- リアルな野球ボール回転エンジン ---
    st.subheader("🔄 投球回転シミュレーション")
    
    row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_str = row['Spin Direction']
    
    def create_ball_engine(spin_direction):
        # 1. 回転軸の計算 (Rapsodo定義)
        hour, minute = map(int, spin_direction.split(':'))
        tilt_deg = (hour % 12 + minute / 60) * 30
        tilt_rad = np.deg2rad(tilt_deg)
        # スピン軸ベクトル: 進行方向に対して垂直
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. リアルな縫い目の生成 (幾何学的野球ボールモデル)
        t = np.linspace(0, 2 * np.pi, 250)
        # 野球ボールの縫い目の標準的な数式近似
        s = 0.4  # 縫い目の幅調整
        seam_x = np.cos(t) * np.sqrt(1 - s**2 * np.cos(2*t)**2)
        seam_y = np.sin(t) * np.sqrt(1 - s**2 * np.cos(2*t)**2)
        seam_z = s * np.cos(2*t)
        
        # 3. 球体メッシュ
        phi, theta = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        sx = np.cos(phi) * np.sin(theta)
        sy = np.sin(phi) * np.sin(theta)
        sz = np.cos(theta)

        # 4. 回転アニメーションの作成
        frames = []
        steps = 30
        for i in range(steps):
            angle = (i / steps) * (2 * np.pi)
            
            # 回転行列 (Rodrigues' rotation formula)
            def rotate(pts, ax, a):
                ax = ax / np.linalg.norm(ax)
                c, s = np.cos(a), np.sin(a)
                K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
                R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
                return np.dot(R, pts)

            # 縫い目の回転
            r_seams = rotate(np.vstack([seam_x, seam_y, seam_z]), axis, angle)
            # 球体の回転 (表面の質感を出すための回転)
            r_ball = rotate(np.vstack([sx.flatten(), sy.flatten(), sz.flatten()]), axis, angle)
            
            frames.append(go.Frame(data=[
                # 球体本体 (真っ白ではなく少し質感を出す)
                go.Surface(x=r_ball[0].reshape(sx.shape), 
                           y=r_ball[1].reshape(sy.shape), 
                           z=r_ball[2].reshape(sz.shape),
                           colorscale=[[0, '#F0F0F0'], [1, '#FFFFFF']], showscale=False),
                # 縫い目 (赤)
                go.Scatter3d(x=r_seams[0], y=r_seams[1], z=r_seams[2],
                             mode='lines', line=dict(color='#D32F2F', width=8))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(
                    xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                    aspectmode='cube',
                    camera=dict(eye=dict(x=1.2, y=-1.5, z=0.8)) # 捕手方向やや斜めからの視点
                ),
                updatemenus=[{
                    "type": "buttons", "buttons": [{
                        "label": "回転を再生", "method": "animate", 
                        "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "loop": True}]
                    }]
                }],
                margin=dict(l=0, r=0, b=0, t=30),
                title=f"球種: {row['Pitch Type']} | Spin Direction: {spin_str}"
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_ball_engine(spin_str), use_container_width=True)
    st.write("※黒い背景に白いボールが浮かび、赤い縫い目が回転軸に従って動きます。")

else:
    st.info("CSVファイルをアップロードしてください。")
