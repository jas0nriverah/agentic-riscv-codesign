(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x42 (bvadd independent_opaque_0 (_ bv5 32))))
(and (distinct ?x42 ?x42) true)))
(check-sat)
