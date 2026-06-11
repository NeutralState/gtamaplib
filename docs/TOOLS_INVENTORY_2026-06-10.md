# INVENTAIRE OUTILS — 2026-06-10 (genere)

| dernier commit | outil | ref CLAUDE_CONTEXT | importe/reference par un outil |
|---|---|---|---|
| 2026-05-03 | tools/bundle_adjust_apply.py | oui | oui |
| 2026-05-07 | tools/audit/audit_fixed_landmarks_quality.py | — | oui |
| 2026-05-07 | tools/audit/audit_leak_consistency.py | — | oui |
| 2026-05-07 | tools/audit/check_camera_consistency.py | — | oui |
| 2026-05-07 | tools/audit/check_landmark_consistency.py | — | — |
| 2026-05-07 | tools/audit/compare_rlx_vs_current.py | — | — |
| 2026-05-07 | tools/audit/diagnose_camera.py | — | — |
| 2026-05-07 | tools/audit/find_outlier_pixels.py | — | oui |
| 2026-05-07 | tools/audit/investigate_landmark.py | — | oui |
| 2026-05-07 | tools/audit/list_extra_observers.py | — | — |
| 2026-05-07 | tools/audit/trace_ray_on_map.py | — | oui |
| 2026-05-07 | tools/outliers_report.py | oui | oui |
| 2026-05-07 | tools/refine/apply_z_constraints.py | — | oui |
| 2026-05-07 | tools/refine/batch_refine_cameras.py | — | — |
| 2026-05-07 | tools/refine/batch_retriangulate_aiwe_fixed.py | — | oui |
| 2026-05-07 | tools/refine/delete_outlier_pixels.py | — | oui |
| 2026-05-07 | tools/refine/pin_on_primary_ray.py | — | — |
| 2026-05-07 | tools/regen_index_camdata.py | — | — |
| 2026-05-09 | tools/prerender_minimaps_fast.py | oui | oui |
| 2026-05-10 | tools/port_rlx_batch.py | — | oui |
| 2026-05-10 | tools/port_rlx_inventory.py | — | oui |
| 2026-05-10 | tools/port_rlx_one_cam.py | — | oui |
| 2026-05-10 | tools/refine/refine_camera.py | oui | oui |
| 2026-05-12 | tools/batch_optimize.py | — | oui |
| 2026-05-12 | tools/calibrate_session.py | oui | oui |
| 2026-05-12 | tools/calibration_order.py | oui | oui |
| 2026-05-14 | tools/audit/audit_all_leak_opportunities.py | — | oui |
| 2026-05-14 | tools/audit/audit_leak_influence_tree.py | oui | oui |
| 2026-05-14 | tools/audit/audit_leak_marker_quality.py | — | oui |
| 2026-05-14 | tools/audit/audit_leak_priority_ranking.py | — | oui |
| 2026-05-14 | tools/calibrate_cam.py | — | oui |
| 2026-05-17 | tools/gen_portofino_lms.py | — | — |
| 2026-05-17 | tools/gen_portofino_precise.py | — | — |
| 2026-05-17 | tools/gen_portofino_v2.py | — | — |
| 2026-05-17 | tools/gen_portofino_v3.py | — | — |
| 2026-05-17 | tools/gen_portofino_v4.py | oui | — |
| 2026-05-18 | tools/refine/retriangulate_landmark.py | — | oui |
| 2026-05-18 | tools/render_loss.py | — | oui |
| 2026-05-21 | tools/densify_portofino_edges.py | oui | oui |
| 2026-05-23 | tools/compute_venetian_xyz.py | — | — |
| 2026-05-23 | tools/discover_mesh_candidates.py | — | — |
| 2026-05-23 | tools/portofino_v5.py | — | oui |
| 2026-05-25 | tools/gen_missing_thumbs.py | oui | — |
| 2026-05-26 | tools/build_cam_health.py | oui | — |
| 2026-05-26 | tools/bundle_adjust.py | oui | oui |
| 2026-05-26 | tools/compute_confidence_tiers.py | oui | oui |
| 2026-05-26 | tools/fix_audit_orientations.py | — | oui |
| 2026-05-26 | tools/intake_camera.py | oui | oui |
| 2026-05-26 | tools/migrate_constraint_classes.py | — | oui |
| 2026-05-31 | tools/server.py | oui | oui |
| 2026-05-31 | tools/triangulate_lm.py | oui | oui |
| 2026-06-03 | tools/audit/circular_deps.py | oui | — |
| 2026-06-03 | tools/audit/retriangulation_candidates.py | oui | — |
| 2026-06-04 | tools/audit/lm_uncertainty.py | oui | oui |
| 2026-06-04 | tools/generate_inventory.py | oui | — |
| 2026-06-04 | tools/leak_cam_audit.py | oui | oui |
| 2026-06-04 | tools/refine_cam_full.py | oui | oui |
| 2026-06-04 | tools/refine_cam_ypr.py | oui | oui |
| 2026-06-08 | tools/observability_report.py | oui | — |
| 2026-06-10 | tools/audit/find_z_candidates.py | oui | oui |
| 2026-06-10 | tools/audit/invariants.py | oui | oui |
| 2026-06-10 | tools/audit/keys_z_bias_analysis.py | oui | oui |
| 2026-06-10 | tools/audit/rms_snapshot.py | oui | oui |
| 2026-06-10 | tools/bundle_adjust_weighted.py | oui | oui |
| 2026-06-10 | tools/calibrate_batch.py | oui | — |
| 2026-06-10 | tools/extract_mesh_edges.py | oui | oui |
| 2026-06-10 | tools/refine/clean_provenance.py | — | — |
| 2026-06-10 | tools/refine/free_waterline_z.py | oui | oui |
| 2026-06-10 | tools/refine/guarded_apply.py | oui | — |
| 2026-06-10 | tools/refine/natural_z_sweep.py | — | oui |

## Candidats archivage (vieux + zero reference) — DECISION ALEXANDRE
- tools/audit/check_landmark_consistency.py (2026-05-07)
- tools/audit/compare_rlx_vs_current.py (2026-05-07)
- tools/audit/diagnose_camera.py (2026-05-07)
- tools/audit/list_extra_observers.py (2026-05-07)
- tools/refine/batch_refine_cameras.py (2026-05-07)
- tools/refine/pin_on_primary_ray.py (2026-05-07)
- tools/regen_index_camdata.py (2026-05-07)
- tools/gen_portofino_lms.py (2026-05-17)
- tools/gen_portofino_precise.py (2026-05-17)
- tools/gen_portofino_v2.py (2026-05-17)
- tools/gen_portofino_v3.py (2026-05-17)
- tools/compute_venetian_xyz.py (2026-05-23)
- tools/discover_mesh_candidates.py (2026-05-23)