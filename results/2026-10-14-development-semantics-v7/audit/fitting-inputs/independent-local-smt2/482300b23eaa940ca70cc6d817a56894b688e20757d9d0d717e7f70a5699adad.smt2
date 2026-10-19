(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x289 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv30 32) (_ bv31 32)))) (bvshl independent_opaque_2 (bvand (_ bv30 32) (_ bv31 32))))))
(let ((?x555 (bvadd independent_opaque_0 ?x289)))
(let ((?x958 (bvand (_ bv30 32) (_ bv31 32))))
(let ((?x624 (bvsub independent_opaque_0 (bvshl (bvsub independent_opaque_1 independent_opaque_2) ?x958))))
(and (distinct ?x624 ?x555) true))))))
(check-sat)
