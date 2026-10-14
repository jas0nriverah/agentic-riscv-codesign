(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x305 (bvadd independent_opaque_0 (_ bv4294967041 32))))
(and (distinct ?x305 ?x305) true)))
(check-sat)
