(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x306 (bvadd independent_opaque_0 (_ bv16 32))))
(and (distinct ?x306 ?x306) true)))
(check-sat)
