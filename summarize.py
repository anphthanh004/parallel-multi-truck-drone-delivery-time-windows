# import os
# import json
# import pandas as pd
# import glob

# def summarize_results():
#     # Danh sách các folder results (bỏ qua result2 vì chưa làm)
#     results_folders = [f"results{i}" for i in [1, 3, 4, 5, 6, 7, 8, 9, 10]]
    
#     # Từ điển để gom nhóm các folder con (VD: '6.10.1': [data từ result1, result3...])
#     summary_data = {}

#     for res_folder in results_folders:
#         if not os.path.exists(res_folder):
#             continue
            
#         # Lấy tất cả các folder con bên trong results*
#         subfolders = [f for f in os.listdir(res_folder) if os.path.isdir(os.path.join(res_folder, f))]
        
#         for sub in subfolders:
#             file_path = os.path.join(res_folder, sub, "best_indi.json")
            
#             if os.path.exists(file_path):
#                 try:
#                     with open(file_path, 'r') as f:
#                         data = json.load(f)
                    
#                     # Trích xuất các thông tin cần thiết
#                     row = {
#                         "source": res_folder,
#                         "served": data.get("served"),
#                         "makespan": data.get("makespan"),
#                         "execution_time": data.get("execution_time") # Sửa lại đúng chính tả nếu file json của bạn là 'excution_time'
#                     }
                    
#                     if sub not in summary_data:
#                         summary_data[sub] = []
#                     summary_data[sub].append(row)
#                 except Exception as e:
#                     print(f"Lỗi khi đọc file {file_path}: {e}")

#     # Xuất ra file CSV cho từng folder con
#     if not os.path.exists("summary_csv"):
#         os.makedirs("summary_csv")

#     for sub_name, rows in summary_data.items():
#         df = pd.DataFrame(rows)
        
#         # Tính trung bình (chỉ tính trên các cột số)
#         avg_row = df.select_dtypes(include=['number']).mean()
#         avg_df = pd.DataFrame([avg_row])
#         avg_df['source'] = 'AVERAGE'
        
#         # Nối dòng trung bình vào cuối
#         df = pd.concat([df, avg_df], ignore_index=True)
        
#         # Lưu file CSV
#         output_file = f"summary_csv/{sub_name}.csv"
#         df.to_csv(output_file, index=False)
#         print(f"Đã tạo file: {output_file}")

# if __name__ == "__main__":
#     summarize_results()

import os
import json
import pandas as pd

def summarize_results():
    # Danh sách các folder results (bỏ qua result2)
    results_folders = [f"results{i}" for i in [1, 3, 4, 5, 6, 7, 8, 9, 10]]
    
    # Dictionary để gom nhóm: { 'tên_folder_con': [danh_sách_data] }
    summary_data = {}

    for res_folder in results_folders:
        if not os.path.exists(res_folder):
            continue
            
        # Lấy các folder con (VD: 6.10.1, 100.40.4)
        subfolders = [f for f in os.listdir(res_folder) if os.path.isdir(os.path.join(res_folder, f))]
        
        for sub in subfolders:
            best_indi_path = os.path.join(res_folder, sub, "best_indi.json")
            population_path = os.path.join(res_folder, sub, "population.json")
            
            # Kiểm tra sự tồn tại của file chính best_indi.json
            if os.path.exists(best_indi_path):
                try:
                    # 1. Đọc file best_indi.json
                    with open(best_indi_path, 'r', encoding='utf-8') as f:
                        best_data = json.load(f)
                    
                    # 2. Đọc file population.json để lấy pareto_count
                    p_count = 0
                    if os.path.exists(population_path):
                        with open(population_path, 'r', encoding='utf-8') as f:
                            pop_data = json.load(f)
                            # Lấy pareto_count từ population.json
                            p_count = pop_data.get("pareto_count", 0)
                    
                    # Trích xuất dữ liệu tổng hợp
                    row = {
                        "source": res_folder,
                        "pareto_count": p_count,
                        "served": best_data.get("served"),
                        "makespan": best_data.get("makespan"),
                        "execution_time": best_data.get("execution_time")
                    }
                    
                    if sub not in summary_data:
                        summary_data[sub] = []
                    summary_data[sub].append(row)
                except Exception as e:
                    print(f"Lỗi khi xử lý folder {os.path.join(res_folder, sub)}: {e}")

    # Tạo folder chứa kết quả CSV
    output_dir = "summary_csv"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for sub_name, rows in summary_data.items():
        df = pd.DataFrame(rows)
        
        # Sắp xếp thứ tự cột
        cols = ["source", "pareto_count", "served", "makespan", "execution_time"]
        df = df[cols]
        
        # Tính trung bình cho các cột số (pareto_count, served, makespan, execution_time)
        numeric_cols = ["pareto_count", "served", "makespan", "execution_time"]
        avg_row = df[numeric_cols].mean()
        
        # Tạo dòng trung bình
        avg_df = pd.DataFrame([avg_row])
        avg_df['source'] = 'AVERAGE'
        
        # Nối dòng trung bình vào cuối
        df = pd.concat([df, avg_df], ignore_index=True)
        
        # Lưu file CSV
        output_file = os.path.join(output_dir, f"{sub_name}.csv")
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"Đã xuất file: {output_file}")

if __name__ == "__main__":
    summarize_results()