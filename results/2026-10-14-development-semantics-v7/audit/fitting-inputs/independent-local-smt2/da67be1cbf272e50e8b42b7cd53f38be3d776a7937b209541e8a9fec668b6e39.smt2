(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x41 (bvadd independent_opaque_0 (_ bv5 32))))
(and (distinct ?x41 ?x41) true)))
(check-sat)
