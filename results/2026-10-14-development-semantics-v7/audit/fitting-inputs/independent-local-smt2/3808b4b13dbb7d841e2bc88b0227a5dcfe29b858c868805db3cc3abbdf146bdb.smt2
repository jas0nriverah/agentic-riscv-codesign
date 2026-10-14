(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1153 (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))))
(let ((?x446 (bvsub (_ bv0 32) ?x1153)))
(and (distinct ?x1153 ?x446) true))))
(check-sat)
