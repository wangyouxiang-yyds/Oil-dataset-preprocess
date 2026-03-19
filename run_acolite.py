# python run_acolite.py
import os
import sys
import glob
import time

# ================= 路徑設定 =================

# 1. ACOLITE 原始碼路徑
acolite_dir = r"/home/sun/oil_dataset/acolite-main"

# 2. 您的資料總根目錄
root_input_dir = r"/home/sun/oil_dataset/new_small"

# 3. 輸出總目錄
root_output_dir = r"/home/sun/oil_dataset/new_small_output"

# ===========================================

sys.path.append(acolite_dir)

try:
    import acolite as ac
except ImportError as e:
    print(f"錯誤：無法匯入 acolite 模組。詳細錯誤: {e}")
    # print sys.path to be sure
    print(f"sys.path: {sys.path}")
    sys.exit()

print(f"開始搜尋 {root_input_dir} 下的所有 L1C ZIP 檔...\n")

success_count = 0
failed_files = {}  # 用於記錄失敗的檔案和原因

count = 0
for current_root, dirs, files in os.walk(root_input_dir):
    for filename in files:
        if filename.endswith(".zip") and "MSIL1C" in filename:
            
            zip_path = os.path.join(current_root, filename)
            rel_path = os.path.relpath(current_root, root_input_dir)
            current_output_dir = os.path.normpath(os.path.join(root_output_dir, rel_path))
            
            if not os.path.exists(current_output_dir):
                os.makedirs(current_output_dir)
            
            # === 檢查 ZIP 檔案大小 ===
            # 因為已證明有壞檔只有 72MB，而正常檔約 300MB，我們設定 100MB 為閾值
            file_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            if file_size_mb < 10:
                print(f"[{count+1}] [跳過] 檔案過小 (可能損毀, {file_size_mb:.2f} MB): {filename}")
                failed_files[filename] = f"File too small ({file_size_mb:.2f} MB)"
                count += 1
                continue

            # === 跳過已完成檢查 ===
            existing_tifs = glob.glob(os.path.join(current_output_dir, "*rhorc*.tif"))
            if len(existing_tifs) > 5:
                print(f"[{count+1}] [跳過] 檔案已存在: {filename}")
                count += 1
                continue

            print(f"[{count+1}] 正在處理: {filename}")
            print(f"      輸出: {current_output_dir}")

            # --- ACOLITE 設定 (修正版) ---
            settings = {
                'inputfile': zip_path,
                'output': current_output_dir,
                
                # 【關鍵修正 1】只計算 rhorc，並使用 DSF
                'output_rhorc': True,
                'aerosol_correction': 'dark_spectrum',
                
                # 【關鍵修正 2】嚴格限制 L2R 輸出的波段 (只留 rhorc)
                # 這會覆蓋預設設定，理論上 ACOLITE 就只會寫入這些波段到 NetCDF 和 TIFF
                'l2r_parameters': 'rhorc_443,rhorc_492,rhorc_560,rhorc_665,rhorc_704,rhorc_833,rhorc_865,rhorc_1614',
                
                # 【關鍵修正 3】輸出開關控制
                'l1r_export_geotiff': False,       # 關閉 rhot 的 TIF 輸出 (您只要 rhorc TIF)
                'l2r_export_geotiff': True,        # 開啟 L2R TIF 輸出 (這裡面包含 rhorc)
                'l2w_export_geotiff_run': False,
                
                # 【恢復】RGB 預覽圖 (生成 PNG 檔供預覽，不會影響 TIF 數量)
                'l1r_export_geotiff_rgb': True,
                'l2r_export_geotiff_rgb': True,
                
                # 遮罩設定
                'l2w_mask': True,
                'l2w_mask_threshold': 0.06
            }

            try:
                start_time = time.time()
                ac.acolite.acolite_run(settings=settings)
                end_time = time.time()
                elapsed_time = end_time - start_time
                print(f"      -> 完成。")
                print(f"      處理時間: {elapsed_time:.2f} 秒")
                success_count += 1

                # === 自動清理 .nc 檔 ===
                files_to_delete = glob.glob(os.path.join(current_output_dir, "*.nc"))
                if len(files_to_delete) > 0:
                    for f_path in files_to_delete:
                        try:
                            # 確保只刪除數據檔 (L1R/L2R/L2W)，保留設定檔
                            if any(x in f_path for x in ['L1R', 'L2R', 'L2W']):  
                                os.remove(f_path)
                        except:
                            pass
                    print(f"      [清理] 已刪除暫存 .nc 檔案。")

            except Exception as e:
                print(f"      -> 失敗: {e}")
                failed_files[filename] = str(e)
            

            
            count += 1
            print("-" * 50)

if count == 0:
    print("未找到任何符合條件的檔案。")
else:
    print(f"\n全部處理完畢。")
    print("=" * 50)
    print(f"成功: {success_count} / {count}")
    print(f"失敗: {len(failed_files)} / {count}")
    if len(failed_files) > 0:
        print("\n失敗列表:")
        for fname, reason in failed_files.items():
            print(f" - {fname}: {reason}")
    print("=" * 50)