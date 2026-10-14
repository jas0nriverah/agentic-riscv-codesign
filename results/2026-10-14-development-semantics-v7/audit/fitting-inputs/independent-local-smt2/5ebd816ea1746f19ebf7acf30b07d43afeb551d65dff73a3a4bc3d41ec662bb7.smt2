(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x684 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv30 32) (_ bv31 32)))) (bvshl independent_opaque_2 (bvand (_ bv30 32) (_ bv31 32))))))
(let ((?x626 (bvadd independent_opaque_0 ?x684)))
(let ((?x1000 (bvand (_ bv30 32) (_ bv31 32))))
(let ((?x1340 (bvsub independent_opaque_0 (bvshl (bvsub independent_opaque_1 independent_opaque_2) ?x1000))))
(and (distinct ?x1340 ?x626) true))))))
(check-sat)
