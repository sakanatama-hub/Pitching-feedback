import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：リアル・スピン・ダイナミクス")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    valid_data = df.dropna(subset=['Spin Direction', 'Total Spin'])
    if not valid_data.empty:
        row = valid_data.iloc[0]
        spin_str = row['Spin Direction']
        total_spin = row['Total Spin']
        p_type = row['Pitch Type']
    else:
        st.stop()

    def create_working_spin_model(spin_dir_str, rpm):
        # 1. 回転軸の計算
        hour, minute = map(int, spin_dir_str.split(':'))
        total_min = (hour % 12) * 60 + minute
        theta = (total_min / 720) * 2 * np.pi 
        # 指定方向に垂直な軸（奥向き順回転用）
        axis = np.array([np.cos(theta), 0, -np.sin(theta)])

        # 2. ボールと縫い目の基本形状
        t_st = np.linspace(0, 2 * np.pi, 108)
        alpha = 0.4
        def get_seam_pts(t_arr):
            sx = np.cos(t_arr) + alpha * np.cos(3*t_arr)
            sy = np.sin(t_arr) - alpha * np.sin(3*t_arr)
            sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_arr)
            norm = np.sqrt(sx**2 + sy**2 + sz**2)
            return np.vstack([sx/norm, sy/norm, sz/norm])

        st_base = get_seam_pts(t_st)
        R_init = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]])
        st_oriented = R_init @ st_base

        # 球体メッシュ（軽量化）
        u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:20j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)
        ball_mesh = np.vstack([bx.flatten(), by.flatten(), bz.flatten()])

        # 回転関数
        def rotate_pts(pts, ax, a):
            ax = ax / (np.linalg.norm(ax) + 1e-9)
            c, s = np.cos(a), np.sin(a)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * (K @ K)
            return R @ pts

        # アニメーション設定
        fps = 60
        num_frames = 60
        angle_step = (rpm / 60) * (2 * np.pi) / fps

        frames = []
        for i in range(num_frames):
            angle = i * angle_step
            r_ball = rotate_pts(ball_mesh, axis, angle)
            r_seam = rotate_pts(st_oriented, axis, angle)
            
            # 縫い目の描画データ生成
            rx, ry, rz = [], [], []
            off = 0.04
            for j in range(108):
                p = r_seam[:, j]
                side = np.cross(p, axis)
                if np.linalg.norm(side) < 0.01: side = np.array([0, 1, 0])
                side = (side / np.linalg.norm(side)) * off
                p_l, p_r = p * 1.01 + side, p * 1.01 - side
                rx.extend([p_l[0], p_r[0], None]); ry.extend([p_l[1], p_r[1], None]); rz.extend([p_l[2], p_r[2], None])

            # 各フレームのデータ定義（Surfaceを0番目、Scatter3dを1番目に固定）
            frames.append(go.Frame(
                data=[
                    go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                               colorscale=[[0, 'white'], [1, 'white']], showscale=False, opacity=1.0),
                    go.Scatter3d(x=rx, y=ry, z=rz, mode='lines', line=dict(color='red', width=10))
                ],
                name=f'f{i}'
            ))

        # ベースとなるグラフ（最初のフレーム）
        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(
                    xaxis=dict(visible=False, range=[-1, 1]),
                    yaxis=dict(visible=False, range=[-1, 1]),
                    zaxis=dict(visible=False, range=[-1, 1]),
                    aspectmode='cube',
                    camera=dict(eye=dict(x=0, y=-1.8, z=0))
                ),
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 1000/fps, "redraw": False}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 {spin_str} | {int(rpm)} rpm",
                margin=dict(l=0, r=0, b=0, t=40)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_working_spin_model(spin_str, total_spin), use_container_width=True)

    # 自動再生JS
    st.components.v1.html(
        """
        <script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) { if (b.innerText === 'Play') { b.click(); clearInterval(itv); } });
        }, 200);
        </script>
        """, height=0
    )
else:
    st.info("CSVをアップロードしてください。")
