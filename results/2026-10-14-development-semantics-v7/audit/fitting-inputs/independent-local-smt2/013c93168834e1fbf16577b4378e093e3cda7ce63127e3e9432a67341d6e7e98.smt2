(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x271 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv1 32)))))
(and (distinct ?x271 ?x271) true)))
(check-sat)
