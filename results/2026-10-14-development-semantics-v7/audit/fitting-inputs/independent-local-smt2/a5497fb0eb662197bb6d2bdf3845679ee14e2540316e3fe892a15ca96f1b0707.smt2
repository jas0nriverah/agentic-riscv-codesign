(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x40 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvadd (bvshl independent_opaque_1 (bvand (_ bv1 32) (_ bv31 32))) (_ bv17 32)))))
(let ((?x12 (bvadd (bvadd (bvsub independent_opaque_1 independent_opaque_0) (_ bv17 32)) independent_opaque_1)))
(and (distinct ?x12 ?x40) true))))
(check-sat)
