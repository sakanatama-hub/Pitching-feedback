import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：リアル・スピン・ビジュアライザー")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # --- 最新の1球のデータを取得 ---
    row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_str = row['Spin Direction']
    pitch_type = row['Pitch Type']

    def create_perfect_ball(spin_dir_str):
        # 1. Rapsodoの時計盤から回転軸ベクトルを算出
        # 12:00はバックスピン、3:00は右投手シュート/スライダー
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_deg = (hour % 12 + minute / 60) * 30
        tilt_rad = np.deg2rad(tilt_deg)
        # マグヌス効果の揚力方向に対し、垂直なのが回転軸
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 精密な野球ボールの縫い目（Seam）幾何学
        # 2つの馬蹄形が絡み合う形状を再現
        t = np.linspace(0, 2 * np.pi, 500)
        alpha = 0.45  # 縫い目の「くびれ」の強さ
        beta = 0.25   # 縫い目の「幅」の広がり
        
        # 数式：球面上の8の字型サドル曲線
        x = np.cos(t) * np.sqrt(1 - alpha**2 * np.sin(2*t)**2)
        y = np.sin(t) * np.sqrt(1 - alpha**2 * np.sin(2*t)**2)
        z = alpha * np.sin(2*t)
        
        # 縫い目は2列並んでいるため、微小なオフセットを加えた2本の線を描画
        seam_pts = np.vstack([x, y, z])

        # 3. 球体メッシュ
        u, v = np.mgrid[0:2*np.pi:50j, 0:np.pi:50j]
        bx = np.cos(u) * np.sin(v)
        by = np.sin(u) * np.sin(v)
        bz = np.cos(v)

        def rotate_pts(pts, axis, angle):
            axis = axis / np.linalg.norm(axis)
            c, s = np.cos(angle), np.sin(angle)
            K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        # 4. アニメーションフレーム作成
        frames = []
        n_frames = 30
        for i in range(n_frames):
            angle = (i / n_frames) * (2 * np.pi)
            # 縫い目と球体を回転
            r_seams = rotate_pts(seam_pts, axis, angle)
            # 球体そのものも回転させる（テクスチャの代わりに表面カラーを微変）
            r_ball_pts = rotate_pts(np.vstack([bx.flatten(), by.flatten(), bz.flatten()]), axis, angle)
            
            frames.append(go.Frame(data=[
                # 球体
                go.Surface(x=r_ball_pts[0].reshape(bx.shape), 
                           y=r_ball_pts[1].reshape(by.shape), 
                           z=r_ball_pts[2].reshape(bz.shape),
                           colorscale=[[0, '#FFFFFF'], [1, '#E0E0E0']], showscale=False),
                # 縫い目1
                go.Scatter3d(x=r_seams[0]*1.01, y=r_seams[1]*1.01, z=r_seams[2]*1.01,
                             mode='lines', line=dict(color='#CC0000', width=7)),
                # 縫い目2（少しずらしてリアルな厚みを表現）
                go.Scatter3d(x=r_seams[0]*1.012, y=r_seams[1]*1.012, z=r_seams[2]*1.012,
                             mode='lines', line=dict(color='#AA0000', width=2))
            ], name=f'fr{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(
                    xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
                    aspectmode='cube',
                    camera=dict(eye=dict(x=1.3, y=-1.3, z=1.0))
                ),
                # 自動再生設定
                updatemenus=[{
                    "type": "buttons",
                    "showactive": False,
                    "buttons": [{
                        "label": "Play",
                        "method": "animate",
                        "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "loop": True}]
                    }]
                }],
                title=f"【{pitch_type}】 回転方向: {spin_str} (Rapsodo Physics Model)",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    # 表示
    chart = create_perfect_ball(spin_str)
    st.plotly_chart(chart, use_container_width=True)
    
    # ページロード時に自動でアニメーションを開始させるためのハック
    st.components.v1.html(
        """
        <script>
        window.parent.document.querySelector('button[kind="primary"]').click();
        </script>
        """, height=0
    )

    # 変化量チャート（白背景）
    st.subheader("⚾ 変化量分布")
    import plotly.express as px
    fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                         x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                         template="plotly_white", range_x=[-60, 60], range_y=[-60, 60])
    fig_mov.add_vline(x=0, line_color="gray")
    fig_mov.add_hline(y=0, line_color="gray")
    st.plotly_chart(fig_mov)

else:
    st.info("CSVファイルをアップロードしてください。")
