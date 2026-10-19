(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x293 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))))
(let ((?x15 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x895 (bvshl (bvsub independent_opaque_0 independent_opaque_1) ?x15)))
(and (distinct ?x895 ?x293) true)))))
(check-sat)
