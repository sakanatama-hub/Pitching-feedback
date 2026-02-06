import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：リアル・スピン・ビジュアライザー")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    # 欠損値処理
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 最新の1球のデータ
    row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_str = row['Spin Direction']
    p_type = row['Pitch Type']

    def create_professional_baseball(spin_dir_str):
        # 1. Rapsodoの回転軸算出
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_deg = (hour % 12 + minute / 60) * 30
        tilt_rad = np.deg2rad(tilt_deg)
        # スピン軸ベクトル（揚力方向に直交）
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 本物の野球ボールの「シーム（縫い目）」構造を再現
        # 2枚のひょうたん型パネルの境界線をパラメータ化 (球面鞍点曲線)
        t = np.linspace(0, 2 * np.pi, 500)
        # 本物の野球ボールの比率に近いパラメータ
        alpha = 0.42 # パネルのくびれ
        beta = 0.28  # パネルの幅
        
        # パネルの境界線（中心線）
        x = np.cos(t) * np.sqrt(1 - alpha**2 * np.cos(2*t)**2)
        y = np.sin(t) * np.sqrt(1 - alpha**2 * np.cos(2*t)**2)
        z = alpha * np.cos(2*t)
        
        # 縫い目は2列並んでいるので左右にオフセット
        # 球面上で少しだけズラして「二本線」を表現
        seam_pts = np.vstack([x, y, z])

        # 3. 球体と回転の行列演算
        u, v = np.mgrid[0:2*np.pi:60j, 0:np.pi:60j]
        bx = np.cos(u) * np.sin(v)
        by = np.sin(u) * np.sin(v)
        bz = np.cos(v)

        def rotate_pts(pts, axis, angle):
            u = axis / np.linalg.norm(axis)
            c, s = np.cos(angle), np.sin(angle)
            K = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        # 4. フレーム作成
        frames = []
        n_fr = 40
        for i in range(n_fr):
            ang = (i / n_fr) * (2 * np.pi)
            r_seams = rotate_pts(seam_pts, axis, ang)
            r_ball = rotate_pts(np.vstack([bx.flatten(), by.flatten(), bz.flatten()]), axis, ang)
            
            # ボールのテクスチャ（実際の野球ボールの質感に近い色合いをマッピング）
            frames.append(go.Frame(data=[
                # 球体表面（皮の質感）
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                           colorscale=[[0, '#FDFDFD'], [0.5, '#F5F5F0'], [1, '#E8E8E0']], 
                           showscale=False, opacity=1.0),
                # 縫い目（立体的な赤色）
                go.Scatter3d(x=r_seams[0]*1.01, y=r_seams[1]*1.01, z=r_seams[2]*1.01,
                             mode='lines', line=dict(color='#8B0000', width=8)),
                # 縫い目の微細なディテール（ステッチの影）
                go.Scatter3d(x=r_seams[0]*1.015, y=r_seams[1]*1.015, z=r_seams[2]*1.015,
                             mode='lines', line=dict(color='#CC0000', width=2))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(
                    xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                    aspectmode='cube',
                    camera=dict(eye=dict(x=1.3, y=-1.3, z=0.5))
                ),
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 25, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 Spin Direction: {spin_str}",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    # --- 表示 ---
    st.plotly_chart(create_professional_baseball(spin_str), use_container_width=True)

    # JavaScriptで自動再生（リロード不要で開始）
    st.components.v1.html(
        """<script>
        var checkExist = setInterval(function() {
           var buttons = window.parent.document.querySelectorAll('button');
           for (var i=0; i<buttons.length; i++) {
               if (buttons[i].innerText === 'Play') {
                   buttons[i].click();
                   clearInterval(checkExist);
               }
           }
        }, 100);
        </script>""", height=0
    )

    # 変化量チャート（白背景）
    import plotly.express as px
    st.subheader("⚾ 変化量分布")
    fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                         x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                         template="plotly_white", range_x=[-60, 60], range_y=[-60, 60])
    fig_mov.add_hline(y=0, line_color="gray")
    fig_mov.add_vline(x=0, line_color="gray")
    st.plotly_chart(fig_mov)
