# python batch_convert_shapefiles_2.py
import os
import json
import rasterio
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import numpy as np

def convert_shp_to_pixel_json(tif_path, shp_path, output_json_path):
    """
    將 Shapefile 的地理座標轉換為對應 TIFF 的像素座標，並輸出 JSON。
    """
    try:
        # 1. 讀取 TIFF 影像資訊
        with rasterio.open(tif_path) as src:
            transform = src.transform
            width = src.width
            height = src.height
            crs = src.crs
            # 取得逆矩陣，雖然現在我們改用 rowcol 方法，但保留以防萬一
            inv_transform = ~transform

        # 2. 讀取 Shapefile
        gdf = gpd.read_file(shp_path)
        
        # 確保 CRS 一致 (如果不一致則轉投影)
        if gdf.crs != crs:
            print(f"  [Reprojecting] Shapefile CRS {gdf.crs} -> TIFF CRS {crs}")
            gdf = gdf.to_crs(crs)

        shapes = []
        
        for _, row in gdf.iterrows():
            geom = row.geometry
            # 修正：使用 geom_type 以避免警告
            if geom.geom_type == 'Polygon':
                polys = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polys = list(geom.geoms)
            else:
                continue # Skip points/lines
            
            for poly in polys:
                # 取得外框座標 (Exterior ring)
                if poly.exterior is None:
                    continue
                    
                exterior_coords = list(poly.exterior.coords)
                
                # 分離 X 和 Y 座標
                xs, ys = zip(*exterior_coords)
                
                # 修正：使用 rasterio 的 rowcol 方法進行座標轉換
                # rowcol 回傳的是 (row, col) 即 (y, x)
                # op is meant for inverse transformation: map -> pixel
                rows, cols = rasterio.transform.rowcol(transform, xs, ys)
                
                points = []
                for r, c in zip(rows, cols):
                    # LabelMe 使用 [x, y] 格式，對應 [col, row]
                    # 強制轉為 int 避免 JSON 序列化錯誤，且像素座標通常為整數
                    points.append([float(c), float(r)])

                shape_data = {
                    "label": "oil", # 統一標籤名稱
                    "points": points,
                    "group_id": None,
                    "shape_type": "polygon",
                    "flags": {}
                }
                shapes.append(shape_data)

        # 3. 輸出 LabelMe JSON 格式
        json_data = {
            "version": "5.2.1",
            "flags": {},
            "shapes": shapes,
            "imagePath": os.path.basename(tif_path),
            "imageData": None, # LabelMe 會自動讀取圖片，不需要編碼
            "imageHeight": height,
            "imageWidth": width
        }

        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
            
        print(f"  [Success] Generated: {output_json_path}")

    except Exception as e:
        print(f"  [ERROR] {os.path.basename(tif_path)} 處理失敗: {e}")
        import traceback
        traceback.print_exc()

def find_shapefile_recursive(root_dir, date_str):
    """
    在 root_dir 下遞迴尋找檔名包含 date_str 的 .shp 檔案
    排除包含 'Point' 的點位檔
    """
    # 確保 date_str 只有日期部分，避免檔名有其他前綴干擾
    search_key = date_str 
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith('.shp') and search_key in f:
                if 'point' in f.lower(): # Skip point sources
                    continue
                return os.path.join(dirpath, f)
    return None

def batch_process(img_root_dir, shp_root_dir):
    print(f"開始批次處理...")
    print(f"影像目錄: {img_root_dir}")
    print(f"標記目錄: {shp_root_dir}")

    if not os.path.exists(img_root_dir):
        print(f"找不到影像目錄")
        return

    # 1. 直接取得所有 TIF 檔案 (不看資料夾)
    tif_files = [f for f in os.listdir(img_root_dir) if f.lower().endswith('.tif')]
    
    count = 0
    for tif_file in tif_files:
        # 檔名範例: 20190530_S2_Atlantic_Ocean_mosaic.tif
        # 取前 8 碼作為日期: 20190530
        date_key = tif_file[:8]
        
        tif_full_path = os.path.join(img_root_dir, tif_file)
        
        # 2. 去找對應的 SHP
        print(f"處理影像: {tif_file} (Date: {date_key})")
        
        shp_path = find_shapefile_recursive(shp_root_dir, date_key)
        
        if shp_path:
            print(f"  -> 找到標記: {shp_path}")
            
            # 定義輸出 JSON 路徑 (與 TIF 同目錄同名)
            json_output_path = os.path.splitext(tif_full_path)[0] + ".json"
            
            convert_shp_to_pixel_json(tif_full_path, shp_path, json_output_path)
            count += 1
        else:
            print(f"  [Warning] 找不到日期 {date_key} 的 Shapefile")

    print(f"\n批次處理完成！共產生了 {count} 個 JSON 標記檔。")

if __name__ == "__main__":
    # 設定根目錄
    IMG_ROOT = r"D:\oil_project\dataset\NewData_1017\for_csie_original\new_acolite_composites\NOAA_Gulf_of_Mexico_High Confidence"
    SHP_ROOT = r"D:\oil_project\dataset\NewData_1017\for_csie_original\new_有附原始壓縮檔的_NOAA報告\NOAA_Gulf of Mexico_High Confidence\2020"
    
    batch_process(IMG_ROOT, SHP_ROOT)