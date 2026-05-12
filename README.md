# dxf-tools

DWG/DXF 地形图分析命令行工具集。

从 CAD 地形图中提取等高线、高程点、工程节点，生成地形断面图。

## 适用场景

- 📐 **线性工程**：从地形图自动提取线路断面
- 🗺️ **GIS 分析**：批量导出 DXF 图层为 GeoJSON
- 🏗️ **工程设计**：快速获取高程范围、高差等关键参数

## 安装

```bash
pip install git+https://github.com/fkdls112/dxf-tools.git
```

依赖：Python 3.9+，shapely，matplotlib。

## 命令

### `dxf2json` — DXF → JSON

```bash
# 图层摘要
dxf2json 地形图.dxf -f summary

# 导出全部图层为 GeoJSON
dxf2json 地形图.dxf -o output.geojson

# 只导出等高线图层
dxf2json 地形图.dxf -l DGX -o contours.geojson

# 输出原始实体列表（用于二次开发）
dxf2json 地形图.dxf -f entities -o entities.json
```

**输出格式**：

| `-f` | 说明 |
|------|------|
| `summary` | 图层 + 实体类型统计 |
| `geojson` | 标准 GeoJSON FeatureCollection（默认） |
| `entities` | 原始实体属性列表 |

### `dxf-profile` — 生成断面图

```bash
# 自动检测节点层（COMPONENT），生成断面图
dxf-profile 地形图.dxf -o 断面图.png --title "工程线路断面"

# 指定节点图层和等高线图层
dxf-profile 地形图.dxf -t MY_NODES -c MY_CONTOUR

# 同时输出 JSON 数据
dxf-profile 地形图.dxf --json profile.json

# 自定义节点标签
dxf-profile 地形图.dxf --labels 起点 N1 N2 N3 N4 N5 N6 N7 N8 终点
```

## 支持的 DXF 格式

- ✅ AutoCAD 原生 DXF（R12~R2018）
- ✅ LibreDWG `dwg2dxf` 转换输出（容错解析）
- ✅ GDAL `ogr2ogr` 导出的 DXF

## 容错说明

本工具针对 **LibreDWG 转换的损坏 DXF**（handle=0、缺失 ENDBLK 等）做了专门容错，即使 ezdxf 和 GDAL 报错也能完整解析。

实测：某项目地形图（18MB DXF），ezdxf 无法读取，GDAL 仅解析 17% 实体，本工具完整提取 11,131 个实体。

## 示例输出

```
$ dxf2json 地形图.dxf -f summary

DGX:    1348 (LWPOLYLINE:1348)    ← 等高线
GCD:    2817 (INSERT:939, ATTRIB:939, SEQEND:939)  ← 高程点
DLSS:   1848 (LINE:1790, LWPOLYLINE:48)  ← 地类界
COMPONENT: 13 (INSERT:13)         ← 线路节点
```

```
$ dxf-profile 地形图.dxf -o profile.png

📖 解析 DXF
   实体总数: 11131
   等高线: 1348 条
   节点数: 9 个
   线路总长: 2140m
   剖面采样: 215 点, 高程 2525~2895m
✅ 断面图: profile.png
```

## 断面图示例

![断面图](https://raw.githubusercontent.com/fkdls112/dxf-tools/main/screenshots/profile.png)

## License

MIT
