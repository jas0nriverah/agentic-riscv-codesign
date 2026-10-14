(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x48 (bvmul (_ bv1 32) x)))
(and (distinct ?x48 x) true)))
(check-sat)
