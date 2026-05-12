"""
DXF 实体提取 → JSON
将 DXF 文件解析为结构化 JSON，支持容错读取（兼容 libredwg 转换的损坏文件）
"""
import json
import sys
import math
from collections import defaultdict


def parse_dxf_raw(path):
    """底层 DXF 解析器，返回所有实体列表"""
    with open(path, 'rb') as f:
        raw = f.read()
    text = raw.replace(b'\r\n', b'\n').decode('utf-8', errors='ignore')
    lines = [l.strip() for l in text.split('\n')]

    # 定位 ENTITIES section
    ent_start = ent_end = None
    for i in range(len(lines)):
        if (lines[i] == 'ENTITIES' and i >= 2 
            and lines[i-1] == '2' and lines[i-2] == 'SECTION'):
            ent_start = i + 1
        if (ent_start and i > ent_start 
            and lines[i] == 'ENDSEC' and lines[i-1] == '0'):
            ent_end = i - 1
            break
    
    if not ent_start or not ent_end:
        raise ValueError("未找到 ENTITIES section")

    entities = []
    i = ent_start
    while i < ent_end:
        if lines[i] == '0':
            i += 1
            if i >= ent_end:
                break
            etype = lines[i]
            entity = {'type': etype, 'props': {}, 'points': []}
            i += 1
            while i < ent_end:
                if lines[i] == '0':
                    break
                code = lines[i]
                if i + 1 >= ent_end:
                    break
                val = lines[i+1]
                if code in ('10', '20', '30'):
                    entity['props'].setdefault(code, []).append(val)
                else:
                    entity['props'][code] = val
                i += 2
            
            # 组装坐标点
            xs = entity['props'].get('10', [])
            ys = entity['props'].get('20', [])
            zs = entity['props'].get('30', [])
            for j in range(max(len(xs), len(ys))):
                x = float(xs[j]) if j < len(xs) else None
                y = float(ys[j]) if j < len(ys) else None
                z = float(zs[j]) if j < len(zs) else None
                entity['points'].append([x, y, z])
            
            entities.append(entity)
        else:
            i += 1

    return entities


def get_val(props, code, default=None):
    """安全获取属性值（兼容 list 和标量）"""
    v = props.get(code, default)
    if isinstance(v, list):
        return v[0] if v else default
    return v


def analyze(entities):
    """统计并生成摘要"""
    layer_stats = defaultdict(lambda: {'count': 0, 'types': defaultdict(int)})
    for e in entities:
        layer = get_val(e['props'], '8', 'UNKNOWN')
        etype = e.get('type', 'UNKNOWN')
        layer_stats[layer]['count'] += 1
        layer_stats[layer]['types'][etype] += 1
    return layer_stats


def to_geojson(entities):
    """将实体转为 GeoJSON FeatureCollection"""
    features = []
    for e in entities:
        layer = get_val(e['props'], '8', 'UNKNOWN')
        etype = e.get('type', 'UNKNOWN')
        pts = e.get('points', [])
        
        geom = None
        if etype == 'LWPOLYLINE' and len(pts) >= 2:
            coords = [[p[0], p[1]] for p in pts if p[0] is not None and p[1] is not None]
            if len(coords) >= 2:
                geom = {"type": "LineString", "coordinates": coords}
        elif etype == 'LINE' and len(pts) >= 2:
            coords = [[p[0], p[1]] for p in pts[:2] if p[0] is not None and p[1] is not None]
            if len(coords) == 2:
                geom = {"type": "LineString", "coordinates": coords}
        elif etype in ('INSERT', 'TEXT', 'ATTRIB') and len(pts) >= 1:
            p = pts[0]
            if p[0] is not None and p[1] is not None:
                geom = {"type": "Point", "coordinates": [p[0], p[1]]}
        
        if geom:
            prop = {
                "Layer": layer,
                "Type": etype,
                "Handle": get_val(e['props'], '5', ''),
            }
            if etype in ('LWPOLYLINE',):
                elev = get_val(e['props'], '38')
                if elev:
                    prop["Elevation"] = float(elev)
            if etype in ('TEXT', 'ATTRIB'):
                txt = get_val(e['props'], '1', '')
                if txt:
                    prop["Text"] = txt
            
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": prop,
            })
    
    return {"type": "FeatureCollection", "features": features}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='DXF → JSON 转换工具')
    parser.add_argument('dxf_file', help='DXF 文件路径')
    parser.add_argument('-o', '--output', default='-', help='输出 JSON 文件路径 (默认: stdout)')
    parser.add_argument('-f', '--format', choices=['summary', 'geojson', 'entities'], 
                       default='geojson', help='输出格式 (默认: geojson)')
    parser.add_argument('-l', '--layer', help='只输出指定图层')
    parser.add_argument('--raw', action='store_true', help='输出原始实体列表（不转 GeoJSON）')
    args = parser.parse_args()

    entities = parse_dxf_raw(args.dxf_file)
    
    if args.layer:
        entities = [e for e in entities if get_val(e['props'], '8', '') == args.layer]
    
    if args.format == 'summary':
        stats = analyze(entities)
        result = {layer: {'count': s['count'], 'types': dict(s['types'])} 
                  for layer, s in stats.items()}
    elif args.format == 'entities':
        result = entities
    else:
        result = to_geojson(entities)
    
    json_str = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output == '-':
        print(json_str)
    else:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json_str)
        print(f'✅ 输出: {args.output} ({len(entities)} 实体)', file=sys.stderr)


if __name__ == '__main__':
    main()
