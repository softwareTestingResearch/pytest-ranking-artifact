import datetime
import glob
import json
import os
import re
import sys
import time
import zipfile
from typing import List, Tuple

import pandas as pd

script_dir = os.path.dirname(__file__)
parent_dir = os.path.join(script_dir, "..", "")
local_dir = os.path.join(script_dir, "..", "eval_global_run_dataset")
sys.path.append(parent_dir)
sys.path.append(local_dir)

import local_const
import local_utils

PARSED_RERUN_DIR = "parsed_rerun_results"


def get_duration(test: dict) -> int:
    ret = 0
    if "setup" in test:
        ret += test["setup"]["duration"]
    if "call" in test:
        ret += test["call"]["duration"]
    if "teardown" in test:
        ret += test["teardown"]["duration"]
    return ret


def parse_test_report_from_artifact(report: dict) -> Tuple[dict, pd.DataFrame]:
    """
    return a list of [testname, test duration, test outcome, worker];
    for test run not using pytest-xdist, worker is None
    return test result summary
    """

    summary = {}
    # collect test suite run data: duration, #tests
    summary["duration"] = report["duration"]
    for k, v in report["summary"].items():
        if k not in ["collected"]:
            summary[k] = v
    df = []
    for test in report["tests"]:
        testname = test["nodeid"]
        outcome = test["outcome"]
        duration = get_duration(test)
        row = [testname, outcome, duration]
        # check if test is run in parallel
        if "longrepr" in test["setup"] and test["setup"]["longrepr"].startswith("[gw"):
            worker = test["setup"]["longrepr"][1:4]
            row.append(worker)
        else:
            row.append(None)
        df.append(row)
    df = pd.DataFrame(df, columns=["test", "outcome", "duration", "worker"])
    return summary, df


def parse_workflow_artifact(artifact_file: str, project, run_id: str, order: str) -> dict:
    print(f"[global-run] Processing {artifact_file}")
    with zipfile.ZipFile(artifact_file) as myzip:
        assert myzip.namelist() == ["test-report.json"]
        with myzip.open("test-report.json") as myfile:
            report = json.load(myfile)
            summary, df = parse_test_report_from_artifact(report)
            if len(df.index):
                output_folder = os.path.join(PARSED_RERUN_DIR, project, run_id)
                os.makedirs(output_folder, exist_ok=True)
                output_file = os.path.join(output_folder, f"{order}.csv")
                df.to_csv(output_file, index=False)
                print(f"[global-run] Writing {output_file}\n")
            return summary


def parse_rerun_dataset():
    """
    Parse rerun dataset as csvs, with a rerun_metadata.csv:
        - project, run_id, order, rerun_id, has_artifact, outcomes, run_html
    """
    rows = pd.read_csv("../global_run_dataset/lite_test_run_metadata.csv")
    df = []
    for i, row in rows.iterrows():
        project = row["project"]
        run_id = row["run_id"]
        run_started_at = row["run_started_at"]
        run_conclusion = row["run_conclusion"]
        for order in local_const.CI_WORKFLOW_NAMES:
            rerun_folder = os.path.join(
                local_const.RERUN_DIR, project, local_const.WORKFLOWRUN_DIR, str(int(run_id))
            )
            if os.path.exists(rerun_folder):
                # Check rerun metadata.
                metadata_file = os.path.join(rerun_folder, local_const.RUN_META_FILE.format(run_name=order))
                rerun_meta = json.load(open(metadata_file, "r"))
                rerun_id = rerun_meta["id"]
                rerun_date = rerun_meta["created_at"]
                rerun_html = rerun_meta["html_url"]
                # Check rerun artifact.
                artifact_file = os.path.join(rerun_folder, local_const.RUN_ARTIFACT_FILE.format(run_name=order))
                new_row = {
                    "project": project, "run_id": run_id, "origin_run_started_at": run_started_at, "origin_run_conclusion": run_conclusion,
                    "order": order, "rerun_id": rerun_id, "rerun_date": rerun_date, "has_artifact": True if os.path.exists(artifact_file) else False
                }
                if os.path.exists(artifact_file):
                    artifact_summary = parse_workflow_artifact(artifact_file, project, str(int(run_id)), order)
                    new_row.update(artifact_summary)
                new_row["rerun_html"] = rerun_html
                df.append(new_row)
    df = pd.DataFrame(df)
    df.to_csv(os.path.join(PARSED_RERUN_DIR, "rerun_metadata.csv"), index=False)


if __name__ == "__main__":
    parse_rerun_dataset()
