from scripts.audit_ascon_source_family import build_report


def test_hash_bound_ascon_source_family_audit_reports_overlap_without_target_claims():
    report = build_report()

    assert report["status"] == "source_level_crypto_overlap_confirmed_exact_target_pool_pending"
    assert report["ascon"]["commit"] == "b7ca60bbf86479785de08b75aab2425dce4e9e8b"
    assert report["ascon"]["copied_file_count"] == 13
    assert report["ascon"]["copied_bytes"] == 288906
    assert report["eligibility"] == {
        "independent_confirmatory_family": False,
        "same_domain_crypto_transfer_lead": True,
        "exact_ascon_candidate_family_audit": "pending target candidate extraction",
        "target_jobs": 0,
        "target_labels": 0,
        "model_fits": 0,
        "candidate_dispatch_enabled": False,
    }

    motifs = report["ascon_source_motifs"]
    assert motifs["complemented_and"]["related_existing_candidate_families"][
        "and(input,xori(input,constant))"] == ["aha_compress"]
    assert motifs["rotate_diffusion"]["related_existing_candidate_families"][
        "or(input,slli(input,constant))"] == ["ndes", "nettle_md5", "nettle_sha256"]

    intersections = report["exact_formula_family_intersections_between_existing_pools"]
    assert intersections["ndes__nettle_md5"] == [
        "add(input,slli(input,constant))",
        "or(input,slli(input,constant))",
    ]
    assert intersections["ndes__nettle_sha256"] == intersections["ndes__nettle_md5"]
    assert intersections["nettle_md5__nettle_sha256"] == intersections["ndes__nettle_md5"]
