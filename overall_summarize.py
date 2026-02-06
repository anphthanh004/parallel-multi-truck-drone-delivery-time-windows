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

    # Danh sách các tên cột có thể có cho thời gian chạy (để tránh bị trống)
    time_colnames = ['excution_time', 'execution_time', 'Avg Execution Time']

    for file_name in os.listdir(input_dir):
        if file_name.endswith(".csv"):
            file_path = os.path.join(input_dir, file_name)
            instance_name = file_name.replace(".csv", "")
            
            try:
                df = pd.read_csv(file_path)
                avg_row = df[df['source'] == 'AVERAGE']
                
                if not avg_row.empty:
                    # Tìm cột thời gian chạy hiện có trong file
                    found_time_col = None
                    for col in time_colnames:
                        if col in avg_row.columns:
                            found_time_col = col
                            break
                    
                    # Lấy giá trị thời gian, nếu không thấy thì để 0.0
                    time_val = avg_row[found_time_col].values[0] if found_time_col else 0.0
                    
                    summary_row = {
                        "Instance": instance_name,
                        "Pareto Count": int(round(avg_row['pareto_count'].values[0])),
                        "Served": int(round(avg_row['served'].values[0])),
                        "Makespan": round(avg_row['makespan'].values[0], 4),
                        "Avg Execution Time": round(time_val, 4)
                    }
                    all_summaries.append(summary_row)
            except Exception as e:
                print(f"Lỗi khi xử lý file {file_name}: {e}")

    if not all_summaries:
        print("Không có dữ liệu để tổng hợp.")
        return

    # Tạo DataFrame
    overall_df = pd.DataFrame(all_summaries)

    # Sắp xếp theo số tự nhiên (6.10.1 sẽ đứng trước 100.40.4)
    overall_df['sort_key'] = overall_df['Instance'].apply(natural_sort_key)
    overall_df = overall_df.sort_values(by='sort_key').drop(columns=['sort_key'])

    # Lưu và in kết quả
    overall_df.to_csv("overall_summary.csv", index=False, encoding='utf-8-sig')
    
    print("\nBẢNG TỔNG HỢP KẾT QUẢ TỐT NHẤT (SẮP XẾP THEO INSTANCE):")
    print("=" * 90)
    # Định dạng hiển thị số thập phân cho đẹp
    pd.options.display.float_format = '{:.4f}'.format
    print(overall_df.to_string(index=False))
    print("=" * 90)

if __name__ == "__main__":
    create_overall_summary()