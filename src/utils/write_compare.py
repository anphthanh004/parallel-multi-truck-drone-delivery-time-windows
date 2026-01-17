import os
import json
import pandas as pd
import argparse


def main(output_name):
    reference_path = '../../results/reference_solution.json'
    with open(reference_path, 'r') as f:
        reference = json.load(f)

    without_time_slot_dir = '../../results/without_time_slot'

    data = []
    for instance in os.listdir(without_time_slot_dir):
        instance_path = os.path.join(without_time_slot_dir, instance)
        if os.path.isdir(instance_path):
            best_indi_path = os.path.join(instance_path, 'best_indi.json')
            if os.path.exists(best_indi_path):
                with open(best_indi_path, 'r') as f:
                    best_indi = json.load(f)
                if instance in reference:
                    ref_data = reference[instance]
                    row = {
                        'instance': instance,
                        'total_request': ref_data['total'],
                        'my_served': best_indi['served'],
                        'my_dropped': best_indi['dropped'],
                        'my_makespan': f"{best_indi['makespan']:.3f}",
                        'served_benchmark': ref_data['served_benchmark'],
                        'dropped_benchmark': ref_data['dropped_benchmark'],
                        'makespan_benchmark': f"{ref_data['makespan_benchmark']:.3f}"
                    }
                    data.append(row)

    df = pd.DataFrame(data)
    df = df.sort_values(by='instance')

    output_dir = '../../compares'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_name)
    df.to_csv(output_path, index=False)

    print(f'Saved comparison to {output_path}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Write csv file")
    parser.add_argument('-o', '--output', type=str, default='without_time_slot')
    args = parser.parse_args()
    main(args.output)