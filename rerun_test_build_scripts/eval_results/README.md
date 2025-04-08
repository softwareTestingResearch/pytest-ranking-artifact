# README

`parse_rerun_results.zip`: parsed test reports from the downloaded rerun artifacts for all orders (350MB).
It can be downloaded at [this link](https://drive.google.com/file/d/1zLfE9WkHMtqpQoWPaWgHsUmW4wN0GngF/view?usp=sharing).
You need to decompress it in this folder to compute evaluation results below.
It contains:
- test result csv file per (project, commit, RTP order) run
- `rerun_metadata.csv` contain metadata of the rerun commits, each row is a (project, commit/origin_run_id, RTP order) run
- `overhead.csv` contains overhead data of each run.
- `regression_failed_runs.json`: contains the rerun IDs that have regression-induced test failures, based on the inspection data `real_test_failures.csv`


`parsed_rerun_results_random_order.zip`: parsed test reports from the downloaded rerun artifacts for 10 random order reruns per historical build (150 MB).
It can be downloaded at [this link](https://drive.google.com/file/d/1f6oKqT6do0-9MWCFWeimdtCMRKf1pWm5/view?usp=sharing).

`flaky_test_failures.csv` and `real_test_failures.csv` contains test result inspection on all orders.

`flaky_test_failures_random_order.csv` contains test result inspection on the 10 random order reruns.


`collected_builds_dataset.zip` contains all builds (`metadata.csv`), test run builds (`test_run_metadata.csv`) and the lite version of the dataset (`lite_test_run_metadata.csv`) we collected.

`parse_rerun_results.py` parses download rerun test run artifacts from scripts in the parent folder, into `parse_rerun_results`.

`analyze_rerun_results`: computes experiment evaluation results from the parsed test reports. It generates a few files:
- `dataset_statistics.csv` consists of the ''Evaluation dataset'' columns, and the ''TSR size'' columns (with the average absolute value of relative percentage difference between durations of each commits) per project.
- `APFDc_one2one.csv` and `APFDc_many2one.csv` show the APFDc values per (project, RTP roder) with one-to-one and many-to-one failure-to-fault mappings, respectively.
- `failure_statistics.csv` shows the number of flaky/real tests and test failures.
- `overhead_statistics.csv` shows the overhead of `pytest-ranking` in the experiment.
