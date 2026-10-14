(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x958 (bvadd independent_opaque_0 (_ bv4294967263 32))))
(and (distinct ?x958 ?x958) true)))
(check-sat)
