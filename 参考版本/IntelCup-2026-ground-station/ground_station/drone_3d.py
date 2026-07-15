"""
IntelCup 地面站 - 无人机3D仿真视图（精简稳定版）
"""
import math
import numpy as np
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph.opengl as gl


class Drone3DView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=80, elevation=30, azimuth=45)
        self.view.setBackgroundColor('w')
        self.view.opts['bgcolor'] = (0.92, 0.93, 0.95, 1.0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self._drone_items = []
        self._path_line = None
        self._path_pts = []
        self._wp_items = []      # 航点标记
        self._px = self._py = self._pz = 0
        self._pr = self._pp = self._pyaw = 0

        # 地面
        # 地面（半透明白）
        gv = np.array([[-50,-50,-0.1],[50,-50,-0.1],[50,50,-0.1],[-50,50,-0.1]], dtype=float)
        gf = np.array([[0,1,2],[0,2,3]])
        gc = np.array([[0.92,0.93,0.95,0.5]]*2)
        self.view.addItem(gl.GLMeshItem(vertexes=gv, faces=gf, faceColors=gc, smooth=False, shader='shaded'))

        # 主网格（稀疏大格）
        gx = gl.GLGridItem()
        gx.setSize(100, 100); gx.setSpacing(5, 5)
        gx.setColor((0.2, 0.2, 0.2, 0.5))
        self.view.addItem(gx)

        # 次要网格（密集小格）- 用线绘制
        for i in range(-50, 51, 2):
            if i % 10 != 0 and i % 5 != 0:
                pts = np.array([[i, -50, 0], [i, 50, 0]], dtype=float)
                self.view.addItem(gl.GLLinePlotItem(pos=pts, color=(0.5,0.5,0.5,0.15), width=1))
                pts = np.array([[-50, i, 0], [50, i, 0]], dtype=float)
                self.view.addItem(gl.GLLinePlotItem(pos=pts, color=(0.5,0.5,0.5,0.15), width=1))
        # 5格线（中格）
        for i in range(-50, 51, 5):
            if i % 10 != 0:
                pts = np.array([[i, -50, 0], [i, 50, 0]], dtype=float)
                self.view.addItem(gl.GLLinePlotItem(pos=pts, color=(0.4,0.4,0.4,0.3), width=1))
                pts = np.array([[-50, i, 0], [50, i, 0]], dtype=float)
                self.view.addItem(gl.GLLinePlotItem(pos=pts, color=(0.4,0.4,0.4,0.3), width=1))
        # 坐标轴
        for i, c in enumerate([(1,0,0,1),(0,1,0,1),(0,0,1,1)]):
            pts = np.array([[0,0,0],[0,0,0]], dtype=float)
            pts[1][i] = 8
            self.view.addItem(gl.GLLinePlotItem(pos=pts, color=c, width=3))

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_waypoints(self, wps):
        """设置绿色航点标记"""
        for item in self._wp_items:
            self.view.removeItem(item)
        self._wp_items.clear()
        if not wps:
            return
        # 画航点之间的连线
        pts_list = [(0,0,0.5)] + [(x, y, 0.5) for x, y in wps]
        for i in range(len(pts_list) - 1):
            pts = np.array([pts_list[i], pts_list[i+1]], dtype=float)
            self.view.addItem(gl.GLLinePlotItem(pos=pts, color=(0.2,0.8,0.2,0.3), width=1, antialias=True))
        # 画航点标记（绿色圆柱）
        for x, y in wps:
            verts, faces, colors = self._cyl(0.4, 0.15, (0.2, 0.8, 0.2, 0.7))
            verts[:,0] += x; verts[:,1] += y; verts[:,2] += 0.5
            mesh = gl.GLMeshItem(vertexes=verts, faces=faces, faceColors=colors,
                                  smooth=True, shader='shaded')
            self.view.addItem(mesh)
            self._wp_items.append(mesh)
        # 起飞点（绿色大点）
        verts, faces, colors = self._cyl(0.6, 0.2, (0.1, 0.9, 0.1, 0.8))
        verts[:,0] += pts_list[0][0]; verts[:,1] += pts_list[0][1]; verts[:,2] += 0.5
        mesh = gl.GLMeshItem(vertexes=verts, faces=faces, faceColors=colors,
                              smooth=True, shader='shaded')
        self.view.addItem(mesh)
        self._wp_items.append(mesh)
    def set_drone_state(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
        self._px, self._py, self._pz = x, y, z
        self._pr, self._pp, self._pyaw = roll, pitch, yaw
    def start(self): self._timer.start()
    def stop(self): self._timer.stop()

    def _rot(self, pts, roll, pitch, yaw):
        """绕原点旋转点集"""
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        out = np.empty_like(pts)
        # Yaw (Z)
        out[:,0] = pts[:,0]*cy - pts[:,1]*sy
        out[:,1] = pts[:,0]*sy + pts[:,1]*cy
        out[:,2] = pts[:,2]
        # Pitch (Y)
        tmp = out.copy()
        out[:,0] = tmp[:,0]*cp + tmp[:,2]*sp
        out[:,2] = -tmp[:,0]*sp + tmp[:,2]*cp
        # Roll (X)
        tmp = out.copy()
        out[:,1] = tmp[:,1]*cr - tmp[:,2]*sr
        out[:,2] = tmp[:,1]*sr + tmp[:,2]*cr
        return out

    def _box(self, w, h, d, color):
        verts = np.array([
            [-w,-d,-h],[w,-d,-h],[w,d,-h],[-w,d,-h],
            [-w,-d, h],[w,-d, h],[w,d, h],[-w,d, h]], dtype=float)
        faces = np.array([
            [0,1,2],[0,2,3],[1,5,6],[1,6,2],[5,4,7],[5,7,6],
            [4,0,3],[4,3,7],[3,2,6],[3,6,7],[1,0,4],[1,4,5]])
        return verts, faces, np.array([color]*12)

    def _cyl(self, r, h, color, seg=16):
        verts, faces = [], []
        for i in range(seg):
            a1 = 2*math.pi*i/seg; a2 = 2*math.pi*(i+1)/seg
            x1, z1 = math.cos(a1)*r, math.sin(a1)*r
            x2, z2 = math.cos(a2)*r, math.sin(a2)*r
            hh = h/2
            n = len(verts)
            verts += [[x1,-hh,z1],[x2,-hh,z2],[x2,hh,z2],[x1,hh,z1]]
            faces += [[n,n+1,n+2],[n,n+2,n+3]]
            n2 = len(verts)
            verts += [[x1,hh,z1],[x2,hh,z2],[0,hh,0]]
            faces += [[n2,n2+1,n2+2]]
            n3 = len(verts)
            verts += [[x1,-hh,z1],[x2,-hh,z2],[0,-hh,0]]
            faces += [[n3,n3+1,n3+2]]
        return np.array(verts), np.array(faces), np.array([color]*len(faces))

    def _disk(self, r, color, alpha=0.5, seg=24):
        verts = [[0,0,0]]
        for i in range(seg+1):
            a = 2*math.pi*i/seg
            verts.append([math.cos(a)*r, 0, math.sin(a)*r])
        faces = [[0,i+1,(i+1)%seg+1] for i in range(seg)]
        return np.array(verts), np.array(faces), np.array([color]*seg)

    def _build_model(self, x, y, z, roll, pitch, yaw):
        """构建四旋翼，全部在原点构建后统一旋转平移"""
        all_verts = []
        all_faces = []
        all_colors = []
        offset = 0

        def add(verts, faces, colors):
            nonlocal offset
            all_verts.append(verts)
            all_faces.append(faces + offset)
            all_colors.append(colors)
            offset += len(verts)

        # 1. 中心机身
        v, f, c = self._box(0.7, 0.25, 0.7, (0.15, 0.50, 0.85, 1))
        add(v, f, c)
        # 上盖
        v, f, c = self._box(0.6, 0.05, 0.6, (0.3, 0.3, 0.3, 1))
        v[:,1] += 0.15  # 抬高一点
        add(v, f, c)

        # 2. 四根机臂 + 电机 + 螺旋桨
        arm_len = 2.8
        motor_colors = [(0.8,0.15,0.15,1),(0.15,0.6,0.15,1),(0.15,0.15,0.8,1),(0.8,0.7,0.1,1)]
        for idx, (ex, ey) in enumerate([(1,1),(-1,1),(1,-1),(-1,-1)]):
            nx = ex * arm_len / math.sqrt(2)
            ny = ey * arm_len / math.sqrt(2)
            angle = math.atan2(ey, ex)

            # 机臂：沿X轴方向做细长条，再旋转到目标方向
            aw, ah, al = 0.12, 0.08, arm_len * 0.65
            v = np.array([
                [-aw,-ah,0],[aw,-ah,0],[aw,ah,0],[-aw,ah,0],
                [-aw,-ah,al],[aw,-ah,al],[aw,ah,al],[-aw,ah,al]
            ], dtype=float)
            # 旋转到目标方向
            ca, sa = math.cos(angle), math.sin(angle)
            for p in v:
                px, py = p[0]*ca - p[2]*sa, p[0]*sa + p[2]*ca
                p[0], p[2] = px, py
            # 平移到正确位置（臂从原点延伸到臂端的一半）
            mx, my = nx * 0.5, ny * 0.5
            v[:,0] += mx; v[:,1] += my
            # 机臂是中心对称的，一半在中心内一半在外
            v2 = v.copy()
            v2[:,0] = -v[:,0]; v2[:,1] = -v[:,1]
            f = np.array([
                [0,1,2],[0,2,3],[1,5,6],[1,6,2],
                [5,4,7],[5,7,6],[4,0,3],[4,3,7],
                [3,2,6],[3,6,7],[1,0,4],[1,4,5]
            ])
            c = np.array([[0.25,0.25,0.25,1]]*12)
            add(v, f, c)

            # 电机（圆柱体，在臂末端）
            mv, mf, mc = self._cyl(0.25, 0.3, motor_colors[idx])
            mv[:,0] += nx; mv[:,1] += ny; mv[:,2] += 0.15
            add(mv, mf, mc)

            # 螺旋桨（薄圆盘，在电机上方）
            pv, pf, pc = self._disk(0.65, (0.7, 0.7, 0.7, 0.4))
            pv[:,0] += nx; pv[:,1] += ny; pv[:,2] += 0.35
            add(pv, pf, pc)

        # 合并所有顶点
        verts = np.vstack(all_verts)
        faces = np.vstack(all_faces)
        colors = np.vstack(all_colors)

        # 整体旋转
        verts = self._rot(verts, roll, pitch, yaw)
        # 平移到位
        verts[:,0] += x; verts[:,1] += y; verts[:,2] += z

        return gl.GLMeshItem(vertexes=verts, faces=faces, faceColors=colors,
                              smooth=True, shader='shaded')

    def _tick(self):
        # 轨迹
        self._path_pts.append([self._px, self._py, max(self._pz, 0)])
        if len(self._path_pts) > 2000: self._path_pts.pop(0)
        if len(self._path_pts) > 1:
            pts = np.array(self._path_pts)
            if self._path_line: self.view.removeItem(self._path_line)
            self._path_line = gl.GLLinePlotItem(pos=pts, color=(1,0.6,0,0.8), width=2)
            self.view.addItem(self._path_line)

        # 清除旧模型
        for item in self._drone_items:
            self.view.removeItem(item)
        self._drone_items.clear()

        # 建新模型
        mesh = self._build_model(self._px, self._py, max(self._pz, 0.2),
                                 self._pr, self._pp, self._pyaw)
        self.view.addItem(mesh)
        self._drone_items.append(mesh)
