(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x332 (bvadd independent_opaque_0 (_ bv17 32))))
(and (distinct ?x332 ?x332) true)))
(check-sat)
