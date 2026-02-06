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

    # 最新データの取得
    valid_data = df.dropna(subset=['Spin Direction', 'Pitch Type'])
    if not valid_data.empty:
        row = valid_data.iloc[0]
        spin_str = row['Spin Direction']
        p_type = row['Pitch Type']
    else:
        st.error("有効なデータが見つかりません。")
        st.stop()

    def create_authentic_baseball_model(spin_dir_str):
        # 1. Rapsodo回転軸の計算 (物理軸)
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_rad = np.deg2rad((hour % 12 + minute / 60) * 30)
        # スピン軸ベクトル（揚力方向に垂直）
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 本物の野球ボールの「縫い目（シーム）」構造の数学的再現
        # 2枚のひょうたん型の皮を繋ぎ合わせる「108本のステッチ」を作成
        t = np.linspace(0, 2 * np.pi, 108) # 108本の縫い目
        
        # 本物のシームに近い鞍点曲線のパラメータ
        a = 0.6  # 湾曲の深さ
        b = 0.4  # 絞り
        
        # シームの基本軌道
        sx = np.cos(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        sy = np.sin(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        sz = a * np.cos(2*t)
        
        # 縫い目はジグザグなので、外側と内側のポイントを生成
        off = 0.05
        p1 = np.vstack([sx*(1+off), sy*(1+off), sz*(1+off)])
        p2 = np.vstack([sx*(1-off), sy*(1-off), sz*(1-off)])
        
        # ジグザグに連結
        stitches = []
        for i in range(len(t)):
            stitches.append(p1[:, i])
            stitches.append(p2[:, (i+1)%len(t)])
        stitches = np.array(stitches).T

        # 3. 球体メッシュ (革の質感を出すための細かさ)
        u, v = np.mgrid[0:2*np.pi:60j, 0:np.pi:60j]
        x_sph = np.cos(u) * np.sin(v)
        y_sph = np.sin(u) * np.sin(v)
        z_sph = np.cos(v)

        def rotate_vec(pts, axis, angle):
            u_ax = axis / np.linalg.norm(axis)
            c, s = np.cos(angle), np.sin(angle)
            K = np.array([[0, -u_ax[2], u_ax[1]], [u_ax[2], 0, -u_ax[0]], [-u_ax[1], u_ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        # 4. アニメーション作成
        frames = []
        n_frames = 30
        for i in range(n_frames):
            angle = (i / n_frames) * (2 * np.pi)
            r_ball = rotate_vec(np.vstack([x_sph.flatten(), y_sph.flatten(), z_sph.flatten()]), axis, angle)
            r_st = rotate_vec(stitches, axis, angle)
            
            frames.append(go.Frame(data=[
                # 球体 (革の質感: オフホワイト)
                go.Surface(x=r_ball[0].reshape(x_sph.shape), y=r_ball[1].reshape(y_sph.shape), z=r_ball[2].reshape(z_sph.shape),
                           colorscale=[[0, '#FDFDFD'], [1, '#EFEFEA']], showscale=False,
                           lighting=dict(ambient=0.6, diffuse=0.8, specular=0.2, roughness=0.9)),
                # 108本のステッチ (太い赤糸)
                go.Scatter3d(x=r_st[0], y=r_st[1], z=r_st[2], mode='lines',
                             line=dict(color='#B22222', width=10))
            ], name=f'fr{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=1.2, y=-1.5, z=0.6))),
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

    # ボール表示
    st.plotly_chart(create_authentic_baseball_model(spin_str), use_container_width=True)

    # 自動再生JS
    st.components.v1.html(
        """<script>
        var check = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            for (var i=0; i<btns.length; i++) {
                if (btns[i].innerText === 'Play') { btns[i].click(); clearInterval(check); }
            }
        }, 100);
        </script>""", height=0
    )

    # 変化量チャート（白背景）
    import plotly.express as px
    st.subheader("⚾ 変化量分布 (Movement)")
    fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                         x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                         template="plotly_white", range_x=[-60, 60], range_y=[-60, 60])
    fig_mov.add_hline(y=0, line_color="black")
    fig_mov.add_vline(x=0, line_color="black")
    st.plotly_chart(fig_mov)

else:
    st.info("CSVファイルをアップロードしてください。")
