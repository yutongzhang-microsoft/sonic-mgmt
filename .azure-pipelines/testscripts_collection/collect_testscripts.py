import sys
import os
import re
import logging
import subprocess
from natsort import natsorted

def collect_all_scripts():
    '''
    This function collects all test scripts under the folder 'tests/'
    '''
    location = sys.argv[1]

    # Recursively find all files starting with "test_" and ending with ".py"
    # Note: The full path and name of files are stored in a list named "files"
    scripts = []
    for root, dirs, script in os.walk(location):
        for s in script:
            if s.startswith("test_") and s.endswith(".py"):
                scripts.append(os.path.join(root, s))
    scripts = natsorted(scripts)

    # Open each file and search for regex pattern
    pattern = re.compile(r"[^@]pytest\.mark\.topology\(([^\)]*)\)")
    test_cases = []

    for s in scripts:
        # Remove prefix from file name:
        script_name = s[len(location) + 1:]
        try:
            with open(s, 'r') as script:
                # Get topology type of script from mark `pytest.mark.topology`
                match = pattern.search(script.read())
                if match:
                    topology = match.group(1)
                else:
                    topology = None


                command = [
                    "python3", "-m", "pytest", f"{s}",
                    "--inventory", "../ansible/veos_vtb", "--host-pattern", "all",
                    "--testbed_file", "../ansible/vtestbed.yaml", "--testbed", "vms-kvm-t0",
                    "--ignore", "saitests", "--ignore", "ptftests", "--ignore", "acstests",
                    "--ignore", "scripts", "--ignore", "sai_qualify", "--ignore", "common",
                    "--ignore-conditional-mark", "--color=no", "--collect-only",
                    "--continue-on-collection-errors", "--disable-warnings", "--capture=no", "-q"
                ]
                result = subprocess.run(command, capture_output=True, text=True)

                output = result.stdout
                test_case_lines = re.findall(r'tests/(.*)', output)

                for test_case in test_case_lines:
                    result = {
                        "testcase": test_case,
                        "topology": topology
                    }
                    test_cases.append(result)

        except Exception as e:
            logging.error('Failed to load script {}, error {}'.format(s, e))
    print(test_cases)
    return test_cases

collect_all_scripts()
