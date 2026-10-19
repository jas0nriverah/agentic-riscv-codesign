(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x402 (bvadd independent_opaque_0 (bvadd (bvsub (_ bv0 32) independent_opaque_1) (_ bv1023 32)))))
(let ((?x941 (bvsub (bvadd independent_opaque_0 (_ bv1023 32)) independent_opaque_1)))
(and (distinct ?x941 ?x402) true))))
(check-sat)
