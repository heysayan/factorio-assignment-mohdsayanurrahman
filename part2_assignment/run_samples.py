# part2_assignment/run_samples.py

import sys
import os
import json
import subprocess
from glob import glob

def run_test(command, input_file):
    """Runs a single test case and compares its output to the expected output."""
    
    expected_output_file = input_file.replace(".in.json", ".out.json")
    if not os.path.exists(expected_output_file):
        print(f"🟡 SKIP: No matching output file for {os.path.basename(input_file)}")
        return "skip", 0

    with open(input_file, 'r') as f_in, open(expected_output_file, 'r') as f_out:
        input_data = f_in.read()
        try:
            expected_output = json.load(f_out)
        except json.JSONDecodeError:
            print(f"🔴 FAIL: Invalid JSON in {os.path.basename(expected_output_file)}")
            return "fail", 1

    try:
        process = subprocess.Popen(
            command.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input_data, timeout=5) # 5s timeout

        if process.returncode != 0:
            print(f"🔴 FAIL: {os.path.basename(input_file)}")
            print(f"   - Process exited with code {process.returncode}")
            print(f"   - Stderr: {stderr.strip()}")
            return "fail", 1

        try:
            actual_output = json.loads(stdout)
        except json.JSONDecodeError:
            print(f"🔴 FAIL: {os.path.basename(input_file)}")
            print(f"   - Program produced invalid JSON output.")
            print(f"   - Output: {stdout}")
            return "fail", 1

        # Compare loaded JSON objects. This handles key order and formatting differences.
        if actual_output == expected_output:
            print(f"🟢 PASS: {os.path.basename(input_file)}")
            return "pass", 0
        else:
            print(f"🔴 FAIL: {os.path.basename(input_file)}")
            print("   - Expected:", json.dumps(expected_output))
            print("   - Actual:  ", json.dumps(actual_output))
            return "fail", 1

    except subprocess.TimeoutExpired:
        print(f"🔴 FAIL: {os.path.basename(input_file)} (Timeout > 5s)")
        process.kill()
        return "fail", 1
    except Exception as e:
        print(f"🔴 FAIL: {os.path.basename(input_file)} (Crashed)")
        print(f"   - Error: {e}")
        return "fail", 1


def main():
    if len(sys.argv) != 3:
        print("Usage: python run_samples.py \"<factory_cmd>\" \"<belts_cmd>\"")
        sys.exit(1)

    factory_cmd = sys.argv[1]
    belts_cmd = sys.argv[2]
    
    factory_inputs = sorted(glob("samples/factory_*.in.json"))
    belts_inputs = sorted(glob("samples/belts_*.in.json"))

    total_failed = 0
    
    print("-" * 20)
    print(f"Running Factory Tests ({factory_cmd})")
    print("-" * 20)
    if not factory_inputs:
        print("No factory samples found in samples/")
    for f in factory_inputs:
        _, failed_count = run_test(factory_cmd, f)
        total_failed += failed_count

    print("\n" + "-" * 20)
    print(f"Running Belts Tests ({belts_cmd})")
    print("-" * 20)
    if not belts_inputs:
        print("No belts samples found in samples/")
    for f in belts_inputs:
        _, failed_count = run_test(belts_cmd, f)
        total_failed += failed_count
        
    print("\n" + "=" * 20)
    if total_failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"🔥 {total_failed} test(s) failed.")
    print("=" * 20)
    
    sys.exit(total_failed)


if __name__ == "__main__":
    main()