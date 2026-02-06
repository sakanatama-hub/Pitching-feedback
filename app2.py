import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ Rapsodo Pitch Visualizer Pro")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # データ処理（統計用）
    numeric_cols = ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # --- 球種別統計（データがあるもののみ） ---
    st.subheader("📊 球種別統計")
    stats = df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna()
    stats.columns = ['平均球速', '最高球速', '平均回転数', '最高回転数']
    st.dataframe(stats.round(1))

    # --- 変化量チャート（白背景） ---
    st.subheader("⚾ 変化量チャート (Movement Profile)")
    import plotly.express as px
    fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                         x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                         template="plotly_white", range_x=[-60, 60], range_y=[-60, 60])
    fig_mov.add_vline(x=0, line_color="lightgray")
    fig_mov.add_hline(y=0, line_color="lightgray")
    st.plotly_chart(fig_mov)

    # --- 3. リアルな回転アニメーション ---
    st.subheader("🔄 リアル回転シミュレーション (最新の1球)")
    
    # 有効な最新データを取得
    valid_row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_dir_str = valid_row['Spin Direction']
    pitch_type = valid_row['Pitch Type']

    def create_realistic_ball_animation(spin_str):
        # 1. Spin Direction (時刻) を角度に変換
        # 12:00 = 0度, 3:00 = 90度 (投手視点)
        hour, minute = map(int, spin_str.split(':'))
        tilt_deg = (hour % 12 + minute / 60) * 30
        tilt_rad = np.deg2rad(tilt_deg)

        # ラプソードの定義に基づき、揚力方向(tilt_rad)に直交する回転軸を算出
        # 軸ベクトル: [cos, 0, -sin] 
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. ボールのメッシュ (球体)
        phi = np.linspace(0, 2*np.pi, 30)
        theta = np.linspace(0, np.pi, 30)
        x = np.outer(np.cos(phi), np.sin(theta))
        y = np.outer(np.sin(phi), np.sin(theta))
        z = np.outer(np.ones(np.size(phi)), np.cos(theta))

        # 3. 野球の「縫い目」の数式 (8の字曲線)
        t = np.linspace(0, 2*np.pi, 200)
        # 野球ボールの縫い目を近似する球面上の軌跡
        seam_x = 1.01 * (np.cos(t) - 0.2 * np.cos(3*t))
        seam_y = 1.01 * (np.sin(t) + 0.2 * np.sin(3*t))
        seam_z = 1.01 * (0.6 * np.sin(2*t))
        seams = np.vstack([seam_x, seam_y, seam_z])

        # 4. アニメーションフレームの作成
        frames = []
        num_frames = 24
        for i in range(num_frames):
            angle = (i / num_frames) * (2 * np.pi)
            
            # ロドリゲスの回転公式で縫い目と球体を回転させる
            def rotate_points(pts, axis, a):
                # 軸周りの回転行列
                axis = axis / np.linalg.norm(axis)
                c, s = np.cos(a), np.sin(a)
                K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
                R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
                return np.dot(R, pts)

            # 縫い目を回転
            rotated_seams = rotate_points(seams, axis, angle)
            
            # 球体のメッシュを回転
            pts = np.vstack([x.flatten(), y.flatten(), z.flatten()])
            rotated_pts = rotate_points(pts, axis, angle)
            rx = rotated_pts[0].reshape(x.shape)
            ry = rotated_pts[1].reshape(y.shape)
            rz = rotated_pts[2].reshape(z.shape)

            frames.append(go.Frame(data=[
                go.Surface(x=rx, y=ry, z=rz, colorscale=[[0, 'white'], [1, '#fdfdfd']], showscale=False),
                go.Scatter3d(x=rotated_seams[0], y=rotated_seams[1], z=rotated_seams[2], 
                             mode='lines', line=dict(color='red', width=6))
            ], name=f'fr{i}'))

        # 5. 基本表示
        fig = go.Figure(
            data=[
                go.Surface(x=x, y=y, z=z, colorscale=[[0, 'white'], [1, '#fdfdfd']], showscale=False, opacity=0.9),
                go.Scatter3d(x=seams[0], y=seams[1], z=seams[2], mode='lines', line=dict(color='red', width=6))
            ],
            layout=go.Layout(
                scene=dict(
                    xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                    aspectmode='cube',
                    camera=dict(eye=dict(x=1.2, y=-1.2, z=1.2)) # 投手斜め後ろからの視点
                ),
                updatemenus=[{
                    "type": "buttons",
                    "buttons": [{"label": "回転開始", "method": "animate", "args": [None, {"frame": {"duration": 40, "redraw": True}, "fromcurrent": True, "mode": "immediate", "loop": True}]}]
                }]
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_realistic_ball_animation(spin_dir_str))
    st.write(f"**球種**: {pitch_type} | **Spin Direction**: {spin_dir_str}")
    st.info("「回転開始」ボタンを押すと、ラプソードの定義に基づいた回転軸（揚力方向に対して垂直）を中心にリアルな縫い目が回転します。")

else:
    st.info("CSVファイルをアップロードしてください。")
