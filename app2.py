import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Pitching Feedback Pro")

# --- データ読み込み ---
uploaded_file = st.file_uploader("Rapsodo CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    # 数値変換
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # --- 統計とチャート（ご要望通り白背景） ---
    st.subheader("📊 投手パフォーマンス統計")
    stats = df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna().round(1)
    stats.columns = ['平均球速', 'MAX球速', '平均回転', 'MAX回転']
    st.table(stats)

    # --- リアル回転軸ビジュアライザー ---
    st.subheader("🔄 リアル・スピン・シミュレーション")
    
    # 最新データの取得
    row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_str = row['Spin Direction']
    pitch_type = row['Pitch Type']

    def generate_pro_ball(spin_dir):
        # 1. Rapsodo回転軸の計算 (物理的なマグヌス軸)
        hour, minute = map(int, spin_dir.split(':'))
        tilt_deg = (hour % 12 + minute / 60) * 30
        tilt_rad = np.deg2rad(tilt_deg)
        # 進行方向(y軸)に対して垂直な回転軸
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 忠実な「縫い目」の幾何学 (球面上の馬蹄形曲線)
        t = np.linspace(0, 2 * np.pi, 400)
        # 野球ボールのシーム形状を決定する定数
        a, b = 0.4, 0.7 
        # 1列目の縫い目
        x = np.cos(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        y = np.sin(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        z = a * np.cos(2*t)
        
        # 3. 球体と回転の計算
        phi, theta = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        bx = np.cos(phi) * np.sin(theta)
        by = np.sin(phi) * np.sin(theta)
        bz = np.cos(theta)

        def get_rotated_data(angle):
            # ロドリゲスの回転行列
            u = axis / np.linalg.norm(axis)
            c, s = np.cos(angle), np.sin(angle)
            R = np.array([
                [c + u[0]**2*(1-c), u[0]*u[1]*(1-c) - u[2]*s, u[0]*u[2]*(1-c) + u[1]*s],
                [u[1]*u[0]*(1-c) + u[2]*s, c + u[1]**2*(1-c), u[1]*u[2]*(1-c) - u[0]*s],
                [u[2]*u[0]*(1-c) - u[1]*s, u[2]*u[1]*(1-c) + u[0]*s, c + u[2]**2*(1-c)]
            ])
            # 縫い目(並行する2本を描写して厚みを出す)
            seams_pts = np.vstack([x, y, z])
            r_seams = R @ seams_pts
            # 球体表面
            ball_pts = np.vstack([bx.flatten(), by.flatten(), bz.flatten()])
            r_ball = (R @ ball_pts)
            return r_seams, r_ball

        # 4. アニメーションフレーム
        frames = []
        for i in range(24):
            ang = (i / 24) * (2 * np.pi)
            rs, rb = get_rotated_data(ang)
            frames.append(go.Frame(data=[
                # 球体本体（わずかに光沢のある白）
                go.Surface(x=rb[0].reshape(bx.shape), y=rb[1].reshape(by.shape), z=rb[2].reshape(bz.shape),
                           colorscale=[[0, '#FDFDFD'], [1, '#E5E5E5']], showscale=False, opacity=1.0),
                # 縫い目（2本のラインで「幅」を表現）
                go.Scatter3d(x=rs[0]*1.01, y=rs[1]*1.01, z=rs[2]*1.01, mode='lines', 
                             line=dict(color='#B71C1C', width=8), name="Seams Main"),
                go.Scatter3d(x=rs[0]*1.015, y=rs[1]*1.015, z=rs[2]*1.015, mode='lines', 
                             line=dict(color='#D32F2F', width=2), name="Seams Detail")
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(
                    xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                    aspectmode='cube',
                    camera=dict(eye=dict(x=1.3, y=-1.3, z=0.5))
                ),
                updatemenus=[{
                    "type": "buttons", "buttons": [{
                        "label": "🔥 リアル回転開始", "method": "animate", 
                        "args": [None, {"frame": {"duration": 40, "redraw": True}, "fromcurrent": True, "loop": True}]
                    }]
                }],
                title=f"球種: {pitch_type} ({spin_dir}) - Rapsodo物理軸モデル"
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(generate_pro_ball(spin_str), use_container_width=True)
    st.write(f"**【解説】** Rapsodoの{spin_str}の方向に対して垂直な平面でスピンさせています。")

else:
    st.info("GitHubのBatting-feedbackプロジェクト用CSVを読み込んでください。")
