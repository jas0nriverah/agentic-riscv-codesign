(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x8 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32))) (_ bv65535 32)))))
(let ((?x28 (bvadd (bvadd (bvadd independent_opaque_1 independent_opaque_0) (_ bv65535 32)) independent_opaque_1)))
(and (distinct ?x28 ?x8) true))))
(check-sat)
