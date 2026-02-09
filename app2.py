import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：超滑らか・自動回転ビジュアライザー")

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

    def create_ultra_smooth_spin(spin_dir_str, rpm):
        # 1. 回転軸の計算
        hour, minute = map(int, spin_dir_str.split(':'))
        total_min = (hour % 12) * 60 + minute
        theta = (total_min / 720) * 2 * np.pi 
        axis = np.array([np.cos(theta), 0, -np.sin(theta)])

        # 2. 野球ボール構造（U字）
        t = np.linspace(0, 2 * np.pi, 200)
        alpha = 0.4
        sx = np.cos(t) + alpha * np.cos(3*t)
        sy = np.sin(t) - alpha * np.sin(3*t)
        sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
        norm = np.sqrt(sx**2 + sy**2 + sz**2)
        s_base = np.vstack([sx/norm, sy/norm, sz/norm])

        t_st = np.linspace(0, 2 * np.pi, 108)
        ssx = np.cos(t_st) + alpha * np.cos(3*t_st)
        ssy = np.sin(t_st) - alpha * np.sin(3*t_st)
        ssz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        sn = np.sqrt(ssx**2 + ssy**2 + ssz**2)
        st_base = np.vstack([ssx/sn, ssy/sn, ssz/sn])

        R_init = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]])
        st_oriented = R_init @ st_base

        # 3. 滑らかさの調整（60fps相当）
        fps = 60
        num_frames = 60
        # 1周するのに必要な角度ではなく、rpmに基づいた1フレームの進み
        angle_step = (rpm / 60) * (2 * np.pi) / fps

        u, v = np.mgrid[0:2*np.pi:30j, 0:np.pi:30j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)
        ball_mesh = np.vstack([bx.flatten(), by.flatten(), bz.flatten()]).astype(np.float64)

        def rotate_vecs(pts, ax, a):
            ax = ax / (np.linalg.norm(ax) + 1e-9)
            c, s = np.cos(a), np.sin(a)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * (K @ K)
            return R @ pts

        frames = []
        for i in range(num_frames):
            angle = i * angle_step
            r_ball = rotate_vecs(ball_mesh, axis, angle)
            r_st_center = rotate_vecs(st_oriented, axis, angle)
            
            rx, ry, rz = [], [], []
            off = 0.05
            for j in range(108):
                p = r_st_center[:, j]
                side = np.cross(p, axis)
                if np.linalg.norm(side) < 0.01: side = np.array([0, 1, 0])
                side = side / np.linalg.norm(side)
                p_l = p * 1.01 + side * off
                p_r = p * 1.01 - side * off
                rx.extend([float(p_l[0]), float(p_r[0]), None])
                ry.extend([float(p_l[1]), float(p_r[1]), None])
                rz.extend([float(p_l[2]), float(p_r[2]), None])

            frames.append(go.Frame(data=[
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape)),
                go.Scatter3d(x=rx, y=ry, z=rz, mode='lines', line=dict(color='#BC1010', width=12))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=0, y=-1.8, z=0)),
                           dragmode=False), # 勝手に回るのでドラッグ無効化でよりスムーズに
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 1000/fps, "redraw": False}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 {spin_str}方向へ {int(rpm)}rpm で自動回転中",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_ultra_smooth_spin(spin_str, total_spin), use_container_width=True)

    # JavaScriptで強制自動再生（Playボタンを隠してクリック）
    st.components.v1.html(
        """
        <script>
        var checkExist = setInterval(function() {
           var buttons = window.parent.document.querySelectorAll('button');
           buttons.forEach(function(btn) {
               if(btn.innerText === "Play") {
                   btn.click();
                   // btn.style.display = "none"; // ボタンを隠したい場合は有効化
                   clearInterval(checkExist);
               }
           });
        }, 100);
        </script>
        """, height=0
    )
else:
    st.info("CSVファイルをアップロードしてください。")
