(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x47 (bvadd (bvshl independent_opaque_0 (bvand (_ bv3 32) (_ bv31 32))) independent_opaque_1)))
(let ((?x8 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32)))) ?x47)))
(let ((?x13 (bvand (_ bv1 32) (_ bv31 32))))
(let ((?x329 (bvshl (bvadd (bvshl independent_opaque_0 ?x13) independent_opaque_0) ?x13)))
(let ((?x59 (bvadd ?x329 independent_opaque_1)))
(and (distinct ?x59 ?x8) true)))))))
(check-sat)
