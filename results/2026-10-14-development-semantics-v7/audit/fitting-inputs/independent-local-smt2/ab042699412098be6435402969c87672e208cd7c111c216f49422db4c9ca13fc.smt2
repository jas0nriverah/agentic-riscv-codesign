(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x38 (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32)))))
(let ((?x44 (bvadd ?x38 independent_opaque_1)))
(let ((?x1153 (bvadd independent_opaque_1 ?x38)))
(and (distinct ?x1153 ?x44) true)))))
(check-sat)
