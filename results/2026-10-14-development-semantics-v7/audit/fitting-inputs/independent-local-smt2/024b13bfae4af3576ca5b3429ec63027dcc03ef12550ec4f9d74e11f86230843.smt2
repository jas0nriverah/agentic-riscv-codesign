(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x15 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv13 32) (_ bv31 32)))) (bvsub (_ bv0 32) (bvshl independent_opaque_2 (bvand (_ bv13 32) (_ bv31 32)))))))
(let ((?x246 (bvadd independent_opaque_0 ?x15)))
(let ((?x1159 (bvand (_ bv13 32) (_ bv31 32))))
(let ((?x113 (bvsub independent_opaque_0 (bvshl (bvadd independent_opaque_1 independent_opaque_2) ?x1159))))
(and (distinct ?x113 ?x246) true))))))
(check-sat)
