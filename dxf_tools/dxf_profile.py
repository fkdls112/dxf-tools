"""
DXF 断面图生成工具
从 DXF 红线图中提取地形剖面，生成断面图 PNG
"""
import sys
import json
import math
import argparse
from collections import defaultdict

from shapely.geometry import LineString, Point

from .dxf2json import parse_dxf_raw, get_val


def extract_contours(entities):
    """提取 DGX 等高线"""
    contours = []
    for e in entities:
        if (e.get('type') == 'LWPOLYLINE' 
            and get_val(e['props'], '8', '') == 'DGX'
            and len(e.get('points', [])) >= 2):
            pts = [(p[0], p[1]) for p in e['points'] 
                   if p[0] is not None and p[1] is not None]
            if len(pts) >= 2:
                elev = get_val(e['props'], '38')
                if elev is not None:
                    contours.append((float(elev), LineString(pts)))
    return contours


def extract_towers(entities, layer='COMPONENT'):
    """提取索道/支架点"""
    towers = []
    for e in entities:
        if (e.get('type') == 'INSERT' 
            and get_val(e['props'], '8', '') == layer):
            pts = e.get('points', [])
            if pts and pts[0][0] is not None and pts[0][1] is not None:
                towers.append((pts[0][0], pts[0][1]))
    
    # 去重（5m 内视为同一支架）
    unique = []
    for pt in towers:
        if not any(((pt[0]-u[0])**2 + (pt[1]-u[1])**2)**0.5 < 5 
                   for u in unique):
            unique.append(pt)
    
    # Y 坐标排序（默认南北方向）
    unique.sort(key=lambda p: p[1])
    return unique


def sample_elevation(cable_line, contours, step=10, max_search=300):
    """沿索道线采样高程"""
    total_len = cable_line.length
    results = []
    
    for dist in range(0, int(total_len) + step, step):
        pt = cable_line.interpolate(dist)
        pt_shapely = Point(pt.x, pt.y)
        
        # 找最近的等高线
        nearby = []
        for elev, line in contours:
            d = line.distance(pt_shapely)
            if d < max_search:
                nearby.append((d, elev))
        
        if not nearby:
            continue
        
        nearby.sort()
        if len(nearby) >= 2:
            d1, e1 = nearby[0]
            d2, e2 = nearby[1]
            elev = (e1 * d2 + e2 * d1) / (d1 + d2) if (d1 + d2) > 0 else e1
        else:
            elev = nearby[0][1]
        
        results.append((dist, elev))
    
    return results


def generate_profile_image(dists, elevs, towers, tower_labels=None, 
                           output='profile.png', title='地形断面图'):
    """生成断面图 PNG"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, ax = plt.subplots(figsize=(16, 6))
    
    min_e, max_e = min(elevs), max(elevs)
    
    # 地形填充
    ax.fill_between(dists, elevs, min_e - 30, alpha=0.25, color='#4CAF50')
    ax.plot(dists, elevs, 'brown', linewidth=1.8, label='地形剖面')
    
    # 支架标注
    cable_line = LineString([(t[0], t[1]) for t in towers])
    for i, t in enumerate(towers):
        td = cable_line.project(Point(t[0], t[1]))
        # 找剖面上最近点
        idx = min(range(len(dists)), key=lambda j: abs(dists[j] - td))
        profile_elev = elevs[idx]
        
        label = tower_labels[i] if tower_labels else f'T{i+1}'
        ax.plot(td, profile_elev, 'ro', markersize=10, zorder=5)
        ax.annotate(label, (td, profile_elev),
                    textcoords="offset points", xytext=(0, 15),
                    ha='center', fontsize=11, fontweight='bold', color='darkred')
        ax.vlines(td, profile_elev, profile_elev + 60, 
                  colors='red', linestyles='--', alpha=0.4, linewidth=0.8)
    
    # 标签
    total_len = cable_line.length
    h_diff = max_e - min_e
    ax.set_title(f'{title}\n总长: {total_len:.0f}m | 高差: {h_diff:.0f}m | 支架: {len(towers)}座',
                 fontsize=13, fontweight='bold')
    ax.set_xlabel('距离 (m)', fontsize=12)
    ax.set_ylabel('高程 (m)', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')
    ax.set_ylim(min_e - 30, max_e + 50)
    
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'✅ 断面图: {output}', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='DXF断面图生成工具')
    parser.add_argument('dxf_file', help='DXF 文件路径')
    parser.add_argument('-o', '--output', default='profile.png', help='输出 PNG 路径 (默认: profile.png)')
    parser.add_argument('-t', '--tower-layer', default='COMPONENT', 
                       help='索道支架图层名 (默认: COMPONENT)')
    parser.add_argument('-c', '--contour-layer', default='DGX',
                       help='等高线图层名 (默认: DGX)')
    parser.add_argument('-s', '--step', type=int, default=10,
                       help='采样步长 m (默认: 10)')
    parser.add_argument('--title', default='地形断面图', help='图标题')
    parser.add_argument('--labels', nargs='*', help='支架标签 (空格分隔)')
    parser.add_argument('--json', help='额外输出剖面 JSON 数据文件')
    args = parser.parse_args()

    print(f'📖 解析 DXF: {args.dxf_file}', file=sys.stderr)
    entities = parse_dxf_raw(args.dxf_file)
    print(f'   实体总数: {len(entities)}', file=sys.stderr)
    
    # 提取等高线
    contours = [c for c in extract_contours(entities) 
                if get_val(next((e for e in entities if e['type']=='LWPOLYLINE'), {}).get('props',{}),'8','') == args.contour_layer
                or True]  # 保留所有
    # 重新正确提取
    contours = []
    for e in entities:
        if (e.get('type') == 'LWPOLYLINE' 
            and get_val(e['props'], '8', '') == args.contour_layer
            and len(e.get('points', [])) >= 2):
            pts = [(p[0], p[1]) for p in e['points'] 
                   if p[0] is not None and p[1] is not None]
            if len(pts) >= 2:
                elev = get_val(e['props'], '38')
                if elev is not None:
                    contours.append((float(elev), LineString(pts)))
    print(f'   等高线: {len(contours)} 条', file=sys.stderr)
    
    # 提取支架
    towers = extract_towers(entities, layer=args.tower_layer)
    print(f'   支架点: {len(towers)} 座', file=sys.stderr)
    
    if not towers:
        print('⚠️  未找到支架点，尝试生成全地形断面...', file=sys.stderr)
        # 手动指定断面线：用等高线范围两端
        all_x, all_y = [], []
        for _, line in contours:
            all_x.extend([line.bounds[0], line.bounds[2]])
            all_y.extend([line.bounds[1], line.bounds[3]])
        if all_x and all_y:
            towers = [(min(all_x), min(all_y)), (max(all_x), max(all_y))]
    
    if not contours:
        print('❌ 未找到等高线', file=sys.stderr)
        sys.exit(1)
    
    # 构建索道线
    cable_line = LineString([(t[0], t[1]) for t in towers])
    total_len = cable_line.length
    print(f'   索道线长: {total_len:.0f}m', file=sys.stderr)
    
    # 采样高程
    profile = sample_elevation(cable_line, contours, step=args.step)
    if not profile:
        print('❌ 采样失败，等高线可能不在索道线范围内', file=sys.stderr)
        # 扩大搜索
        profile = sample_elevation(cable_line, contours, step=args.step, max_search=500)
    
    if not profile:
        print('❌ 仍失败', file=sys.stderr)
        sys.exit(1)
    
    dists = [p[0] for p in profile]
    elevs = [p[1] for p in profile]
    print(f'   剖面采样: {len(profile)} 点, 高程 {min(elevs):.0f}~{max(elevs):.0f}m', file=sys.stderr)
    
    # 出图
    labels = args.labels if args.labels else None
    generate_profile_image(dists, elevs, towers, tower_labels=labels,
                          output=args.output, title=args.title)
    
    # 输出 JSON
    if args.json:
        data = {
            'towers': towers,
            'total_length': total_len,
            'profile': [(d, e) for d, e in profile],
            'elev_range': [min(elevs), max(elevs)],
        }
        with open(args.json, 'w') as f:
            json.dump(data, f, ensure_ascii=False)
        print(f'✅ JSON: {args.json}', file=sys.stderr)


if __name__ == '__main__':
    main()
