(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1183 (bvadd independent_opaque_0 (bvsub (_ bv0 32) independent_opaque_1))))
(let ((?x402 (bvsub independent_opaque_0 independent_opaque_1)))
(and (distinct ?x402 ?x1183) true))))
(check-sat)
