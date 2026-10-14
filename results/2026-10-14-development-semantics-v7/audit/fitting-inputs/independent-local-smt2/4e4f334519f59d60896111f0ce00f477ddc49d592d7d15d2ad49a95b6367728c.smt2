(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x15 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32))))))
(let ((?x1104 (bvand (_ bv1 32) (_ bv31 32))))
(let ((?x24 (bvadd independent_opaque_0 (bvshl independent_opaque_1 (bvand (_ bv3 32) (_ bv31 32))))))
(let ((?x1153 (bvshl ?x24 ?x1104)))
(and (distinct ?x1153 ?x15) true))))))
(check-sat)
