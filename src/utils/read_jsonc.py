import os
import json
from typing import List, Tuple, Dict

def _load_jsonc(filepath: str) -> List[Dict]:
    """
    Load file *.json.result.jsonc dạng:
    { ... }
    { ... }
    { ... }

    Có comment // và không bọc trong []
    """
    objects = []
    buffer = ""

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # bỏ comment và dòng rỗng
            if not line or line.startswith("//"):
                continue
            if "//" in line:
                line = line.split("//", 1)[0].rstrip()

            buffer += line

            try:
                obj = json.loads(buffer)
                objects.append(obj)
                buffer = ""
            except json.JSONDecodeError:
                # chưa đủ dữ liệu để tạo 1 object
                continue

    return objects

def read_reference_solution() -> Dict[str, Dict[str, object]]:
    results = {}
    reference_dir = "../../reference_solution/WithTimeWindows"

    for filename in os.listdir(reference_dir):
        if not filename.endswith(".json.result.jsonc"):
            continue

        problem_id = filename.replace(".json.result.jsonc", "")
        filepath = os.path.join(reference_dir, filename)

        data = _load_jsonc(filepath)

        dropped_set = set()
        result_value = None
        found_last_route = False

        for entry in reversed(data):
            if not isinstance(entry, dict):
                continue

            if entry.get("__") == "LASTROUTE":
                dropped = entry.get("dropped", [])
                if isinstance(dropped, list):
                    dropped_set.update(dropped)
                found_last_route = True
                continue

            if found_last_route and "result" in entry:
                result_value = entry["result"]
                break

        results[problem_id] = {
            "result": result_value,
            "num_dropped": len(dropped_set),
            "dropped": sorted(dropped_set)
        }

    return results

def version_key(s: str):
    return tuple(map(int, s.split(".")))

def write_benchmark_json(
    benchmark_data: dict,
    output_path: str = "../../results3/benchmark.json",
):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # with open(output_path, "w", encoding="utf-8") as f:
    #     json.dump(benchmark_data, f, indent=2, ensure_ascii=False)
    # sort theo version number
    sorted_data = dict(
        sorted(benchmark_data.items(), key=lambda x: version_key(x[0]))
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=2, ensure_ascii=False)



if __name__ == "__main__":
    result = read_reference_solution()
    print(result)
    print(len(result))
    write_benchmark_json(result)
    print("benchmark.json written to results !")
    
# python read_jsonc.py