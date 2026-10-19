"""Inference audit guards with label-free fake predictors; never fit or map."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('infer_v8_under_test',ROOT/'scripts/infer_v8_applications.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FakePredictor:
    def __init__(self,mutate=None):self.mutate=mutate;self.native_rows=None;self.stored_values=None
    def compatibility_report(self):return {'audited_compatible':True}
    def predict_features(self,rows,values,*,feature_columns):
        self.stored_values=values
        if self.mutate:self.mutate()
        return [{**{k:r[k] for k in ('formula','benchmark','candidate_id') if k in r},'predicted_lut4':float(v[0]),'upper_lut4':None} for r,v in zip(rows,values)]
    def predict_with_evidence(self,rows):
        self.native_rows=rows
        if self.mutate:self.mutate()
        return {'predictions':[{'formula':r['formula'],'predicted_lut4':3.,'upper_lut4':None} for r in rows],
                'feature_records':[{'formula':r['formula'],'retained_first_native_proof':'fallback-original'} for r in rows]}

class InferenceGuards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.model=self.root/'model.joblib';self.model.write_bytes(b'fixed-point-artifact')
        self.model.with_suffix('.json').write_text('{}')
        self.candidates=self.root/'candidates.json';self.features=self.root/'features.json';self.output=self.root/'inference.json'
    def put(self,path,value):path.write_text(json.dumps(value))
    def invoke(self,predictor,features=False):
        with patch.object(m.v8,'load_model',return_value=predictor),redirect_stdout(io.StringIO()):
            m.run(self.model,self.candidates,self.output,self.root/'cache',self.features if features else None)
        return json.loads(self.output.read_text())
    def test_native_deduplicates_canonical_formula_and_discards_outcomes(self):
        rows=[{'benchmark':'A','candidate_id':'a','formula':' addi(in0, 1) ','lut4_count':999,'values':[999]},
              {'benchmark':'B','candidate_id':'b','formula':'addi(in0,1)','predicted_lut4':999,'upper_lut4':999}]
        self.put(self.candidates,rows);predictor=FakePredictor();result=self.invoke(predictor)
        self.assertEqual(predictor.native_rows,[{'formula':'addi(in0,1)'}])
        self.assertEqual([r['benchmark'] for r in result['predictions']],['A','B'])
        self.assertTrue(all(r['predicted_lut4']==3 and r['upper_lut4'] is None for r in result['predictions']))
        self.assertFalse(any('lut4_count' in r or 'values' in r for r in result['predictions']))
        self.assertEqual(result['feature_records'][0]['retained_first_native_proof'],'fallback-original')
    def test_stored_rows_align_by_formula_and_keep_duplicate_program_weights(self):
        self.put(self.candidates,[{'formula':'addi(in0,1)','benchmark':'A'},{'formula':'addi(in0,2)','benchmark':'B'},{'formula':'addi(in0,1)','benchmark':'C'}])
        self.put(self.features,{'columns':['fake-column'],'records':[{'formula':'addi(in0,2)','values':[2]},{'formula':'addi(in0,1)','values':[1]}]})
        p=FakePredictor();r=self.invoke(p,features=True)
        self.assertEqual(p.stored_values,[[1],[2],[1]])
        self.assertEqual([x['predicted_lut4'] for x in r['predictions']],[1,2,1])
        self.assertEqual(r['application_rows'],3)
    def test_stored_union_rejects_missing_extra_and_duplicate_records(self):
        self.put(self.candidates,[{'formula':'addi(in0,1)'}])
        valid={'formula':'addi(in0,1)','values':[1]};extra={'formula':'addi(in0,2)','values':[2]}
        for records in ([],[valid,extra],[valid,dict(valid)]):
            with self.subTest(records=records):
                self.put(self.features,{'columns':['x'],'records':records})
                with self.assertRaises(ValueError):self.invoke(FakePredictor(),features=True)
                self.assertFalse(self.output.exists())
    def test_existing_output_blocks_model_loading(self):
        self.output.write_text('retained')
        with patch.object(m.v8,'load_model',side_effect=AssertionError('must not load')):
            with self.assertRaises(ValueError):m.run(self.model,self.candidates,self.output,self.root/'cache')
        self.assertEqual(self.output.read_text(),'retained')
    def test_changed_input_or_artifact_during_inference_cannot_be_rebound(self):
        for selected in ('model','schema','candidates','features'):
            with self.subTest(selected=selected):
                self.output.unlink(missing_ok=True);self.model.write_bytes(b'fixed-point-artifact');self.model.with_suffix('.json').write_text('{}')
                self.put(self.candidates,[{'formula':'addi(in0,1)'}]);self.put(self.features,{'columns':['x'],'records':[{'formula':'addi(in0,1)','values':[1]}]})
                target={'model':self.model,'schema':self.model.with_suffix('.json'),'candidates':self.candidates,'features':self.features}[selected]
                predictor=FakePredictor(lambda:target.write_text('changed-after-load'))
                with self.assertRaises(ValueError):self.invoke(predictor,features=True)
                self.assertFalse(self.output.exists())

    def test_runtime_source_change_blocks_inference_evidence(self):
        self.put(self.candidates,[{'formula':'addi(in0,1)'}])
        with patch.object(m.v8,'source_hashes',side_effect=[{'source':'before'},{'source':'after'}]):
            with self.assertRaises(ValueError):self.invoke(FakePredictor())
        self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
