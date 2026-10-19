(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x222 (bvadd (bvsub (_ bv0 32) independent_opaque_0) independent_opaque_1)))
(let ((?x602 (bvsub independent_opaque_1 independent_opaque_0)))
(and (distinct ?x602 ?x222) true))))
(check-sat)
