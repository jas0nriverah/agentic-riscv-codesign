(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x821 (bvadd independent_opaque_0 (_ bv129 32))))
(and (distinct ?x821 ?x821) true)))
(check-sat)
