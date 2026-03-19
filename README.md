# Oil-dataset-preprocess
從原始資料拿下來需要經過大氣矯正，到可以用的形式
# 1. run_acolite.py -> 去跑acolite的程式
# 2. organize_and_clean_s2.py  -> 刪除不必要的程式，並且轉換成10/15/20/60mm
# 3. batch_convert_shapefiles_2.py -> 從原始檔案裡面到標記檔並輸出JSON
# 4. export_NIR_overlap_fixed.py -> 將11波段輸出成3波段並且可以調整是否要標記
