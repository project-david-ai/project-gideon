from project_gideon.models.job import Job
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)
from project_gideon.services.job_identity import (
    build_job_identity,
    canonical_job_fingerprint,
)


def make_job(
    **overrides,
):
    values = {
        "id": "job-1",
        "tenant_id": "tenant-1",
        "source": "LinkedIn",
        "source_job_id": "ABC-123",
        "source_url": "https://example.com/job/1",
        "title": "Senior Network Engineer",
        "company": "Acme Ltd.",
        "description": "Role description.",
        "location": "Berlin, Germany",
        "remote": False,
        "employment_type": "Full Time",
    }

    values.update(
        overrides
    )

    return Job(
        **values
    )


def test_fingerprint_is_stable_across_cosmetic_text_variants():
    left = make_job()

    right = make_job(
        id="job-2",
        company="  ACME LTD  ",
        title="Senior   Network Engineer",
        location="BERLIN, GERMANY",
        employment_type="full-time",
        description="Completely different board description.",
    )

    assert (
        canonical_job_fingerprint(
            left
        )
        == canonical_job_fingerprint(
            right
        )
    )


def test_fingerprint_excludes_source_identity():
    left = make_job()

    right = make_job(
        id="job-2",
        source="Indeed",
        source_job_id="indeed-999",
        source_url="https://indeed.example/job/999",
    )

    assert (
        canonical_job_fingerprint(
            left
        )
        == canonical_job_fingerprint(
            right
        )
    )


def test_build_identity_keeps_source_and_requisition_evidence():
    candidate = JobIngestionCandidate(
        job=make_job(),
        requisition_id="REQ-7788",
    )

    identity = build_job_identity(
        candidate
    )

    assert identity.tenant_id == "tenant-1"
    assert identity.source == "linkedin"
    assert identity.source_job_id == "abc-123"
    assert identity.requisition_id == "req-7788"
    assert identity.canonical_fingerprint
