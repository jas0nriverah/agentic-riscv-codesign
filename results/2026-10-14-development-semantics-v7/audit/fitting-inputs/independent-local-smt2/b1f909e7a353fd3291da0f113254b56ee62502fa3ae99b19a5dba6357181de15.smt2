(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1196 (bvadd independent_opaque_0 (_ bv9 32))))
(and (distinct ?x1196 ?x1196) true)))
(check-sat)
