import os
import glob
import json
import numpy as np
import rasterio
import cv2
from pathlib import Path
from tqdm import tqdm
import shutil

# === 修改成你目前的路徑架構 ===
IMG_BASE_DIR = "/home/alanyh/oil_dataset/new_NOAA_Atlantic_Ocean_High_Confidence"
JSON_DIR = "/home/alanyh/oil_dataset/new_NOAA_Atlantic_Ocean_High_Confidence/JSON"

# ================== 功能開關區 ================== 
# 開啟這個模式，PNG 不會烙印框線（保持乾淨），並會自動複製、修改對應的 JSON 到同一個資料夾。
# 你可以直接用 LabelMe 開啟這個資料夾，圖片與標記框會完美疊合，方便二次編輯！
LABELME_READY_MODE = True

# 若上方的 LABELME_READY_MODE 為 False，則退回原來的直接導圖模式 (可選要不要把線燙在圖上)
OVERLAP = False
# ================================================

if LABELME_READY_MODE:
    OUT_DIR = "/home/alanyh/oil_dataset/new_NOAA_Atlantic_Ocean_High_Confidence/LabelMe_Workspace"
else:
    OUT_DIR = "/home/alanyh/oil_dataset/new_NOAA_Atlantic_Ocean_High_Confidence/NIR_R_G_Output"

os.makedirs(OUT_DIR, exist_ok=True)

def stretch_percentile(band, p_low=1, p_high=99):
    valid_mask = (band > 0) & (band < 15000)
    if not np.any(valid_mask):
        return np.zeros_like(band, dtype=np.uint8)
    
    valid_pixels = band[valid_mask]
    p_min, p_max = np.percentile(valid_pixels, (p_low, p_high))
    
    band_clipped = np.clip(band, p_min, p_max)
    band_scaled = (band_clipped - p_min) / (p_max - p_min + 1e-8) * 255.0
    band_scaled[~valid_mask] = 0
    return band_scaled.astype(np.uint8)

def find_band_file(band_dir, possible_suffixes):
    for suffix in possible_suffixes:
        found = glob.glob(os.path.join(band_dir, f"*{suffix}"))
        if found:
            return found[0]
    return None

def main():
    print("掃描影像目錄...")
    tasks = []
    years = ["2019", "2025"] 
    for y in years:
        year_dir = os.path.join(IMG_BASE_DIR, y)
        if os.path.exists(year_dir):
            # 新增 L9，才能抓到所有事件資料夾
            scene_folders = glob.glob(os.path.join(year_dir, "*_S2")) + glob.glob(os.path.join(year_dir, "*L8")) + glob.glob(os.path.join(year_dir, "*L9"))
            tasks.extend(scene_folders)
            
    print(f"共找到 {len(tasks)} 個衛星事件，準備開始處理... \n輸出目錄: {OUT_DIR}")
    
    for scene_folder in tqdm(tasks):
        scene_name = os.path.basename(scene_folder) 
        
        band_10m_dir = os.path.join(scene_folder, "10m")
        band_20m_dir = os.path.join(scene_folder, "20m")
        
        # 兼容 Landsat 波段: _865 (NIR), _654/_655 (R), _561 (G)
        # 兼容 Sentinel-2 波段: _833/_842 (NIR), _665 (R), _560 (G)
        
        nir_path = find_band_file(band_10m_dir, ["_833.tif", "_835.tif", "_842.tif", "_865.tif"])
        if not nir_path:
            nir_path = find_band_file(band_20m_dir, ["_865.tif", "_864.tif"])
            
        r_path   = find_band_file(band_10m_dir, ["_665.tif", "_667.tif", "_654.tif", "_655.tif"])
        g_path   = find_band_file(band_10m_dir, ["_560.tif", "_559.tif", "_561.tif"])
        
        if not r_path or not g_path or not nir_path:
            print(f"  [跳過] 找不到完整 NIR/R/G 波段: {scene_name}")
            continue
            
        json_search = glob.glob(os.path.join(JSON_DIR, f"{scene_name}*.json"))
        if not json_search:
            print(f"  [跳過] JSON 目錄裡找不到對應配對檔: {scene_name}")
            continue
            
        json_file = json_search[0]
        json_basename = os.path.splitext(os.path.basename(json_file))[0]
        
        if LABELME_READY_MODE:
            out_png_name = f"{json_basename}.png"
            out_json_name = f"{json_basename}.json"
            print(f"\n  [轉換為 LabelMe 格式] {json_basename}")
        else:
            out_png_name = f"{scene_name}_NIR_R_G.png"
            if OVERLAP:
                 print(f"\n  [處理純影像-疊加框線] {scene_name}")
            else:
                 print(f"\n  [處理純影像-無疊加] {scene_name}")
             
        try:
            with rasterio.open(nir_path) as src_nir, \
                 rasterio.open(r_path) as src_r, \
                 rasterio.open(g_path) as src_g:
                 
                 b_nir = src_nir.read(1)
                 b_r = src_r.read(1)
                 b_g = src_g.read(1)
                 
            if b_nir.shape != b_r.shape:
                 b_nir = cv2.resize(b_nir, (b_r.shape[1], b_r.shape[0]), interpolation=cv2.INTER_LINEAR)
                 
            h, w = b_r.shape
            img_bgr = np.zeros((h, w, 3), dtype=np.uint8)
            img_bgr[:,:,0] = stretch_percentile(b_g)
            img_bgr[:,:,1] = stretch_percentile(b_r)
            img_bgr[:,:,2] = stretch_percentile(b_nir)

            # 獲取 JSON 原始大小以計算縮放 (例如從 60m 的參考作出的 JSON，套在 10m 圖上需要放大點位)
            with open(json_file, 'r', encoding='utf-8') as f:
                jdata = json.load(f)
            
            orig_w = jdata.get('imageWidth', w)
            orig_h = jdata.get('imageHeight', h)
            scale_x = w / float(orig_w) if float(orig_w) > 0 else 1.0
            scale_y = h / float(orig_h) if float(orig_h) > 0 else 1.0
            
            if LABELME_READY_MODE:
                # ====== LABELME 模式: 輸出乾淨的影像與更新過的 JSON ======
                out_png_path = os.path.join(OUT_DIR, out_png_name)
                out_json_path = os.path.join(OUT_DIR, out_json_name)
                
                # 修正點位座標
                if scale_x != 1.0 or scale_y != 1.0:
                    for shape in jdata.get('shapes', []):
                        new_points = []
                        for pt in shape.get('points', []):
                            new_points.append([pt[0] * scale_x, pt[1] * scale_y])
                        shape['points'] = new_points
                
                # 重寫必要的 LabelMe 格式參數
                jdata['imagePath'] = out_png_name
                jdata['imageData'] = None
                jdata['imageWidth'] = w
                jdata['imageHeight'] = h
                
                cv2.imwrite(out_png_path, img_bgr)
                with open(out_json_path, 'w', encoding='utf-8') as f:
                    json.dump(jdata, f, indent=2, ensure_ascii=False)
                    
            else:
                # ====== 傳統模式: 帶框線的輸出 (給視覺觀看而不是二次編輯) ======
                if OVERLAP:
                    oil_labels = ['oil_spill', 'oil spill', '0', 'oil', 'Oil']
                    for shape in jdata.get('shapes', []):
                        label = shape.get('label', '')
                        pts = np.array(shape.get('points', []), dtype=np.float32)
                        if len(pts) < 3: 
                            continue
                            
                        # 同樣要做座標縮放還原
                        pts[:, 0] *= scale_x
                        pts[:, 1] *= scale_y
                        
                        pts = pts.astype(np.int32).reshape((-1, 1, 2))
                        if label in oil_labels:
                            color = (0, 255, 255) # Yellow
                        else:
                            color = (0, 255, 0)   # Green
                            
                        cv2.polylines(img_bgr, [pts], isClosed=True, color=color, thickness=1)
                
                out_png_path = os.path.join(OUT_DIR, out_png_name)
                cv2.imwrite(out_png_path, img_bgr)
            
        except Exception as e:
            print(f"  [出錯] {scene_name} 發生錯誤: {e}")

if __name__ == "__main__":
    main()
