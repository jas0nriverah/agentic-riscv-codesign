(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x756 (bvadd independent_opaque_1 (_ bv3 32))))
(let ((?x402 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x756)))
(let ((?x98 (bvsub ?x756 independent_opaque_0)))
(and (distinct ?x98 ?x402) true)))))
(check-sat)
