(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x7 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x52 (bvadd independent_opaque_0 (bvshl independent_opaque_1 (bvand (_ bv0 32) (_ bv31 32))))))
(and (distinct ?x52 ?x7) true))))
(check-sat)
