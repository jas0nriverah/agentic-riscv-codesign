"""Check plotted arithmetic against committed raw summaries, without native jobs."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cpu_tradeoff_plot',ROOT/'scripts/plot_cpu_hardware_tradeoffs.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class HardwareTradeoffTests(unittest.TestCase):
    def setUp(self):
        self.summary=m.read(ROOT/m.SOURCE_DIR/'summary.json')
        self.routing=m.read(ROOT/m.SOURCE_DIR/'routing-summary.json')

    def test_every_resource_delta_matches_exact_source_counts(self):
        data=m.actual_data();expected=[(1633,1704,71),(655,679,24),(295,297,2),(20,20,0)]
        for row,(baseline,custom,delta) in zip(data['resources'],expected):
            self.assertEqual((row['baseline'],row['custom'],row['delta']),(baseline,custom,delta))
            self.assertEqual(row['ratio'],custom/baseline)
            self.assertEqual(row['change_percent'],100*(custom/baseline-1))

    def test_all_matched_seeds_use_each_own_frequency_not_cross_seed_extrema(self):
        data=m.actual_data();cycles=self.summary['measurements'];lutratio=1704/1633
        for row in data['runtime_cases'][:3]:
            seed=int(row['case'][-1])
            freqs={r['configuration']:r['limiting_internal_fmax_mhz'] for r in self.routing['runs'] if r['seed']==seed}
            baseline=cycles['baseline']['cycles']/(freqs['baseline']*1e6)
            custom=cycles['custom']['cycles']/(freqs['custom']*1e6)
            self.assertEqual(row['baseline_seconds'],baseline);self.assertEqual(row['custom_seconds'],custom)
            self.assertEqual(row['custom_over_baseline_runtime'],custom/baseline)
            self.assertEqual(row['lut4_times_runtime_ratio'],lutratio*custom/baseline)
            self.assertAlmostEqual(row['baseline_over_custom_speedup']*row['custom_over_baseline_runtime'],1,places=14)
        self.assertEqual([r['case'] for r in data['runtime_cases']],['seed1','seed2','seed3','common12mhz'])

    def test_common_clock_is_cycle_ratio_and_absolute_runtime(self):
        row=m.actual_data()['runtime_cases'][-1]
        self.assertEqual(row['baseline_seconds'],32387382/12e6)
        self.assertEqual(row['custom_seconds'],29602102/12e6)
        self.assertEqual(row['custom_over_baseline_runtime'],29602102/32387382)
        self.assertAlmostEqual(row['lut4_times_runtime_ratio'],.9537402533197489,places=15)

    def test_proxy_preserves_all_three_seed_tradeoffs(self):
        values=[r['lut4_times_runtime_ratio'] for r in m.actual_data()['runtime_cases']]
        for a,b in zip(values,[1.0209889766695506,1.002424653808924,.9150003295864668,.9537402533197489]):self.assertAlmostEqual(a,b,places=14)
        self.assertEqual(sum(x>1 for x in values[:3]),2)

    def test_missing_duplicate_unexpected_or_failed_run_rejected(self):
        cases=[]
        d=copy.deepcopy(self.routing);d['runs'].pop();cases.append(d)
        d=copy.deepcopy(self.routing);d['runs'].append(copy.deepcopy(d['runs'][0]));cases.append(d)
        d=copy.deepcopy(self.routing);d['runs'][0]['seed']=4;cases.append(d)
        d=copy.deepcopy(self.routing);d['runs'][0]['internal_timing_pass']=False;cases.append(d)
        d=copy.deepcopy(self.routing);d['runs'][0]['limiting_internal_fmax_mhz']=float('nan');cases.append(d)
        d=copy.deepcopy(self.routing);d['netlist_sha256']['baseline']='wrong';cases.append(d)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):m.derive_data(self.summary,case)

    def test_cycle_controls_and_checksum_must_match(self):
        for kind in ['source-control','stock-on-custom']:
            d=copy.deepcopy(self.summary);d['measurements'][kind]['cycles']+=1
            with self.assertRaises(ValueError):m.derive_data(d,self.routing)
        d=copy.deepcopy(self.summary);d['measurements']['custom']['full_checksum']+=1
        with self.assertRaises(ValueError):m.derive_data(d,self.routing)

    def test_source_hashes_are_verified_before_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/m.SOURCE_DIR;folder.mkdir(parents=True)
            (folder/'summary.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash'):m.actual_data(root)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            marker=Path(d)/'keep';marker.write_text('original')
            with self.assertRaises(FileExistsError):m.run(Path(d))
            self.assertEqual(marker.read_text(),'original')

if __name__=='__main__':unittest.main()
