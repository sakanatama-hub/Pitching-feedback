import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 究極：リアル・スピン・ビジュアライザー")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    # 数値変換
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 最新データの取得
    valid_data = df.dropna(subset=['Spin Direction', 'Pitch Type'])
    if not valid_data.empty:
        row = valid_data.iloc[0]
        spin_str = row['Spin Direction']
        p_type = row['Pitch Type']
    else:
        st.stop()

    def create_authentic_ball(spin_dir_str):
        # 1. Rapsodo回転軸の計算
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_rad = np.deg2rad((hour % 12 + minute / 60) * 30)
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 縫い目（シーム）の基本形状：深い馬蹄形
        t = np.linspace(0, 2 * np.pi, 108) # 108本の縫い目
        a = 0.62 # 実際のボールに近い深い湾曲
        
        sx = np.cos(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        sy = np.sin(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        sz = a * np.cos(2*t)
        
        # 3. 108本の「独立したV字ステッチ」を作成
        stitch_list = []
        for i in range(len(t)):
            mid = np.array([sx[i], sy[i], sz[i]])
            # 垂直ベクトルと接線ベクトルから横方向を算出
            norm = mid / np.linalg.norm(mid)
            tangent = np.array([-sy[i], sx[i], 0])
            if np.linalg.norm(tangent) < 0.001: tangent = np.array([0, 1, 0])
            side = np.cross(norm, tangent)
            side /= np.linalg.norm(side)
            
            # 本物の縫い目のように、外側から内側へV字に沈む
            p1 = mid * 1.02 + side * 0.05  # 左
            p2 = mid * 0.97               # 底
            p3 = mid * 1.02 - side * 0.05  # 右
            
            stitch_list.append(np.vstack([p1, p2, p3]))

        # 球体メッシュ
        u, v = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)

        def rotate(pts, ax, ang):
            ax = ax / np.linalg.norm(ax)
            c, s = np.cos(ang), np.sin(ang)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        # 4. アニメーション
        frames = []
        for i in range(30):
            angle = (i / 30) * (2 * np.pi)
            
            # 球体の回転
            r_ball = rotate(np.vstack([bx.flatten(), by.flatten(), bz.flatten()]), axis, angle)
            
            # 全ステッチの回転（Noneを含めず一気に計算してエラー回避）
            rotated_stitches_x = []
            rotated_stitches_y = []
            rotated_stitches_z = []
            
            for st_pts in stitch_list:
                r_st = rotate(st_pts.T, axis, angle)
                rotated_stitches_x.extend([r_st[0,0], r_st[0,1], r_st[0,2], None])
                rotated_stitches_y.extend([r_st[1,0], r_st[1,1], r_st[1,2], None])
                rotated_stitches_z.extend([r_st[2,0], r_st[2,1], r_st[2,2], None])
            
            frames.append(go.Frame(data=[
                # 革の本体
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                           colorscale=[[0, '#FDFDFD'], [1, '#EAEAEA']], showscale=False),
                # 108本の独立V字ステッチ
                go.Scatter3d(x=rotated_stitches_x, y=rotated_stitches_y, z=rotated_stitches_z,
                             mode='lines', line=dict(color='#BC1010', width=6))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=1.3, y=-1.3, z=0.5))),
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

    st.plotly_chart(create_authentic_ball(spin_str), use_container_width=True)

    # 自動再生JS
    st.components.v1.html(
        """<script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) { if (b.innerText === 'Play') { b.click(); clearInterval(itv); } });
        }, 100);
        </script>""", height=0
    )

    # 球種別統計
    st.subheader("📊 解析データ概要")
    st.dataframe(df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna().round(1))

else:
    st.info("CSVをアップロードしてください。")
