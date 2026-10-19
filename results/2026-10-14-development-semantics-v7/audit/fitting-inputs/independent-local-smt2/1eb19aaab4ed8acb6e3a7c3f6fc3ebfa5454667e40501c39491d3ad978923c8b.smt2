(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x13 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))) independent_opaque_1)))
(let ((?x428 (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))))
(let ((?x42 (bvadd ?x428 independent_opaque_1)))
(and (distinct ?x42 ?x13) true)))))
(check-sat)
