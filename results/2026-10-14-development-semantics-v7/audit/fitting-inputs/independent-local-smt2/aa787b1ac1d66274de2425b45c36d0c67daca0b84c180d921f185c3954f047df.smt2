(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x844 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32)))) (bvshl independent_opaque_1 (bvand (_ bv16 32) (_ bv31 32))))))
(let ((?x1180 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x1257 (bvshl (bvsub independent_opaque_1 independent_opaque_0) ?x1180)))
(and (distinct ?x1257 ?x844) true)))))
(check-sat)
