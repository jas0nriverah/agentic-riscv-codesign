(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x283 (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x1000 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x283)))
(let ((?x538 (bvsub ?x283 independent_opaque_0)))
(and (distinct ?x538 ?x1000) true)))))
(check-sat)
