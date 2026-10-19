(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x424 (bvadd independent_opaque_0 (_ bv11 32))))
(and (distinct ?x424 ?x424) true)))
(check-sat)
