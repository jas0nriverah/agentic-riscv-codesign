(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x289 (bvadd independent_opaque_0 (bvsub (_ bv0 32) independent_opaque_1))))
(let ((?x82 (bvsub independent_opaque_0 independent_opaque_1)))
(and (distinct ?x82 ?x289) true))))
(check-sat)
