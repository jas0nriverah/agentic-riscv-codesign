(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x25 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32))) (_ bv4294966072 32)))))
(let ((?x11 (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x13 (bvadd (bvadd independent_opaque_0 (_ bv4294966072 32)) ?x11)))
(and (distinct ?x13 ?x25) true)))))
(check-sat)
