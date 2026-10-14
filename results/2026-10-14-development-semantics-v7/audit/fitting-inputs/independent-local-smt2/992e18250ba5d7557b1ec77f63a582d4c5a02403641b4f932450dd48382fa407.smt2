(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x98 (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))))
(let ((?x13 (bvsub (_ bv0 32) ?x98)))
(and (distinct ?x98 ?x13) true))))
(check-sat)
