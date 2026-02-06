import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 完璧再現：Rapsodoスピン・ダイナミクス")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

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

    def create_perfect_physics_ball(spin_dir_str):
        # 1. 回転軸と位相の計算
        hour, minute = map(int, spin_dir_str.split(':'))
        total_minutes = (hour % 12) * 60 + minute
        theta = (total_minutes / 720) * 2 * np.pi  # 0(12:00) -> 2pi
        
        # 自転軸（常に進行方向に垂直な面内）
        # 12:00(0) -> [1, 0, 0] 3:00(pi/2) -> [0, 1, 0]... 
        axis = np.array([np.cos(theta), -np.sin(theta), 0])

        # 2. 野球ボール曲線の生成
        t = np.linspace(0, 2 * np.pi, 200)
        alpha = 0.4
        
        # 基本となる構造線
        sx_raw = np.cos(t) + alpha * np.cos(3*t)
        sy_raw = np.sin(t) - alpha * np.sin(3*t)
        sz_raw = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
        
        # 正規化
        norm = np.sqrt(sx_raw**2 + sy_raw**2 + sz_raw**2)
        s_base = np.vstack([sx_raw/norm, sy_raw/norm, sz_raw/norm])

        # 3. 時刻に応じた「初期のボールの向き」を定義
        # ここで「12:00は左膨らみ」「3:00は逆U字」などの初期姿勢を制御
        def get_initial_rotation(ang):
            # 12:00基準の姿勢をベースに、時刻分だけボール自体を傾ける
            c, s = np.cos(ang), np.sin(ang)
            # Z軸周りの回転で時刻に合わせる
            Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            # 12:00の初期姿勢を左膨らみに調整するための固定回転
            R_fix = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]])
            return Rz @ R_fix

        R_init = get_initial_rotation(theta)
        s_oriented = R_init @ s_base

        # 108本のステッチも同様に配置
        t_st = np.linspace(0, 2 * np.pi, 108)
        ssx = (np.cos(t_st) + alpha * np.cos(3*t_st))
        ssy = (np.sin(t_st) - alpha * np.sin(3*t_st))
        ssz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        sn = np.sqrt(ssx**2 + ssy**2 + ssz**2)
        st_base = np.vstack([ssx/sn, ssy/sn, ssz/sn])
        st_oriented = R_init @ st_base

        # 4. アニメーション計算
        u, v = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)
        ball_base = np.vstack([bx.flatten(), by.flatten(), bz.flatten()])

        def rotate_pts(pts, ax, a):
            ax = ax / np.linalg.norm(ax)
            c, s = np.cos(a), np.sin(a)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        frames = []
        for i in range(30):
            # 12:00の時は手前に回るように符号を調整
            rot_angle = (i / 30) * (2 * np.pi)
            r_ball = rotate_pts(ball_base, axis, rot_angle)
            
            # ステッチのジグザグ描画
            off = 0.05
            rx, ry, rz = [], [], []
            r_st_center = rotate_pts(st_oriented, axis, rot_angle)
            
            for j in range(108):
                p = r_st_center[:, j]
                n = p / np.linalg.norm(p)
                # 側面の平行線を出すためのサイドベクトル
                side = np.array([-p[1], p[0], 0])
                if np.linalg.norm(side) < 0.1: side = np.array([0, 1, 0])
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
                           camera=dict(eye=dict(x=0, y=-1.8, z=0))), # 投手後方視点
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 Spin Direction: {spin_str}",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_perfect_physics_ball(spin_str), use_container_width=True)

    # 自動再生JS
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
