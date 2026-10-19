(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x514 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))) (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv31 32) (_ bv31 32)))))))
(let ((?x1210 (bvand (_ bv31 32) (_ bv31 32))))
(let ((?x305 (bvshl (bvsub independent_opaque_1 independent_opaque_0) ?x1210)))
(and (distinct ?x305 ?x514) true)))))
(check-sat)
