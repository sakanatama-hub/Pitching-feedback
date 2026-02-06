import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# データの読み込み
# ユーザーから提供されたファイルを想定 (ヘッダーが5行目からなので skiprows=4)
df = pd.read_csv('1087119_pitching_a59b8a732597ec99670f.csv', skiprows=4)

# 1. 基本統計量の算出
stats = df.groupby('Pitch Type').agg({
    'Velocity': ['mean', 'max'],
    'Total Spin': ['mean', 'max']
}).reset_index()

# 2. 変化量 (VB vs HB) のグラフ
def plot_movement(df):
    fig = px.scatter(df, x='HB (trajectory)', y='VB (trajectory)', 
                     color='Pitch Type', title='変化量チャート (Movement Profile)',
                     labels={'HB (trajectory)': 'Horizontal Break (cm)', 'VB (trajectory)': 'Vertical Break (cm)'})
    fig.add_hline(y=0)
    fig.add_vline(x=0)
    return fig

# 3. 回転軸（Spin Direction）の3D視覚化
# "12:52" のような文字列を角度に変換してボールの回転軸を表示
def plot_ball_spin(pitch_type, spin_direction_str):
    # 時刻形式を角度に変換 (例: 12:00 -> 0度, 3:00 -> 90度)
    try:
        hour, minute = map(int, spin_direction_str.split(':'))
        angle_deg = (hour % 12 + minute / 60) * 30
        angle_rad = np.deg2rad(angle_deg)
    except:
        angle_rad = 0

    # ボールの球体を作成
    u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
    x = np.cos(u)*np.sin(v)
    y = np.sin(u)*np.sin(v)
    z = np.cos(v)

    fig = go.Figure(data=[go.Surface(x=x, y=y, z=z, colorscale='Greys', opacity=0.5, showscale=False)])

    # 回転軸のベクトルを表示
    vx = np.sin(angle_rad)
    vy = 0
    vz = np.cos(angle_rad)

    fig.add_trace(go.Scatter3d(x=[0, vx], y=[0, vy], z=[0, vz],
                                mode='lines+markers', line=dict(color='red', width=10),
                                name=f'Spin Axis ({spin_direction_str})'))
    
    fig.update_layout(title=f"{pitch_type} の回転軸イメージ", scene=dict(
        xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)
    ))
    return fig

# 4. 投球位置 (Strike Zone)
def plot_plate_location(df):
    fig = px.scatter(df, x='Strike Zone Side', y='Strike Zone Height', 
                     color='Pitch Type', title='投球位置 (Pitch Location)',
                     range_x=[-100, 100], range_y=[0, 200])
    # 簡易的なストライクゾーンの枠を追加
    fig.add_shape(type="rect", x0=-25, y0=45, x1=25, y1=105, line=dict(color="Black"))
    return fig

# 実行例（一部を表示）
# fig_movement = plot_movement(df)
# fig_movement.show()
