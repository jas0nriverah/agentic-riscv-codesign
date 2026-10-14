(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1180 (bvadd independent_opaque_0 (_ bv63 32))))
(and (distinct ?x1180 ?x1180) true)))
(check-sat)
