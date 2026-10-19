(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x67 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) (bvshl independent_opaque_0 (bvand (_ bv7 32) (_ bv31 32))))))
(let ((?x305 (bvadd independent_opaque_0 ?x67)))
(let ((?x329 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x505 (bvadd (bvshl independent_opaque_0 (bvand (_ bv5 32) (_ bv31 32))) independent_opaque_0)))
(let ((?x10 (bvadd (bvshl ?x505 ?x329) independent_opaque_0)))
(and (distinct ?x10 ?x305) true)))))))
(check-sat)
