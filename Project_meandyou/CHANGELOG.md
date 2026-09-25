# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2025-04-01
### Added
- Include retrieval result encompassing sample-average retrieval MRR, Multi-MRR, Hit-Rate, Multi-HitRate, Recall and micro-average Recall. These are included within `tax_global_metrics.json` and `wangchan_global_metrics.json` when running `script/metric_e2e.py`
- Add CHANGELOG for tracking future changes

### Fixed
- Fix `setup_data.py` to accommodate the adjusted schema in the dataset repo on huggingface


## [1.0.0] - 2025-02-20
### Added
- Initial release of the project.