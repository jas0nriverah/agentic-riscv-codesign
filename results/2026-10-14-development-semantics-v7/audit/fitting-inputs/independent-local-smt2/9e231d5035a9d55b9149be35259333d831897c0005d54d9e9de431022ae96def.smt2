(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x958 (bvadd independent_opaque_0 (_ bv0 32))))
(and (distinct independent_opaque_0 ?x958) true)))
(check-sat)
