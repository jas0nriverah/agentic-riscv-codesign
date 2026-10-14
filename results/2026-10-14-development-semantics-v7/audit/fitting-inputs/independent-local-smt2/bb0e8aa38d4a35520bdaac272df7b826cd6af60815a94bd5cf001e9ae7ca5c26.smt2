(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x84 (bvadd independent_opaque_0 (_ bv4294966274 32))))
(and (distinct ?x84 ?x84) true)))
(check-sat)
