(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x356 (bvshl independent_opaque_1 (bvand (_ bv7 32) (_ bv31 32)))))
(let ((?x402 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x356)))
(let ((?x308 (bvsub ?x356 independent_opaque_0)))
(and (distinct ?x308 ?x402) true)))))
(check-sat)
