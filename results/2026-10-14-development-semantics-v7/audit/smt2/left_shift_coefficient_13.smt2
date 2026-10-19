(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x163 (bvmul x (_ bv8192 32))))
(let ((?x161 (bvshl x (_ bv13 32))))
(and (distinct ?x161 ?x163) true))))
(check-sat)
