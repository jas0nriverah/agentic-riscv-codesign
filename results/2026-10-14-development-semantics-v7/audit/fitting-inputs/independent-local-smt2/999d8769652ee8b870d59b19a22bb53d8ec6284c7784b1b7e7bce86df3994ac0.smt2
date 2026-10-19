(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x72 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x34 (bvadd independent_opaque_0 (bvshl independent_opaque_1 (bvand (_ bv0 32) (_ bv31 32))))))
(and (distinct ?x34 ?x72) true))))
(check-sat)
