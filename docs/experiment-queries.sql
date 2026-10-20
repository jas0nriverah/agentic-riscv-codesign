-- Read-only analysis of the authenticated SQLite projection; never give this
-- database to a selection policy. Run after `make demo`:
-- sqlite3 -header -column generated/reproduction/prospective-slre/experiments.sqlite < docs/experiment-queries.sql

-- Retain the baseline as an option; apply the declared area and timing limits
-- BEFORE ranking. Join by context, not merely by workload/formula names.
WITH baselines AS (
    SELECT context_id, integrated_lut4 + 128 AS area_cap
    FROM measurements WHERE name = 'baseline' AND candidate_id IS NULL
), feasible AS (
    SELECT m.*, c.workload, b.area_cap,
           ROW_NUMBER() OVER (
               PARTITION BY m.context_id
               ORDER BY m.speedup DESC, m.integrated_lut4, m.name
           ) AS choice
    FROM measurements AS m
    JOIN contexts AS c USING (context_id)
    JOIN baselines AS b USING (context_id)
    WHERE c.status = 'verified_complete'
      AND m.correctness_verified = 1 AND m.timing_feasible = 1
      AND m.frequency_mhz = 12 AND m.integrated_lut4 <= b.area_cap
)
SELECT workload, name, cycles, ROUND(speedup, 6) AS speedup,
       integrated_lut4, added_lut4,
       (SELECT ROUND(MIN(r.fmax_mhz), 3) FROM routes AS r
        WHERE r.context_id = f.context_id AND r.evaluation_id = f.evaluation_id) AS worst_routed_fmax_mhz
FROM feasible AS f WHERE choice = 1 ORDER BY workload;

-- Timer kinds overlap. Only aggregate within a timer kind; include incomplete
-- contexts so the cost of the failed preparation remains visible.
SELECT c.workload, c.status, s.kind, s.phase, s.records,
       ROUND(s.seconds, 3) AS seconds
FROM cost_summary AS s JOIN contexts AS c USING (context_id)
ORDER BY c.workload, c.status, s.kind, s.phase;

-- Trace a failure back to its exact build context and authentication status.
SELECT c.workload, f.context_id, f.source_path, f.authentication,
       json_extract(f.detail_json, '$.error') AS error
FROM failures AS f JOIN contexts AS c USING (context_id)
ORDER BY c.workload, f.context_id, f.source_path;
