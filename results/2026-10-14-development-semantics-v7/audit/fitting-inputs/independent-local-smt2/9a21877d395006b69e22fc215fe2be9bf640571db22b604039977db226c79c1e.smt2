(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1264 (bvshl independent_opaque_0 (bvand (_ bv0 32) (_ bv31 32)))))
(and (distinct ?x1264 independent_opaque_0) true)))
(check-sat)
