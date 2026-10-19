(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x72 (bvadd independent_opaque_0 (_ bv0 32))))
(and (distinct ?x72 independent_opaque_0) true)))
(check-sat)
