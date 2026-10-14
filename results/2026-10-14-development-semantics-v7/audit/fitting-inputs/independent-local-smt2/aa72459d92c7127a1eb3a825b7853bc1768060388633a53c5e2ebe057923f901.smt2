(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x231 (bvadd (bvsub (_ bv0 32) independent_opaque_0) independent_opaque_1)))
(let ((?x1000 (bvsub independent_opaque_1 independent_opaque_0)))
(and (distinct ?x1000 ?x231) true))))
(check-sat)
