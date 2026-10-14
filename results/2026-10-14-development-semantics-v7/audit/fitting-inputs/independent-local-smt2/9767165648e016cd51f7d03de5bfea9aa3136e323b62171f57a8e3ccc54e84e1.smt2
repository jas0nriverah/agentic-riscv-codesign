(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1141 (bvadd independent_opaque_0 (_ bv4294967288 32))))
(and (distinct ?x1141 ?x1141) true)))
(check-sat)
