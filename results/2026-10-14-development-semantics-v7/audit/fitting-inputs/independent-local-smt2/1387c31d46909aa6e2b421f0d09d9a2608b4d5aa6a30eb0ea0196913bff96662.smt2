(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x48 (bvadd independent_opaque_0 (_ bv30 32))))
(and (distinct ?x48 ?x48) true)))
(check-sat)
