(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x98 (bvadd independent_opaque_0 (_ bv2047 32))))
(and (distinct ?x98 ?x98) true)))
(check-sat)
