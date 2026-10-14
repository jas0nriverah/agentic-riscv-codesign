(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x385 (bvadd independent_opaque_0 (_ bv4294967295 32))))
(and (distinct ?x385 ?x385) true)))
(check-sat)
