(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x231 (bvadd (bvshl independent_opaque_1 (bvand (_ bv16 32) (_ bv31 32))) (bvsub (_ bv0 32) (bvshl independent_opaque_2 (bvand (_ bv16 32) (_ bv31 32)))))))
(let ((?x703 (bvadd independent_opaque_0 ?x231)))
(let ((?x1180 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x538 (bvsub independent_opaque_0 (bvshl (bvsub independent_opaque_2 independent_opaque_1) ?x1180))))
(and (distinct ?x538 ?x703) true))))))
(check-sat)
