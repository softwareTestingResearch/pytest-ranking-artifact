# README

`parse_rerun_results.zip`: parsed test reports from the downloaded rerun artifacts.
It can be downloaded at [this link](https://drive.google.com/file/d/1rn6ayFg55BQEeWMWfd6w72E6-SoVYqPE/view?usp=sharing).
You need to decompress it in this folder to compute evaluation results below.
It contains:
- test result csv file per (project, commit, RTP order) run
- `rerun_metadata.csv` contain metadata of the rerun commits, each row is a (project, commit/origin_run_id, RTP order) run
- `flaky_test_failures.csv` and `real_test_failures.csv` contains test failure inspection results. 


`collected_builds_dataset.zip` contains all builds (`metadata.csv`), test run builds (`test_run_metadata.csv`) and the lite version of the dataset (`lite_test_run_metadata.csv`) we collect.

`parse_rerun_results.py` parses download rerun test run artifacts from scripts in the parent folder, into `parse_rerun_results`.

`analyze_rerun_results`: computes experiment evaluation reuslts from the parsed test reports. It generates a few files:
- `dataset_statistics.csv` consists of the ''Evaluation dataset'' columns, and the ''TSR size'' columns (with the average absolute value of relative percentage difference between durations of each commits) per project.
- `APFDc_one2one.csv` and `APFDc_many2one.csv` show the APFDc values per (project, RTP roder) with one-to-one and many-to-one failure-to-fault mappings, respectively.
- `failure_statistics.csv` shows the number of flaky/real tests and test failures.
- `overhead_statistics.csv` shows the overhead of `pytest-ranking` in the experiment.

