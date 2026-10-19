(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1159 (bvadd independent_opaque_0 (_ bv30 32))))
(and (distinct ?x1159 ?x1159) true)))
(check-sat)
