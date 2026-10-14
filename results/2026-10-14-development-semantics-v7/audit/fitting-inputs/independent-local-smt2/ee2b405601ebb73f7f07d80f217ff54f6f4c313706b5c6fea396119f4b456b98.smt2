(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x756 (bvadd independent_opaque_0 (_ bv7 32))))
(and (distinct ?x756 ?x756) true)))
(check-sat)
