import os
import sys

import numpy as np

script_dir = os.path.dirname(__file__)
parent_dir = os.path.join(script_dir, "..")
local_dir = os.path.join(script_dir, "..", "rerun_test_build_scripts")
sys.path.append(parent_dir)
sys.path.append(local_dir)



class Test:
    def __init__(self, name, outcome, duration):
        self.name = name
        self.outcome = outcome
        self.duration = duration


def add_TF(TFis, pos, mapping):
    if mapping == "sameBug":
        if len(TFis["Bug"]) == 0:
            TFis["Bug"].append(pos)
    elif mapping == "uniqueBug":
        TFis["Bug"].append(pos)
    elif mapping == "sameFix":
        if len(TFis["Fix"]) == 0:
            TFis["Fix"].append(pos)
    elif mapping == "uniqueFix":
        TFis["Fix"].append(pos)
    return TFis

def convert_TFis_to_list(TFis):
    ret = []
    for k, v in TFis.items():
        ret += v
    return ret


def has_fail_tests(tests):
    failed = [1 for t in tests if t.outcome == "failed"]
    if len(failed) > 0:
        return True
    return False


class FaultDetectionMetric:
    def __init__(self, tests, bug_mapping, ts_duration, num_fail_tests):
        self.tests = tests
        self.num_tests = len(tests)
        self.ts_duration = ts_duration
        self.num_fail_tests = num_fail_tests
        self.num_bugs = self.count_num_bugs(bug_mapping)
        self.TFis = self.get_TFis(bug_mapping)

    def count_num_bugs(self, bug_mapping):
        if bug_mapping == "uniqueBug":
            num_bugs = self.num_fail_tests
        else:
            num_bugs = 1
        return num_bugs

    def get_TFis(self, bug_mapping):
        TFis = {"Bug": [], "Fix": []}
        for pos, test in enumerate(self.tests):
            if test.outcome == "failed":
                TFis = add_TF(TFis, pos + 1, bug_mapping)
        TFis = convert_TFis_to_list(TFis)
        return TFis

    def APFD(self):
        # for test suite that dont have failed tests, return nan
        if self.num_fail_tests <= 0:
            return np.nan

        ret = sum(self.TFis) / (self.num_bugs * self.num_tests)
        ret = 1 - ret + (1 / (2 * self.num_tests))
        return ret

    def APFDc(self):
        # for test suite that dont have failed bugs, return nan
        if self.num_fail_tests <= 0:
            return np.nan

        # compute cost for each detected transition
        TF_costs = []
        for pos in self.TFis:
            TF_costs.append(sum(self.ts_duration[pos - 1:]) - (self.ts_duration[pos - 1] / 2))

        worst_case_cost = self.num_bugs * sum(self.ts_duration)
        return sum(TF_costs) / worst_case_cost



def compute_metrics(tests, filtered_failed_tests=set()):
    values = {}

    # compute APFD(c)
    bug_mappings = ["sameBug", "uniqueBug"]
    tests_for_fail = [t for t in tests if t.name not in filtered_failed_tests]
    ts_duration, num_fail_tests = [], 0
    for t in tests_for_fail:
        ts_duration.append(t.duration)
        if t.outcome == "failed":
            num_fail_tests += 1
    for bug_mapping in bug_mappings:
        fault_metric = FaultDetectionMetric(
            tests=tests_for_fail, bug_mapping=bug_mapping,
            ts_duration=ts_duration, num_fail_tests=num_fail_tests)
        values[f"APFDc_{bug_mapping}"] = fault_metric.APFDc()
    return values
