(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x46 (bvmul (_ bv0 32) x)))
(and (distinct (_ bv0 32) ?x46) true)))
(check-sat)
