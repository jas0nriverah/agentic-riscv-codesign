(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(assert
 (let ((?x15 (bvadd (_ bv0 32) (_ bv84 32))))
(and (distinct (_ bv84 32) ?x15) true)))
(check-sat)
