(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x676 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) (_ bv2 32))))
(let ((?x113 (bvand (_ bv1 32) (_ bv31 32))))
(let ((?x1208 (bvshl (bvadd independent_opaque_0 (_ bv1 32)) ?x113)))
(and (distinct ?x1208 ?x676) true)))))
(check-sat)
