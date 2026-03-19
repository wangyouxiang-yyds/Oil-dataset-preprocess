# python organize_and_clean_s2.py
import os
import shutil
import re

# 定義波段範圍與解析度 (Band Center, Tolerance +/- 15nm usually covers S2A/S2B variations)
# 格式: (解析度, 最小波長, 最大波長)
# 參考 Sentinel-2 波段中心: https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/resolutions/radiometric
BAND_RANGES = [
    # --- 10m Bands ---
    ('10m', 460, 520),   # B2 (Blue): ~490-496
    ('10m', 530, 590),   # B3 (Green): ~560
    ('10m', 630, 690),   # B4 (Red): ~665
    ('10m', 800, 850),   # B8 (NIR): ~835-842
    
    # --- 20m Bands ---
    ('20m', 690, 720),   # B5 (Red Edge 1): ~705
    ('20m', 730, 760),   # B6 (Red Edge 2): ~740
    ('20m', 760, 800),   # B7 (Red Edge 3): ~783
    ('20m', 850, 890),   # B8A (Narrow NIR): ~865
    ('20m', 1550, 1680), # B11 (SWIR 1): ~1610
    ('20m', 2000, 2300), # B12 (SWIR 2): ~2190
    
    # --- 60m Bands ---
    ('60m', 400, 460),   # B1 (Coastal): ~443
    ('60m', 900, 980),   # B9 (Water Vapour): ~945
    ('60m', 1300, 1450)  # B10 (Cirrus): ~1375
]

def get_resolution(filename):
    # Regex to find the wavelength number after 'rhorc_'
    # Matches patterns like ...rhorc_443.tif or ...rhorc_443_clean.tif
    match = re.search(r'rhorc_(\d+)', filename)
    if match:
        try:
            wavelength = int(match.group(1))
            
            # 使用範圍判斷
            for res, min_w, max_w in BAND_RANGES:
                if min_w <= wavelength <= max_w:
                    return res
            
            # 如果找不到範圍，印出警告以便除錯
            print(f"  [Warning] Wavelength {wavelength} not in any known range.")
        except ValueError:
            pass
            
    return 'Unknown_Resolution'

def process_event_folder(folder_path):
    print(f"Processing folder: {folder_path}")
    
    # === Rescue Step: Deep Recursion Scan ===
    # Check for Unknown_Resolution recursively regardless of nesting depth
    unknown_res_path = os.path.join(folder_path, 'Unknown_Resolution')
    
    if os.path.exists(unknown_res_path) and os.path.isdir(unknown_res_path):
        print(f"  [Rescue] Found Unknown_Resolution, exploring recursively...")
        
        # Walk through the unknown folder top-down
        for root, dirs, files in os.walk(unknown_res_path):
            for f in files:
                if 'rhorc' in f and f.endswith('.tif'):
                    src = os.path.join(root, f)
                    dst = os.path.join(folder_path, f)
                    
                    if not os.path.exists(dst):
                        try:
                            # print(f"  [Rescue] Moving {f} back to root.") 
                            shutil.move(src, dst)
                        except Exception as e:
                            print(f"  ! Error rescuing {f}: {e}")
        
        # After moving valid files out, nuke the folder
        try:
            print(f"  [Rescue] Deleteing {unknown_res_path}")
            shutil.rmtree(unknown_res_path)
        except Exception as e:
            print(f"  ! Warning: Could not delete Unknown_Resolution: {e}")
            
    # =======================================================
    
    # 1. Identify files to Keep vs Delete
    # ----------------------------------
    all_items = os.listdir(folder_path)
    
    # Lists to handle
    tifs_to_move = []
    items_to_delete = []
    
    # Pre-scan to ensure this is an ACOLITE folder with data
    # (If no rhorc data is found, we might skip to be safe, or user might want to clean partial runs)
    has_rhorc = any('rhorc' in name and name.endswith('.tif') for name in all_items)
    
    if not has_rhorc:
        print(f"  [Skip] No 'rhorc' tif files found in {os.path.basename(folder_path)}. Skipping cleanup to be safe.")
        return

    for item_name in all_items:
        item_path = os.path.join(folder_path, item_name)
        
        # SKIP our output folders if they already exist from a previous run
        if item_name in ['10m', '20m', '60m', 'Unknown_Resolution']:
            continue
            
        # KEEP PNGs (stay in root of event folder)
        if item_name.lower().endswith('.png') and os.path.isfile(item_path):
            print(f"  [Keep PNG] {item_name}")
            continue
            
        # KEEP & MOVE rhorc TIFs
        if 'rhorc' in item_name and item_name.lower().endswith('.tif') and os.path.isfile(item_path):
            tifs_to_move.append(item_name)
            continue
            
        # MARK FOR DELETION (Everything else: .SAFE, .nc, .txt, other .tifs like sza, etc.)
        items_to_delete.append(item_path)

    # 2. Execute Deletion
    # -------------------
    for path in items_to_delete:
        try:
            if os.path.isdir(path):
                print(f"  [Deleting Dir] {os.path.basename(path)}")
                shutil.rmtree(path)
            else:
                print(f"  [Deleting File] {os.path.basename(path)}")
                os.remove(path)
        except Exception as e:
            print(f"  ! Error deleting {os.path.basename(path)}: {e}")

    # 3. Sort and Move TIFs
    # ---------------------
    for filename in tifs_to_move:
        res_folder_name = get_resolution(filename)
        
        # ...existing code...
        if not res_folder_name or res_folder_name == 'Unknown_Resolution': # Modified check
            print(f"  [Warning] Could not determine resolution for {filename}. Moving to 'Unknown_Resolution'")
            res_folder_name = 'Unknown_Resolution'
            
        target_dir = os.path.join(folder_path, res_folder_name)
        
        # Create 10m/20m/60m folder if needed
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        src_path = os.path.join(folder_path, filename)
        dst_path = os.path.join(target_dir, filename)
        
        try:
            print(f"  [Moving] {filename} -> {res_folder_name}/")
            shutil.move(src_path, dst_path)
        except Exception as e:
            print(f"  ! Error moving {filename}: {e}")

def main():
    root_dir = r"/home/sun/oil_dataset/new_small_output"
    
    if not os.path.exists(root_dir):
        print(f"Root path not found: {root_dir}")
        return

    # ...existing code...
    target_folders = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Heuristic: If a folder contains 'rhorc' .tif files, it's an event folder.
        # We also want to avoid processing the '10m'/'20m' folders we just created if we re-run.
        if os.path.basename(dirpath) in ['10m', '20m', '60m', 'Unknown_Resolution']: # Added Unknown check
            continue
        
        # 新增：避開已知的大分類資料夾名稱
        if "NOAA_" in os.path.basename(dirpath): 
             continue

        # Check 1: Are there rhorc files directly in this folder?
        has_rhorc_files = any('rhorc' in f and f.endswith('.tif') for f in filenames)

        # Check 2: Is there an Unknown_Resolution folder that might contain hidden files?
        has_unknown_folder = 'Unknown_Resolution' in dirnames
        
        if has_rhorc_files or has_unknown_folder:
            target_folders.append(dirpath)
            
    print(f"Found {len(target_folders)} folders to process.")
    
    for folder in target_folders:
        process_event_folder(folder)

if __name__ == "__main__":
    main()