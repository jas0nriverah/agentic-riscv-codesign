(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x66 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32))))))
(let ((?x33 (bvand (_ bv1 32) (_ bv31 32))))
(let ((?x676 (bvshl (bvadd independent_opaque_1 independent_opaque_0) ?x33)))
(and (distinct ?x676 ?x66) true)))))
(check-sat)
