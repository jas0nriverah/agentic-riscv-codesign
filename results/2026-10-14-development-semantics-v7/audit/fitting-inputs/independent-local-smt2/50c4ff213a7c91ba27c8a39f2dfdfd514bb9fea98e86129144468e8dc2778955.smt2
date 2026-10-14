(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1180 (bvshl independent_opaque_0 (bvand (_ bv31 32) (_ bv31 32)))))
(let ((?x402 (bvsub (_ bv0 32) ?x1180)))
(and (distinct ?x1180 ?x402) true))))
(check-sat)
