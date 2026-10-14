(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1265 (bvadd independent_opaque_0 (_ bv4294967202 32))))
(and (distinct ?x1265 ?x1265) true)))
(check-sat)
