(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1141 (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32)))))
(let ((?x1153 (bvadd ?x1141 independent_opaque_1)))
(let ((?x38 (bvadd independent_opaque_1 ?x1141)))
(and (distinct ?x38 ?x1153) true)))))
(check-sat)
