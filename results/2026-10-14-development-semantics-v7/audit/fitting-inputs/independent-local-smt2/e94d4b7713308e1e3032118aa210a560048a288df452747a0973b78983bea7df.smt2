(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x392 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) (bvadd (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32))) (_ bv16 32)))))
(let ((?x996 (bvand (_ bv1 32) (_ bv31 32))))
(let ((?x37 (bvadd independent_opaque_0 (bvshl independent_opaque_1 (bvand (_ bv3 32) (_ bv31 32))))))
(let ((?x67 (bvadd (bvshl ?x37 ?x996) (_ bv16 32))))
(and (distinct ?x67 ?x392) true))))))
(check-sat)
