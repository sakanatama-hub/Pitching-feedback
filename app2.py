import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：スピン軸・初期姿勢完全再現")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    valid_data = df.dropna(subset=['Spin Direction', 'Pitch Type'])
    if not valid_data.empty:
        row = valid_data.iloc[0]
        spin_str = row['Spin Direction']
        p_type = row['Pitch Type']
    else:
        st.stop()

    def create_precise_spinning_ball(spin_dir_str):
        # 1. 回転軸の計算 (Rapsodoの時計の針の方向に垂直な軸)
        hour, minute = map(int, spin_dir_str.split(':'))
        total_min = (hour % 12) * 60 + minute
        theta = (total_min / 720) * 2 * np.pi
        
        # 軸：12:00のときX軸(水平)、3:00のときY軸(垂直)
        axis = np.array([np.cos(theta), -np.sin(theta), 0])

        # 2. 野球ボール曲線の生成 (U字構造)
        t = np.linspace(0, 2 * np.pi, 200)
        alpha = 0.4
        sx = np.cos(t) + alpha * np.cos(3*t)
        sy = np.sin(t) - alpha * np.sin(3*t)
        sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
        norm = np.sqrt(sx**2 + sy**2 + sz**2)
        s_base = np.vstack([sx/norm, sy/norm, sz/norm])

        # 108本のステッチ
        t_st = np.linspace(0, 2 * np.pi, 108)
        ssx = np.cos(t_st) + alpha * np.cos(3*t_st)
        ssy = np.sin(t_st) - alpha * np.sin(3*t_st)
        ssz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        sn = np.sqrt(ssx**2 + ssy**2 + ssz**2)
        st_base = np.vstack([ssx/sn, ssy/sn, ssz/sn])

        # 3. 各時刻ごとの「初期姿勢」と「回転の向き」の定義
        # ここで「12:00は左に膨らんだ⊂」など、指示通りの向きに固定
        def get_pose_and_spin(ang):
            # 12:00基準：U字が左に膨らむように基本姿勢を回転
            # Y軸周りに90度、Z軸周りに90度などの調整
            R_fix = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]])
            # 時刻に合わせてボール自体の向きも連動させる
            c, s = np.cos(ang), np.sin(ang)
            Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            return Rz @ R_fix

        R_init = get_pose_and_spin(theta)
        s_oriented = R_init @ s_base
        st_oriented = R_init @ st_base

        # 4. 回転アニメーションの計算
        u, v = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)
        ball_base = np.vstack([bx.flatten(), by.flatten(), bz.flatten()])

        def rotate_matrix(pts, ax, a):
            ax = ax / np.linalg.norm(ax)
            c, s = np.cos(a), np.sin(a)
            # 12:00で「手前に回転」させるために回転角の符号を調整
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * (K @ K)
            return R @ pts

        frames = []
        for i in range(30):
            # 回転の進み（バックスピンならプラス方向）
            angle = (i / 30) * (2 * np.pi)
            r_ball = rotate_matrix(ball_base, axis, angle)
            r_st_center = rotate_matrix(st_oriented, axis, angle)
            
            # ステッチの描画
            off = 0.05
            rx, ry, rz = [], [], []
            for j in range(108):
                p = r_st_center[:, j]
                # 側面の平行線を出すためのサイドベクトル（軸方向に依存）
                side = np.array([-p[1], p[0], 0.1]) 
                side /= np.linalg.norm(side)
                p_l, p_r = p * 1.01 + side * off, p * 1.01 - side * off
                rx.extend([p_l[0], p_r[0], None])
                ry.extend([p_l[1], p_r[1], None])
                rz.extend([p_l[2], p_r[2], None])

            frames.append(go.Frame(data=[
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                           colorscale=[[0, '#FFFFFF'], [1, '#EAEAEA']], showscale=False),
                go.Scatter3d(x=rx, y=ry, z=rz, mode='lines', line=dict(color='#BC1010', width=12))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=0, y=-1.8, z=0))),
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 {spin_str}方向のスピン再現",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_precise_spinning_ball(spin_str), use_container_width=True)

    # 自動再生
    st.components.v1.html(
        """<script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) { if (b.innerText === 'Play') { b.click(); clearInterval(itv); } });
        }, 100);
        </script>""", height=0
    )

else:
    st.info("CSVファイルをアップロードしてください。")
