(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1183 (bvadd (bvsub (_ bv0 32) independent_opaque_0) (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))))))
(let ((?x744 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) independent_opaque_0)))
(and (distinct ?x744 ?x1183) true))))
(check-sat)
