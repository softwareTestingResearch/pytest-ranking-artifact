import ast
import collections
import os
import sys

import numpy as np
import pandas as pd

script_dir = os.path.dirname(__file__)
parent_dir = os.path.join(script_dir, "..", "")
local_dir = os.path.join(script_dir, "..", "eval_global_run_dataset")
sys.path.append(parent_dir)
sys.path.append(local_dir)

import local_const
import metrics

TEST_RESULT_DIR = "parsed_rerun_results_random_order"

CI_WORKFLOW_NAMES = [f"{local_const.WF_RANDOM}_{i}" for i in range(1, 11)]


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
            for order in CI_WORKFLOW_NAMES:
                val = df[(df["project"]==project) & (df["order"]==order)][metric].mean()
                row.append(val)
            tab.append(row)
        header = ["project"] + CI_WORKFLOW_NAMES
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
                    # Label non-real failure as passed test
                    if outcome == "failed" and name not in real_failures[project]:
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
    f = f[f['order'] == len(CI_WORKFLOW_NAMES)][['project', 'run_id']]
    ret1 = pd.merge(ret, f, how="inner", on=["project", "run_id"])
    compute_rtp_metrics_helper(ret1)


def parse_run_id_labels(run_ids):
    if pd.notna(run_ids) and np.nan != run_ids:
        return set([int(i) for i in ast.literal_eval(run_ids)])
    return set()


if __name__ == "__main__":
    compute_rtp_metrics()
