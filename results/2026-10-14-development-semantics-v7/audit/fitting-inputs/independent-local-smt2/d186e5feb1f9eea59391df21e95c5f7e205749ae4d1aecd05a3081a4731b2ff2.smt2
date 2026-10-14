(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x843 (bvadd independent_opaque_0 (_ bv8 32))))
(and (distinct ?x843 ?x843) true)))
(check-sat)
