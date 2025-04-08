import ast
import collections
import os
import sys
import zipfile

import numpy as np
import pandas as pd

script_dir = os.path.dirname(__file__)
parent_dir = os.path.join(script_dir, "..", "")
local_dir = os.path.join(script_dir, "..", "eval_global_run_dataset")
sys.path.append(parent_dir)
sys.path.append(local_dir)

import local_const
import metrics

TEST_RESULT_DIR = "parsed_rerun_results"
RAW_RERUN_DIR = "../rerun_results"


def get_num_failures_by_type(type_fail_tests: set, failset: list[set]):
    num_failures = 0
    for fails in failset:
        num_failures += len(fails.intersection(type_fail_tests))
    return num_failures


def get_failure_stats_from_reruns():
    df = pd.read_csv(os.path.join(TEST_RESULT_DIR, "rerun_metadata.csv"))
    # Only consider those ran tests.
    df = df[df["total"] > 0]
    failset = []
    failset_by_project = collections.defaultdict(set)
    # Load test result csv to get a set of test failures per run.
    for i, row in df.iterrows():
        project, run_id, order = row["project"], row["run_id"], row["order"]
        csv_file = os.path.join(TEST_RESULT_DIR, project, str(run_id), f"{order}.csv")
        if not os.path.exists(csv_file):
            continue
        csv = pd.read_csv(csv_file)
        fails = set(csv[csv["outcome"]=="failed"]["test"].values.tolist())
        if len(fails) > 0:
            failset.append(fails)
        failset_by_project[project] = failset_by_project[project].union(fails)

    flaky = get_failure_labels("flaky_test_failures.csv")
    real = get_failure_labels("real_test_failures.csv")


    failure_statistics = []
    for project in df["project"].drop_duplicates().values.tolist():
        num_flaky_tests = len(flaky[project])
        num_flaky_failures = get_num_failures_by_type(flaky[project], failset)
        num_real_tests = len(real[project])
        num_real_failures = get_num_failures_by_type(real[project], failset)
        failure_statistics.append(
            [
                project,
                num_flaky_tests,
                num_real_tests,
                num_flaky_failures,
                num_real_failures,
            ]
        )
    failure_statistics = pd.DataFrame(failure_statistics, columns="project,num_flaky_tests,num_real_tests,num_flaky_failures,num_real_failures".split(","))
    failure_statistics.to_csv(os.path.join(TEST_RESULT_DIR, "failure_statistics.csv"), index=False)


def compute_rtp_metrics_helper(df: pd.DataFrame):
    """
    metric1 table
        order1, order2 order3
    proj1
    proj2
    proj3

    metric2 table
    ...
    """
    ffmaps = [
        "sameBug",
        "uniqueBug"
    ]
    tabname = {
        "APFDc_sameBug": "APFDc_many2one.csv",
        "APFDc_uniqueBug": "APFDc_one2one.csv",
    }
    metrics = [f"APFDc_{x}" for x in ffmaps]
    for metric in metrics:
        tab = []
        for project in df["project"].drop_duplicates().values.tolist():
            row = [project]
            for order in local_const.CI_WORKFLOW_NAMES:
                val = df[(df["project"]==project) & (df["order"]==order)][metric].mean()
                row.append(val)
            tab.append(row)
        header = ["project"] + [local_const.CI_WORKFLOW_MACRO[w] for w in local_const.CI_WORKFLOW_NAMES]
        tab = pd.DataFrame(tab, columns=header)
        tab.to_csv(os.path.join(TEST_RESULT_DIR, tabname[metric]), index=False)


def compute_rtp_metrics():
    """compute APFDc per project per technique."""

    # Get labels of real failures
    real_failures_df = pd.read_csv("real_test_failures.csv")
    real_failures = collections.defaultdict(dict)
    for i, row in real_failures_df.iterrows():
        real_failures[row["Project"]][row["Test"]] = parse_run_id_labels(row["ID"])

    # Compute RTP metrics
    df = pd.read_csv(os.path.join(TEST_RESULT_DIR, "rerun_metadata.csv"))
    df["failed"] = pd.to_numeric(df["failed"], errors="coerce").fillna(value=0)
    ret = []
    for i, row in df.iterrows():
        project, run_id, order, failed = row["project"], row["run_id"], row["order"], row["failed"]
        # Only consider failed tests
        if failed > 0:
            folder = os.path.join(TEST_RESULT_DIR, project, str(run_id))
            csv = pd.read_csv(os.path.join(folder, f"{order}.csv"))
            tests = []
            for j, t in csv.iterrows():
                name, outcome, duration = t["test"], t["outcome"], t["duration"]
                if outcome in ["passed", "failed", "xpassed", "xfailed"]:
                    label_outcome = outcome
                    # Consider non-real failures as passing tests.
                    if outcome == "failed":
                        if name not in real_failures[project] or run_id not in real_failures[project][name]:
                            label_outcome = "passed"
                    test = metrics.Test(name, label_outcome, duration)
                    tests.append(test)
            # If there is no real failure, skip this build
            if not any(t.outcome == "failed" for t in tests):
                continue
            evals = metrics.compute_metrics(tests)
            ret_row = evals
            ret_row["project"] = project
            ret_row["run_id"] = run_id
            ret_row["order"] = order
            ret.append(ret_row)

    ret = pd.DataFrame(ret)

    f = df[df['failed'] > 0][['project', 'run_id', 'order']].groupby(['project', 'run_id']).count().reset_index()
    f = f[f['order'] == len(local_const.CI_WORKFLOW_NAMES)][['project', 'run_id']]
    ret1 = pd.merge(ret, f, how="inner", on=["project", "run_id"])
    compute_rtp_metrics_helper(ret1)


def parse_run_id_labels(run_ids):
    if pd.notna(run_ids) and np.nan != run_ids:
        return set([int(i) for i in ast.literal_eval(run_ids)])
    return set()

def get_failure_labels(filename):
    failures_df = pd.read_csv(filename)
    failures = collections.defaultdict(dict)
    for i, row in failures_df.iterrows():
        failures[row["Project"]][row["Test"]] = parse_run_id_labels(row["ID"])
    return failures


def get_failed_test_runs_helper(project, valid_failed_tests):
    """Number of failed runs only consider flaky or real test failures."""
    df = pd.read_csv(os.path.join(TEST_RESULT_DIR, "rerun_metadata.csv"))
    fail_runs = 0
    tmp = df[(df["project"] == project) & (df["failed"] > 0)]
    for i, row in tmp.iterrows():
        folder = os.path.join(TEST_RESULT_DIR, project, str(row["run_id"]))
        csv = pd.read_csv(os.path.join(folder, f"{row['order']}.csv"))
        fails = csv[csv["outcome"] == "failed"]["test"].values.tolist()
        if any(f in valid_failed_tests and row["run_id"] in valid_failed_tests[f] for f in fails):
            fail_runs += 1
    return fail_runs


def get_dataset_statistics():
    """for each project, get
        - total number of ran commits
        - total number of successfully ran commits
        - total number test runs
        - total number of failed test runs
        - total number of failed test runs with regressions
        - average number of tests across builds across orders
        - average duration (in default order)
        - average duration relative difference from other orders to default orders
    """
    df = pd.read_csv(os.path.join(TEST_RESULT_DIR, "rerun_metadata.csv"))
    real = get_failure_labels("real_test_failures.csv")

    data = []
    for project in df["project"].drop_duplicates().values.tolist():
        total_ran_builds = len(df[df["project"] == project]["run_id"].drop_duplicates())
        total_ran_builds_with_test_runs = len(df[(df["project"] == project) & (df["total"] > 0)]["run_id"].drop_duplicates())
        testruns = df[(df["project"] == project) & (df["total"] > 0)][['project', 'run_id', 'order', 'duration', 'total', 'failed']]
        total_test_runs = len(testruns)
        total_failed_test_runs = len(df[(df["project"] == project) & (df["failed"] > 0)])
        total_failed_test_runs_real = get_failed_test_runs_helper(project, real[project])
        run_ids = testruns["run_id"].drop_duplicates().values.tolist()
        mean_tests = []
        mean_duration_default = []
        mean_duration_rel_diff_prec = []
        for run_id in run_ids:
            run_df = testruns[testruns["run_id"] == run_id]
            mean_tests += run_df["total"].values.tolist()
            default_duration = run_df[run_df["order"] == local_const.WF_DEFUALT]["duration"].values.tolist()[0]
            mean_duration_default.append(default_duration)
            non_default_durations = run_df[run_df["order"] != local_const.WF_DEFUALT]["duration"].values.tolist()
            mean_duration_rel_diff_prec.append(np.mean([100 * abs(nondefault - default_duration) / default_duration for nondefault in non_default_durations]))

        data.append(
            [
                project,
                total_ran_builds,
                total_ran_builds_with_test_runs,
                total_test_runs,
                total_failed_test_runs,
                total_failed_test_runs_real,
                np.mean(mean_tests),
                np.mean(mean_duration_default),
                np.mean(mean_duration_rel_diff_prec)
            ]
        )
    final_result = pd.DataFrame(data, columns="project,total_ran_commits,total_ran_commits_succeeded,total_testruns,total_failed_testruns,total_failed_testruns_w_regression,mean_num_tests,mean_duration,mean_duration_abs_rel_diff".split(","))
    final_result.to_csv(os.path.join(TEST_RESULT_DIR, 'dataset_statistics.csv'), index=False)
    pass


def get_plugin_runtime_overhead_helper(zip_folder_path):
    # Specify the phrases to search for
    search_phrases = [
        "test-change similarity compute time (s)",
        "test order compute time (s)",
        "feature collection time (s)"
    ]

    # Read files directly from the zip
    matching_lines = []

    with zipfile.ZipFile(zip_folder_path, 'r') as zip_ref:
        # Iterate through all files in the zip
        for file_name in zip_ref.namelist():
            if "/" in file_name:
                continue
            if file_name.endswith(".txt"):  # Only process text files
                with zip_ref.open(file_name, 'r') as file:
                    for line in file:
                        # Decode line from bytes to string
                        line = line.decode('utf-8').strip()
                        if any(phrase in line for phrase in search_phrases):
                            matching_lines.append((file_name, line))

    overhead = {line.split(": ")[0].split("Z ")[-1]: float(line.split()[-1]) for _, line in matching_lines}
    if len(overhead):
        overhead["total_runtime"] = sum(list(overhead.values()))
        return overhead

# Calculate the total size of files in the zip
def get_zip_size_in_kb(zip_file_path):
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        total_size_bytes = sum(file.file_size for file in zip_ref.infolist())
    total_size_kb = total_size_bytes / 1024  # Convert bytes to KB
    return total_size_kb


def get_plugin_cache_overhead_helper(zip_folder_path):
    # Specify the phrases to search for
    prefix = "Cache Size: "
    suffix = "B)"

    with zipfile.ZipFile(zip_folder_path, 'r') as zip_ref:
        # Iterate through all files in the zip
        for file_name in zip_ref.namelist():
            if "pytest-ranking cache" not in file_name.lower():
                continue
            if file_name.endswith(".txt"):  # Only process text files
                with zip_ref.open(file_name, 'r') as file:
                    for line in file:
                        # Decode line from bytes to string
                        line = line.decode('utf-8').strip()
                        if prefix in line and line.endswith(suffix):
                            cache_size = int(line.split(" ")[-2].replace("(", "")) / 1024
                            return {"total_cache": cache_size}


def get_plugin_runtime_overhead():
    df = pd.read_csv(os.path.join(TEST_RESULT_DIR, "rerun_metadata.csv"))
    overheads = []
    for i, row in df.iterrows():
        run_log_zip = os.path.join(RAW_RERUN_DIR, row["project"], "workflow_runs", str(row["run_id"]), f"run_log_{row['order']}.zip")
        try:
            summary = {
                "project": row["project"], "run_id": row["run_id"], "order": row["order"]
            }
            runtime_overhead = get_plugin_runtime_overhead_helper(run_log_zip)
            cache_overhead = get_plugin_cache_overhead_helper(run_log_zip)
            test_log_zip_size = get_zip_size_in_kb(run_log_zip)
            if runtime_overhead:
                summary.update(runtime_overhead)
            if cache_overhead:
                summary.update(cache_overhead)
            summary["test_log_zip_size"] = test_log_zip_size
            overheads.append(summary)
        except:
            print(run_log_zip)
            pass
    overheads = pd.DataFrame(overheads)
    overheads.to_csv(os.path.join(TEST_RESULT_DIR, 'overhead.csv'), index=False)


def get_plugin_runtime_overhead_statistics():
    overheads = pd.read_csv(os.path.join(TEST_RESULT_DIR, 'overhead.csv'))
    runtime_stats = overheads[["project", "total_runtime"]].groupby(["project"]).mean().reset_index()
    cache_stats = overheads[["project", "total_cache"]].groupby(["project"]).mean().reset_index()
    size_stats = overheads[["project", "test_log_zip_size"]].groupby(["project"]).mean().reset_index()
    merged = pd.merge(runtime_stats, cache_stats, "inner", on=["project"])
    merged = pd.merge(merged, size_stats, "inner", on=["project"])
    merged["prec_cache_to_log_size"] = merged["total_cache"] / merged["test_log_zip_size"]
    merged.to_csv(os.path.join(TEST_RESULT_DIR, 'overhead_statistics.csv'), index=False)

if __name__ == "__main__":
    get_dataset_statistics()
    compute_rtp_metrics()
    get_failure_stats_from_reruns()
    # get_plugin_runtime_overhead()
    get_plugin_runtime_overhead_statistics()
