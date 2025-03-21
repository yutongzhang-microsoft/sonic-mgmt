import sys
import os
import re
import ast
import logging
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
                tree = ast.parse(script.read(), filename=s)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                                test_cases.append(f"{script_name}::{node.name}::{item.name}")
                    elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        test_cases.append(f"{script_name}::{node.name}")
                # Get topology type of script from mark `pytest.mark.topology`
                # match = pattern.search(script.read())
                # if match:
                #     result = {
                #         "testscript": script_name,
                #         "topology": match.group(1)
                #     }
                #     test_scripts.append(result)
        except Exception as e:
            logging.error('Failed to load script {}, error {}'.format(s, e))
    print(test_cases)
    return test_cases



collect_all_scripts()