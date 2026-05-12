#!/usr/bin/env python3
"""DXF 解析命令行工具集 —— 从 DWG/DXF 红线图中提取地形数据、生成断面图"""

from setuptools import setup, find_packages

setup(
    name="dxf-tools",
    version="1.0.0",
    description="DWG/DXF 红线图地形分析工具——等高线提取、高程点解析、断面图生成",
    author="fkdls112",
    packages=find_packages(),
    install_requires=[
        "shapely>=2.0",
        "matplotlib>=3.5",
    ],
    entry_points={
        "console_scripts": [
            "dxf2json=dxf_tools.dxf2json:main",
            "dxf-profile=dxf_tools.dxf_profile:main",
        ],
    },
    python_requires=">=3.9",
)
