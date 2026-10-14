(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x113 (bvadd independent_opaque_0 (_ bv12 32))))
(and (distinct ?x113 ?x113) true)))
(check-sat)
