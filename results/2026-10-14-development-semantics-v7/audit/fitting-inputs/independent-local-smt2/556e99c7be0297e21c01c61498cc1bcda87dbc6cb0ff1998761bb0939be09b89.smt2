(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(assert
 (let ((?x505 (bvadd (_ bv0 32) (_ bv0 32))))
(and (distinct (_ bv0 32) ?x505) true)))
(check-sat)
