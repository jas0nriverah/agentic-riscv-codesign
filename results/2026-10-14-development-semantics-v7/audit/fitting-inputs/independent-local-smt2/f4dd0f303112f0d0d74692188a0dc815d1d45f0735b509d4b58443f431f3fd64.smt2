(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x231 (bvshl independent_opaque_0 (bvand (_ bv13 32) (_ bv31 32)))))
(let ((?x1335 (bvadd ?x231 (bvsub (_ bv0 32) independent_opaque_1))))
(let ((?x85 (bvsub ?x231 independent_opaque_1)))
(and (distinct ?x85 ?x1335) true)))))
(check-sat)
