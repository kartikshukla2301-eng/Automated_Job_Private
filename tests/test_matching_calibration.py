"""Unit tests for Matching Calibration and Performance Analytics (Phase 2.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import pytest

from worker.matching.calibration import (
    CalibrationReport,
    CalibrationSample,
    MatchingCalibrator,
    generate_benchmark_samples,
)


def test_generate_benchmark_samples_integrity():
    """Verify benchmark samples generation produces 50 canonical, well-structured samples."""
    samples = generate_benchmark_samples()
    assert len(samples) == 50

    apply_count = sum(1 for s in samples if s.human_label == "APPLY")
    skip_count = sum(1 for s in samples if s.human_label == "SKIP")
    assert apply_count > 0
    assert skip_count > 0
    assert apply_count + skip_count == 50

    # Verify hard filter rejections
    excluded_samples = [s for s in samples if not s.passed_hard_filters]
    assert len(excluded_samples) >= 15
    for s in excluded_samples:
        assert s.human_label == "SKIP"
        assert s.decision == "EXCLUDED"
        assert len(s.hard_filter_reasons) > 0


def test_matching_calibrator_metrics():
    """Verify precision, recall, false positive rate, and segment metrics calculation."""
    calibrator = MatchingCalibrator()
    report: CalibrationReport = calibrator.evaluate(threshold=65.0)

    assert report.total_samples == 50
    assert report.precision >= 70.0
    assert report.recall >= 70.0
    assert report.false_positive_rate <= 15.0
    assert report.f1_score >= 70.0

    # Architectural invariant: Hard filter override count MUST strictly be 0
    assert report.hard_filter_override_count == 0

    # Score percentiles
    dist = report.score_distribution
    assert "p25" in dist and "p50" in dist and "p75" in dist and "p90" in dist
    assert dist["p25"] <= dist["p50"] <= dist["p75"] <= dist["p90"]

    # Segment breakdowns
    assert "backend" in report.role_family_performance
    assert "platform" in report.role_family_performance
    assert "remote" in report.work_mode_performance
    assert report.role_family_performance["backend"]["accuracy"] >= 60.0


def test_hard_filter_override_detection():
    """Verify that an illegal hard-filter override (e.g. LLM promoting excluded job) is caught."""
    samples = generate_benchmark_samples()
    # Inject an intentional violation
    samples[45].decision = "MATCH"
    samples[45].passed_hard_filters = False

    calibrator = MatchingCalibrator(samples=samples)
    report = calibrator.evaluate()

    assert report.hard_filter_override_count == 1
