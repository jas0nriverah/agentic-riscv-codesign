(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x66 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv30 32) (_ bv31 32)))) (_ bv1023 32))))
(let ((?x113 (bvadd independent_opaque_0 ?x66)))
(let ((?x76 (bvshl independent_opaque_1 (bvand (_ bv30 32) (_ bv31 32)))))
(let ((?x89 (bvsub (bvadd independent_opaque_0 (_ bv1023 32)) ?x76)))
(and (distinct ?x89 ?x113) true))))))
(check-sat)
