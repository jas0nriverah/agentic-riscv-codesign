(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x13 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) (bvadd independent_opaque_1 (_ bv2147483648 32)))))
(let ((?x22 (bvadd (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv2147483648 32)) independent_opaque_0)))
(and (distinct ?x22 ?x13) true))))
(check-sat)
