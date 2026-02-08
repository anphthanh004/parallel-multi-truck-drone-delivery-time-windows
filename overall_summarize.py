import os
import pandas as pd
import re

def natural_sort_key(s):
    """Hàm bổ trợ để sắp xếp tên instance theo thứ tự số tự nhiên (6 < 10)"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def create_overall_summary():
    input_dir = "summary_csv"
    all_summaries = []

    if not os.path.exists(input_dir):
        print(f"Không tìm thấy thư mục {input_dir}")
        return

    for file_name in os.listdir(input_dir):
        if file_name.endswith(".csv"):
            file_path = os.path.join(input_dir, file_name)
            instance_name = file_name.replace(".csv", "")
            
            try:
                df = pd.read_csv(file_path)
                
                # SỬA TẠI ĐÂY: Tìm dòng có cột 'source' chứa chữ 'BEST' 
                # (Vì summarize.py của bạn đặt là "BEST (from resultsX)")
                best_row = df[df['source'].str.contains('BEST', na=False)]
                
                if not best_row.empty:
                    summary_row = {
                        "Instance": instance_name,
                        "Source": best_row['source'].values[0],
                        "Pareto Count": int(round(best_row['pareto_count'].values[0])),
                        "Served": int(round(best_row['served'].values[0])),
                        "Makespan": round(best_row['makespan'].values[0], 4),
                        "Avg Execution Time": round(best_row['execution_time'].values[0], 4)
                    }
                    all_summaries.append(summary_row)
            except Exception as e:
                print(f"Lỗi khi xử lý file {file_name}: {e}")

    if not all_summaries:
        print("Không có dữ liệu để tổng hợp. Kiểm tra lại các file trong summary_csv có dòng 'BEST' không.")
        return

    overall_df = pd.DataFrame(all_summaries)

    # Sắp xếp theo tên Instance (tự nhiên)
    overall_df['sort_key'] = overall_df['Instance'].apply(natural_sort_key)
    overall_df = overall_df.sort_values(by='sort_key').drop(columns=['sort_key'])

    # Lưu file tổng hợp cuối cùng
    overall_df.to_csv("overall_summary.csv", index=False, encoding='utf-8-sig')
    
    print("\nBẢNG TỔNG HỢP KẾT QUẢ TỐT NHẤT (SẮP XẾP THEO INSTANCE):")
    print("=" * 110)
    pd.options.display.float_format = '{:.4f}'.format
    # Hiển thị bảng ra màn hình
    print(overall_df.to_string(index=False))
    print("=" * 110)

if __name__ == "__main__":
    create_overall_summary()