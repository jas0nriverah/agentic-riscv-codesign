(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(assert
 (let ((?x308 (bvadd (_ bv0 32) (_ bv1 32))))
(and (distinct (_ bv1 32) ?x308) true)))
(check-sat)
