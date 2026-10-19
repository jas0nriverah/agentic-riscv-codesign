(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x624 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))) independent_opaque_1)))
(let ((?x219 (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))))
(let ((?x538 (bvsub independent_opaque_1 ?x219)))
(and (distinct ?x538 ?x624) true)))))
(check-sat)
